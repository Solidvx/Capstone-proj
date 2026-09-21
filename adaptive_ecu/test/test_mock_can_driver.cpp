#include "mock_can_driver.h"

#include <gtest/gtest.h>

TEST(MockCanDriver, OpenSendStoreAndCallback) {
    MockCanDriver driver;
    CanFrame callback_frame{};
    int callback_count = 0;

    driver.registerCallback([&](const CanFrame& frame) {
        callback_frame = frame;
        ++callback_count;
    });

    ASSERT_TRUE(driver.open("vcan0"));
    driver.startReceive();

    CanFrame frame{};
    frame.id = 0x100;
    frame.dlc = 8;
    frame.data = {0x96, 0xBE, 0x10, 0x68, 0xFF, 0xEC, 0x41, 0x00};

    ASSERT_TRUE(driver.send(frame));
    const auto sent = driver.sentFrames();

    ASSERT_EQ(sent.size(), 1U);
    EXPECT_EQ(sent[0].id, 0x100U);
    EXPECT_EQ(sent[0].data[0], 0x96);
    EXPECT_EQ(callback_count, 1);
    EXPECT_EQ(callback_frame.id, 0x100U);
    EXPECT_TRUE(driver.isReceiving());
}

TEST(MockCanDriver, RejectsSendWhenClosed) {
    MockCanDriver driver;
    CanFrame frame{};
    frame.id = 0x100;
    frame.dlc = 8;

    EXPECT_FALSE(driver.send(frame));
}
