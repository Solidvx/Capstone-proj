#include "publisher.h"

#include <gtest/gtest.h>

#include <atomic>
#include <thread>
#include <vector>

namespace {
struct Sample {
    int value = 0;
};
}

TEST(Publisher, DeliversToAllSubscribers) {
    Publisher<Sample> publisher;
    int first = 0;
    int second = 0;

    publisher.subscribe([&](const Sample& sample) { first = sample.value; });
    publisher.subscribe([&](const Sample& sample) { second = sample.value; });
    publisher.send({42});

    EXPECT_EQ(first, 42);
    EXPECT_EQ(second, 42);
    EXPECT_EQ(publisher.subscriberCount(), 2U);
}

TEST(Publisher, SupportsConcurrentSubscribeAndSend) {
    Publisher<Sample> publisher;
    std::atomic<int> received{0};
    std::vector<std::thread> threads;

    for (int i = 0; i < 10; ++i) {
        threads.emplace_back([&] {
            publisher.subscribe([&](const Sample&) { ++received; });
            publisher.send({1});
        });
    }

    for (auto& thread : threads) {
        thread.join();
    }

    publisher.send({1});
    EXPECT_GE(received.load(), 10);
}
