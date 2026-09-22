#pragma once

#include <atomic>
#include <cstdint>
#include <functional>
#include <mutex>
#include <string>
#include <thread>

#include "can_types.h"

namespace ivi {

class SocketCanReceiver {
public:
    using FrameCallback = std::function<void(std::uint32_t, const CanPayload&)>;

    SocketCanReceiver() = default;
    ~SocketCanReceiver();

    SocketCanReceiver(const SocketCanReceiver&) = delete;
    SocketCanReceiver& operator=(const SocketCanReceiver&) = delete;

    bool open(const std::string& interface_name);
    void setCallback(FrameCallback callback);
    bool start();
    void stop();
    bool isRunning() const;
    std::string lastError() const;

private:
    void receiveLoop();
    void closeDescriptors();
    void setError(std::string message);

    mutable std::mutex mutex_;
    FrameCallback callback_;
    std::thread worker_;
    std::atomic<bool> running_{false};
    int socket_fd_ = -1;
#if defined(__linux__)
    int wake_fds_[2] = {-1, -1};
#endif
    std::string last_error_;
};

}  // namespace ivi
