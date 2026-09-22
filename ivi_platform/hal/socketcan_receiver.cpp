#include "socketcan_receiver.h"

#include "can_parser.h"

#include <algorithm>
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

    socket_fd_ = ::socket(PF_CAN, SOCK_RAW | SOCK_CLOEXEC, CAN_RAW);
    if (socket_fd_ < 0) {
        setError("socket(PF_CAN) failed");
        closeDescriptors();
        return false;
    }

    const can_filter filters[] = {
        {kCanIdBmsStatus, CAN_SFF_MASK},
        {kCanIdBmsFailSafe, CAN_SFF_MASK},
        {kCanIdBmsSecOc, CAN_SFF_MASK},
        {kCanIdFailSafeSecOc, CAN_SFF_MASK},
        {kCanIdIdsAlert, CAN_SFF_MASK},
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
        (void)::write(wake_fds_[1], &signal, sizeof(signal));
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

void SocketCanReceiver::receiveLoop() {
#if defined(__linux__)
    pollfd descriptors[2] = {{socket_fd_, POLLIN, 0}, {wake_fds_[0], POLLIN, 0}};
    while (running_.load()) {
        const int result = ::poll(descriptors, 2, 1000);
        if (result < 0) {
            if (errno == EINTR) {
                continue;
            }
            setError("poll() failed");
            break;
        }
        if (result == 0) {
            continue;
        }
        if ((descriptors[1].revents & POLLIN) != 0) {
            break;
        }
        if ((descriptors[0].revents & POLLIN) == 0) {
            continue;
        }

        can_frame frame{};
        const auto received = ::read(socket_fd_, &frame, sizeof(frame));
        if (received != static_cast<ssize_t>(sizeof(frame))) {
            if (received < 0 && (errno == EINTR || errno == EAGAIN)) {
                continue;
            }
            setError("invalid SocketCAN read length");
            continue;
        }
        if ((frame.can_id & (CAN_EFF_FLAG | CAN_RTR_FLAG | CAN_ERR_FLAG)) != 0U ||
            frame.can_dlc != kClassicCanPayloadSize) {
            continue;
        }
        const auto can_id = frame.can_id & CAN_SFF_MASK;
        if (!isSupportedCanId(can_id)) {
            continue;
        }
        CanPayload payload{};
        std::copy_n(frame.data, payload.size(), payload.begin());
        FrameCallback callback;
        {
            std::lock_guard<std::mutex> lock(mutex_);
            callback = callback_;
        }
        if (callback) {
            callback(can_id, payload);
        }
    }
#endif
    running_.store(false);
}

void SocketCanReceiver::closeDescriptors() {
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
