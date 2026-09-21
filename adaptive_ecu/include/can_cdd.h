#pragma once

#include "can_driver.h"

#include <atomic>
#include <mutex>
#include <string>
#include <thread>

class SocketCanCdd : public CanDriver {
public:
    SocketCanCdd() = default;
    ~SocketCanCdd() override;

    bool open(const std::string& interface_name) override;
    void close() override;
    bool send(const CanFrame& frame) override;
    void registerCallback(CanCallback callback) override;
    void startReceive() override;
    void stopReceive() override;

private:
    void receiveLoop();

    int socket_fd_ = -1;
    std::atomic<bool> running_{false};
    std::thread receive_thread_;
    std::mutex callback_mutex_;
    CanCallback callback_;
};
