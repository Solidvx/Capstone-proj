#include "socketcan_receiver.h"

#include "can_frame_validator.h"
#include "receive_retry_policy.h"

#include <algorithm>
#include <chrono>
#include <utility>

#if defined(__linux__)
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <linux/can.h>
#include <linux/can/raw.h>
#include <net/if.h>
#include <poll.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>
#endif

namespace ivi {
namespace {

#if defined(__linux__)
constexpr int kMaxReceiveRetries = 3;
constexpr auto kReceiveRetryDelay = std::chrono::milliseconds{10};
#endif

}  // namespace

SocketCanReceiver::~SocketCanReceiver() {
    stop();
}

bool SocketCanReceiver::open(const std::string& interface_name) {
    stop();
#if defined(__linux__)
    if (::pipe2(wake_fds_, O_CLOEXEC | O_NONBLOCK) != 0) {
        setError("pipe2() failed");
        return false;
    }

    socket_fd_ = ::socket(PF_CAN, SOCK_RAW | SOCK_CLOEXEC | SOCK_NONBLOCK, CAN_RAW);
    if (socket_fd_ < 0) {
        setError("socket(PF_CAN) failed");
        closeDescriptors();
        return false;
    }

    int overflow_enabled=1;
    if(::setsockopt(socket_fd_,SOL_SOCKET,SO_RXQ_OVFL,&overflow_enabled,sizeof(overflow_enabled))!=0){
        setError("setsockopt(SO_RXQ_OVFL) failed");closeDescriptors();return false;
    }
    received_frames_=0;socket_drops_=0;drop_measurement_=true;
    const can_filter filters[] = {
        {kCanIdBmsStatus, CAN_SFF_MASK},
        {kCanIdBmsFailSafe, CAN_SFF_MASK},
        {kCanIdBmsSecOc, CAN_SFF_MASK},
        {kCanIdFailSafeSecOc, CAN_SFF_MASK},
        {kCanIdIdsAlert, CAN_SFF_MASK},
        {kCanIdCurrentState,CAN_SFF_MASK|CAN_EFF_FLAG|CAN_RTR_FLAG},
        {kCanIdCurrentStateSecOc,CAN_SFF_MASK|CAN_EFF_FLAG|CAN_RTR_FLAG},
        {kCanIdSessionEcu,CAN_SFF_MASK|CAN_EFF_FLAG|CAN_RTR_FLAG},
        {kCanIdDiagnosticEcu,CAN_SFF_MASK|CAN_EFF_FLAG|CAN_RTR_FLAG},
    };
    if (::setsockopt(socket_fd_, SOL_CAN_RAW, CAN_RAW_FILTER, filters, sizeof(filters)) != 0) {
        setError("setsockopt(CAN_RAW_FILTER) failed");
        closeDescriptors();
        return false;
    }

    ifreq request{};
    std::strncpy(request.ifr_name, interface_name.c_str(), IFNAMSIZ - 1);
    if (::ioctl(socket_fd_, SIOCGIFINDEX, &request) != 0) {
        setError("CAN interface was not found: " + interface_name);
        closeDescriptors();
        return false;
    }

    sockaddr_can address{};
    address.can_family = AF_CAN;
    address.can_ifindex = request.ifr_ifindex;
    if (::bind(socket_fd_, reinterpret_cast<sockaddr*>(&address), sizeof(address)) != 0) {
        setError("bind() failed for CAN interface: " + interface_name);
        closeDescriptors();
        return false;
    }
    setError("");
    return true;
#else
    (void)interface_name;
    setError("SocketCAN requires Linux");
    return false;
#endif
}

void SocketCanReceiver::setCallback(FrameCallback callback) {
    std::lock_guard<std::mutex> lock(mutex_);
    callback_ = std::move(callback);
}

bool SocketCanReceiver::start() {
    if (running_.load()) {
        return true;
    }
    if (socket_fd_ < 0) {
        setError("CAN socket is not open");
        return false;
    }
    running_.store(true);
    worker_ = std::thread(&SocketCanReceiver::receiveLoop, this);
    return true;
}

void SocketCanReceiver::stop() {
    const bool was_running = running_.exchange(false);
#if defined(__linux__)
    if (was_running && wake_fds_[1] >= 0) {
        const std::uint8_t signal = 1;
        const auto written = ::write(wake_fds_[1], &signal, sizeof(signal));
        if (written < 0 && errno != EAGAIN && errno != EWOULDBLOCK) {
            setError("wake pipe write failed");
        }
    }
#else
    (void)was_running;
#endif
    if (worker_.joinable()) {
        worker_.join();
    }
    closeDescriptors();
}

bool SocketCanReceiver::isRunning() const {
    return running_.load();
}

std::string SocketCanReceiver::lastError() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return last_error_;
}

bool SocketCanReceiver::sendControl(std::uint32_t id,const CanPayload& payload){
    if(id!=kCanIdSessionIvi && id!=kCanIdDiagnosticIvi)return false;
    std::lock_guard<std::mutex> lock(mutex_);
#if defined(__linux__)
    if(socket_fd_<0)return false;
    can_frame frame{};frame.can_id=id;frame.can_dlc=8;
    std::copy(payload.begin(),payload.end(),frame.data);
    return ::send(socket_fd_,&frame,sizeof frame,MSG_DONTWAIT|MSG_NOSIGNAL)==sizeof frame;
#else
    (void)payload;return false;
#endif
}

void SocketCanReceiver::receiveLoop() {
#if defined(__linux__)
    std::uint32_t last_drop_counter=0;
    pollfd descriptors[2] = {{socket_fd_, POLLIN, 0}, {wake_fds_[0], POLLIN, 0}};
    ReceiveRetryBudget retry_budget(kMaxReceiveRetries);
    const auto retry = [this, &retry_budget](const char* operation) {
        if (!running_.load() || !retry_budget.consumeRetry()) {
            setError(std::string(operation) + " failed after receive retries");
            return false;
        }
        setError(std::string(operation) + " failed; retrying (" +
                 std::to_string(retry_budget.retriesUsed()) + "/" +
                 std::to_string(kMaxReceiveRetries) + ")");
        std::this_thread::sleep_for(kReceiveRetryDelay * retry_budget.retriesUsed());
        return running_.load();
    };

    while (running_.load()) {
        descriptors[0].revents = 0;
        descriptors[1].revents = 0;
        const int result = ::poll(descriptors, 2, 1000);
        if (result < 0) {
            if (errno == EINTR) {
                continue;
            }
            if (!retry("poll()")) {
                break;
            }
            continue;
        }
        if (result == 0) {
            continue;
        }
        if ((descriptors[1].revents & POLLIN) != 0) {
            break;
        }
        if ((descriptors[0].revents & (POLLERR | POLLHUP | POLLNVAL)) != 0) {
            if (!retry("SocketCAN poll event")) {
                break;
            }
            continue;
        }
        if ((descriptors[0].revents & POLLIN) == 0) {
            continue;
        }

        can_frame frame{};
        alignas(cmsghdr) char ancillary[CMSG_SPACE(sizeof(std::uint32_t))]{};
        iovec vector{&frame,sizeof(frame)};msghdr message{};
        message.msg_iov=&vector;message.msg_iovlen=1;
        message.msg_control=ancillary;message.msg_controllen=sizeof(ancillary);
        const auto received = ::recvmsg(socket_fd_, &message, 0);
        const auto received_at = Clock::now();
        if (received != static_cast<ssize_t>(sizeof(frame))) {
            if (received < 0 && errno == EINTR) {
                continue;
            }
            if (!retry(received < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)
                           ? "SocketCAN read would block"
                           : "SocketCAN read")) {
                break;
            }
            continue;
        }
        if(message.msg_flags&(MSG_TRUNC|MSG_CTRUNC)){drop_measurement_=false;continue;}
        ++received_frames_;
        for(auto* item=CMSG_FIRSTHDR(&message);item;item=CMSG_NXTHDR(&message,item)){
            if(item->cmsg_level==SOL_SOCKET && item->cmsg_type==SO_RXQ_OVFL){
                if(item->cmsg_len!=CMSG_LEN(sizeof(std::uint32_t))){drop_measurement_=false;continue;}
                std::uint32_t current=0;std::memcpy(&current,CMSG_DATA(item),sizeof(current));
                socket_drops_.fetch_add(static_cast<std::uint32_t>(current-last_drop_counter));last_drop_counter=current;
            }
        }
        retry_budget.reset();
        setError("");
        if (validateClassicCanFrame(frame.can_id, frame.can_dlc) !=
            CanFrameValidation::kAccepted) {
            continue;
        }
        const auto can_id = frame.can_id & kCanSffMask;
        CanPayload payload{};
        std::copy_n(frame.data, payload.size(), payload.begin());
        FrameCallback callback;
        {
            std::lock_guard<std::mutex> lock(mutex_);
            callback = callback_;
        }
        if (callback) {
            callback(can_id, payload, received_at);
        }
    }
#endif
    running_.store(false);
    drop_measurement_=false;
}

void SocketCanReceiver::closeDescriptors() {
    std::lock_guard<std::mutex> lock(mutex_);
#if defined(__linux__)
    if (socket_fd_ >= 0) {
        ::close(socket_fd_);
        socket_fd_ = -1;
    }
    for (int& fd : wake_fds_) {
        if (fd >= 0) {
            ::close(fd);
            fd = -1;
        }
    }
#endif
}

void SocketCanReceiver::setError(std::string message) {
    std::lock_guard<std::mutex> lock(mutex_);
    last_error_ = std::move(message);
}

}  // namespace ivi
