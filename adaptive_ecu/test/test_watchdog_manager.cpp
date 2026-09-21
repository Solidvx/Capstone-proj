#include "watchdog_manager.h"

#include <gtest/gtest.h>

#include <atomic>
#include <chrono>
#include <thread>

TEST(WatchdogManager, CallsTimeoutCallback) {
    std::atomic<uint32_t> timeout_count{0};
    WatchdogManager watchdog(10, 30);

    watchdog.start([&](uint32_t count) { timeout_count = count; });
    std::this_thread::sleep_for(std::chrono::milliseconds(80));
    watchdog.stop();

    EXPECT_GE(timeout_count.load(), 1U);
    EXPECT_GE(watchdog.timeoutCount(), 1U);
}

TEST(WatchdogManager, KickPreventsTimeout) {
    std::atomic<uint32_t> timeout_count{0};
    WatchdogManager watchdog(10, 50);

    watchdog.start([&](uint32_t count) { timeout_count = count; });
    for (int i = 0; i < 4; ++i) {
        watchdog.kick();
        std::this_thread::sleep_for(std::chrono::milliseconds(15));
    }
    watchdog.stop();

    EXPECT_EQ(timeout_count.load(), 0U);
}
