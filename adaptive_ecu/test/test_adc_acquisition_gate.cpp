#include "adc_acquisition_gate.h"
#include <gtest/gtest.h>

TEST(AdcAcquisitionGate, PollAndRequestIntervals) {
    AdcAcquisitionGate gate;
    ASSERT_TRUE(gate.begin(0));
    EXPECT_FALSE(gate.pollDue(0));
    EXPECT_TRUE(gate.pollDue(1));
    EXPECT_FALSE(gate.pollDue(1));
    EXPECT_TRUE(gate.finish(8, true));
    EXPECT_FALSE(gate.finish(9, true));
    EXPECT_FALSE(gate.begin(99));
    EXPECT_TRUE(gate.begin(100));
}

TEST(AdcAcquisitionGate, ExpiryDoesNotReleaseOutstandingRequest) {
    AdcAcquisitionGate gate;
    ASSERT_TRUE(gate.begin(0));
    EXPECT_FALSE(gate.expired(19));
    EXPECT_TRUE(gate.expired(20));
    EXPECT_FALSE(gate.pollDue(20));
    EXPECT_FALSE(gate.begin(100));
    EXPECT_TRUE(gate.pending());
    EXPECT_FALSE(gate.finish(101, true));
    EXPECT_TRUE(gate.begin(102));
    EXPECT_FALSE(gate.finish(103, false));
    EXPECT_FALSE(gate.begin(104));
}
