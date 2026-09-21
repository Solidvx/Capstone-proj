#include "can_publisher.h"

#include <gtest/gtest.h>

TEST(CanPublisher, EncodesBmsStatusPerIcd) {
    const auto frame = encodeBmsStatusFrame({75.0f, 95.0f, 42.0f, -2.0f, 25});

    EXPECT_EQ(frame.id, 0x100U);
    EXPECT_EQ(frame.dlc, 8);
    EXPECT_EQ(frame.data[0], 0x96);
    EXPECT_EQ(frame.data[1], 0xBE);
    EXPECT_EQ(frame.data[2], 0x10);
    EXPECT_EQ(frame.data[3], 0x68);
    EXPECT_EQ(frame.data[4], 0xFF);
    EXPECT_EQ(frame.data[5], 0xEC);
    EXPECT_EQ(frame.data[6], 0x41);
    EXPECT_EQ(frame.data[7], 0x00);
}

TEST(CanPublisher, EncodesFailSafeEventPerIcd) {
    const auto frame = encodeFailSafeFrame({0, 1, 0x01, 19.0f, 30});

    EXPECT_EQ(frame.id, 0x101U);
    EXPECT_EQ(frame.dlc, 8);
    EXPECT_EQ(frame.data[0], 0x00);
    EXPECT_EQ(frame.data[1], 0x01);
    EXPECT_EQ(frame.data[2], 0x01);
    EXPECT_EQ(frame.data[3], 0x26);
    EXPECT_EQ(frame.data[4], 0x46);
    EXPECT_EQ(frame.data[5], 0x00);
    EXPECT_EQ(frame.data[6], 0x00);
    EXPECT_EQ(frame.data[7], 0x00);
}
