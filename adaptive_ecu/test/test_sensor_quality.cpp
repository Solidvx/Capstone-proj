#include "sensor_quality.h"
#include <gtest/gtest.h>

TEST(SensorQuality, StartupRequiresThreeNewConversions) {
    SensorQualityTracker tracker;
    EXPECT_EQ(tracker.state(), SensorQuality::Preparing);
    EXPECT_FALSE(tracker.accept(true));
    EXPECT_FALSE(tracker.accept(false));
    EXPECT_FALSE(tracker.accept(true));
    EXPECT_EQ(tracker.state(), SensorQuality::Preparing);
    EXPECT_TRUE(tracker.accept(true));
    EXPECT_EQ(tracker.state(), SensorQuality::Valid);
    EXPECT_FALSE(tracker.accept(false));
    EXPECT_TRUE(tracker.accept(true));
}

TEST(SensorQuality, ErrorResetsRecoveryAndPreservesValueAvailability) {
    for (bool previous_value : {false, true}) {
        SensorQualityTracker tracker;
        if (previous_value) for (int k = 0; k < 3; ++k) tracker.accept(true);
        tracker.error();
        EXPECT_EQ(tracker.state(), previous_value ? SensorQuality::ErrorWithValue : SensorQuality::ErrorWithoutValue);
        EXPECT_FALSE(tracker.accept(true));
        EXPECT_EQ(tracker.state(), previous_value ? SensorQuality::RecoveringWithValue : SensorQuality::RecoveringWithoutValue);
        tracker.error();
        EXPECT_FALSE(tracker.accept(true));
        EXPECT_FALSE(tracker.accept(true));
        EXPECT_TRUE(tracker.accept(true));
        EXPECT_EQ(tracker.state(), SensorQuality::Valid);
    }
}
