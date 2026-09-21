#include "watchdog_manager.h"

#include <utility>

WatchdogManager::WatchdogManager(int check_period_ms, int timeout_ms)
    : check_period_(check_period_ms), timeout_(timeout_ms), last_kick_(std::chrono::steady_clock::now()) {}

WatchdogManager::~WatchdogManager() {
    stop();
}

void WatchdogManager::start(TimeoutCallback callback) {
    if (running_) {
        return;
    }
    callback_ = std::move(callback);
    {
        std::lock_guard<std::mutex> lock(mutex_);
        last_kick_ = std::chrono::steady_clock::now();
    }
    running_ = true;
    thread_ = std::thread(&WatchdogManager::loop, this);
}

void WatchdogManager::stop() {
    running_ = false;
    if (thread_.joinable()) {
        thread_.join();
    }
}

void WatchdogManager::kick() {
    std::lock_guard<std::mutex> lock(mutex_);
    last_kick_ = std::chrono::steady_clock::now();
}

std::uint32_t WatchdogManager::timeoutCount() const {
    return timeout_count_;
}

bool WatchdogManager::isRunning() const {
    return running_;
}

void WatchdogManager::loop() {
    while (running_) {
        std::this_thread::sleep_for(check_period_);
        std::chrono::steady_clock::duration elapsed;
        {
            std::lock_guard<std::mutex> lock(mutex_);
            elapsed = std::chrono::steady_clock::now() - last_kick_;
        }
        if (elapsed >= timeout_) {
            const auto count = ++timeout_count_;
            if (callback_) {
                callback_(count);
            }
            {
                std::lock_guard<std::mutex> lock(mutex_);
                last_kick_ = std::chrono::steady_clock::now();
            }
        }
    }
}
