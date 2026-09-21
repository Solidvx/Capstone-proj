#pragma once

#include <atomic>
#include <chrono>
#include <cstdint>
#include <functional>
#include <mutex>
#include <thread>

class WatchdogManager {
public:
    using TimeoutCallback = std::function<void(std::uint32_t timeout_count)>;

    WatchdogManager(int check_period_ms = 1000, int timeout_ms = 3000);
    ~WatchdogManager();

    void start(TimeoutCallback callback);
    void stop();
    void kick();
    std::uint32_t timeoutCount() const;
    bool isRunning() const;

private:
    void loop();

    std::chrono::milliseconds check_period_;
    std::chrono::milliseconds timeout_;
    std::atomic<bool> running_{false};
    std::atomic<std::uint32_t> timeout_count_{0};
    mutable std::mutex mutex_;
    std::chrono::steady_clock::time_point last_kick_;
    TimeoutCallback callback_;
    std::thread thread_;
};
