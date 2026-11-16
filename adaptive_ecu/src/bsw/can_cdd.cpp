#include "can_cdd.h"

#include <cstring>
#include <cerrno>
#include <utility>
#include <stdexcept>

#if defined(__linux__)
#include <linux/can.h>
#include <linux/can/raw.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>
#endif

SocketCanCdd::~SocketCanCdd() {
    close();
}

bool SocketCanCdd::open(const std::string& interface_name) {
#if defined(__linux__)
    close();

    socket_fd_ = socket(PF_CAN, SOCK_RAW, CAN_RAW);
    if (socket_fd_ < 0) {
        return false;
    }

    timeval timeout{};
    timeout.tv_usec = 100000;
    if (setsockopt(socket_fd_, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout)) != 0) {
        ::close(socket_fd_);socket_fd_=-1;return false;
    }

    ifreq ifr{};
    std::strncpy(ifr.ifr_name, interface_name.c_str(), IFNAMSIZ - 1);
    if (ioctl(socket_fd_, SIOCGIFINDEX, &ifr) < 0) {
        ::close(socket_fd_);
        socket_fd_ = -1;
        return false;
    }

    sockaddr_can address{};
    address.can_family = AF_CAN;
    address.can_ifindex = ifr.ifr_ifindex;

    if (bind(socket_fd_, reinterpret_cast<sockaddr*>(&address), sizeof(address)) < 0) {
        ::close(socket_fd_);
        socket_fd_ = -1;
        return false;
    }

    return true;
#else
    (void)interface_name;
    return false;
#endif
}

void SocketCanCdd::close() {
    stopReceive();
#if defined(__linux__)
    if (socket_fd_ >= 0) {
        ::close(socket_fd_);
        socket_fd_ = -1;
    }
#else
    socket_fd_ = -1;
#endif
}

bool SocketCanCdd::send(const CanFrame& frame) {
    const auto attempt=tx_trace_ ? tx_trace_->begin() : CanTxTrace::Attempt{};
    if (socket_fd_ < 0 || frame.dlc > frame.data.size()) {
        if(tx_trace_)tx_trace_->complete(attempt,frame,false,-1,socket_fd_<0?EBADF:EINVAL,false);
        return false;
    }

#if defined(__linux__)
    can_frame socket_frame{};
    socket_frame.can_id = frame.id;
    socket_frame.can_dlc = frame.dlc;
    std::memcpy(socket_frame.data, frame.data.data(), frame.data.size());
    // A full CAN TX queue must not stall BMS/protection or the session owner.
    // The caller observes failure; no hidden retry or counter rollback.
    const auto returned=::send(socket_fd_, &socket_frame, sizeof(socket_frame), MSG_DONTWAIT | MSG_NOSIGNAL);
    const int send_errno=errno;
    const bool accepted=returned==sizeof(socket_frame);
    if(tx_trace_)tx_trace_->complete(attempt,frame,true,returned,returned<0?send_errno:0,accepted);
    errno=send_errno;
    return accepted;
#else
    if(tx_trace_)tx_trace_->complete(attempt,frame,false,-1,ENOTSUP,false);
    return false;
#endif
}

void SocketCanCdd::enableTxTrace(int fd,const std::array<std::uint8_t,16>& instance){
    if(tx_trace_ || running_)throw std::logic_error("TX trace must be selected once before receiving");
    tx_trace_=std::make_unique<CanTxTrace>(fd,instance);
}

void SocketCanCdd::registerCallback(CanCallback callback) {
    std::lock_guard<std::mutex> lock(callback_mutex_);
    callback_ = std::move(callback);
}

void SocketCanCdd::startReceive() {
    if (socket_fd_ < 0 || running_ || receive_thread_.joinable()) {
        return;
    }

    faulted_=false;receive_error_=0;progress_=0;frames_=0;stopped_=false;running_=true;
    try {receive_thread_ = std::thread(&SocketCanCdd::receiveLoop, this);}
    catch (...) {running_=false;stopped_=true;faulted_=true;throw;}
}

SocketCanCdd::ReceiveHealth SocketCanCdd::receiveHealth() const {
    return {stopped_.load(),faulted_.load(),progress_.load(),frames_.load(),receive_error_.load()};
}

void SocketCanCdd::requestReceiveStop() {running_=false;}

bool SocketCanCdd::reapReceiveIfStopped() {
    if(!stopped_.load())return false;
    if(receive_thread_.joinable())receive_thread_.join();
    return true;
}

void SocketCanCdd::stopReceive() {
    running_ = false;
    if (receive_thread_.joinable()) {
        receive_thread_.join();
    }
}

void SocketCanCdd::receiveLoop() {
#if defined(__linux__)
    while (running_) {
        can_frame socket_frame{};
        const auto size=read(socket_fd_, &socket_frame, sizeof(socket_frame));
        if(!running_)break;
        if(size<0 && (errno==EAGAIN || errno==EWOULDBLOCK || errno==EINTR)) {
            ++progress_; // A quiet bus is a responsive receive task, not failure.
            continue;
        }
        if(size!=sizeof(socket_frame)) {
            receive_error_=size<0 ? errno : EIO;faulted_=true;break;
        }

        CanFrame frame{};
        frame.id = socket_frame.can_id;
        frame.dlc = socket_frame.can_dlc;
        std::memcpy(frame.data.data(), socket_frame.data, frame.data.size());

        try {
            CanCallback callback;
            {
                std::lock_guard<std::mutex> lock(callback_mutex_);
                callback = callback_;
            }
            if (callback) callback(frame);
        }
        catch (...) {receive_error_=ECANCELED;faulted_=true;break;}
        ++frames_;++progress_; // Completion follows callback, never precedes it.
    }
#endif
    running_=false;stopped_=true;
}
