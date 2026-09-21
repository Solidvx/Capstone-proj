#include "can_cdd.h"

#include <cstring>
#include <utility>

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
    setsockopt(socket_fd_, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));

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
    if (socket_fd_ < 0 || frame.dlc > frame.data.size()) {
        return false;
    }

#if defined(__linux__)
    can_frame socket_frame{};
    socket_frame.can_id = frame.id;
    socket_frame.can_dlc = frame.dlc;
    std::memcpy(socket_frame.data, frame.data.data(), frame.data.size());
    return write(socket_fd_, &socket_frame, sizeof(socket_frame)) == sizeof(socket_frame);
#else
    return false;
#endif
}

void SocketCanCdd::registerCallback(CanCallback callback) {
    std::lock_guard<std::mutex> lock(callback_mutex_);
    callback_ = std::move(callback);
}

void SocketCanCdd::startReceive() {
    if (socket_fd_ < 0 || running_) {
        return;
    }

    running_ = true;
    receive_thread_ = std::thread(&SocketCanCdd::receiveLoop, this);
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
        if (read(socket_fd_, &socket_frame, sizeof(socket_frame)) != sizeof(socket_frame)) {
            continue;
        }

        CanFrame frame{};
        frame.id = socket_frame.can_id;
        frame.dlc = socket_frame.can_dlc;
        std::memcpy(frame.data.data(), socket_frame.data, frame.data.size());

        CanCallback callback;
        {
            std::lock_guard<std::mutex> lock(callback_mutex_);
            callback = callback_;
        }
        if (callback) {
            callback(frame);
        }
    }
#endif
}
