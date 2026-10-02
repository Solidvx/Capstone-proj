#include "hardware_sample_feed.h"

#include <gtest/gtest.h>

namespace {
AdcSnapshot valid(std::uint64_t sequence, std::uint64_t at_ms, float pack_v = 36.0f,
                  std::uint64_t last_error = 0) {
    AdcSnapshot s;
    s.sequence = sequence;
    s.last_valid_sequence = sequence;
    s.last_error_sequence = last_error;
    s.last_valid_ms = at_ms;
    s.pack_v = pack_v;
    return s;
}

AdcSnapshot error(AdcSnapshot previous) {
    ++previous.sequence;
    previous.last_error_sequence = previous.sequence;
    return previous;
}
}  // namespace

TEST(HardwareSampleFeed, NothingBeforeFirstResult) {
    HardwareSampleFeed feed;
    EXPECT_FALSE(feed.cycle(AdcSnapshot{}, 0).has_value());
    EXPECT_EQ(feed.quality(), SensorQuality::Preparing);
}

TEST(HardwareSampleFeed, ThreeNewValidResultsRequiredBeforeTransmission) {
    HardwareSampleFeed feed;
    EXPECT_FALSE(feed.cycle(valid(1, 0), 0).has_value());
    EXPECT_FALSE(feed.cycle(valid(2, 100), 100).has_value());
    const auto third = feed.cycle(valid(3, 200, 41.0f), 200);
    ASSERT_TRUE(third.has_value());
    EXPECT_FLOAT_EQ(*third, 41.0f);
    EXPECT_EQ(feed.quality(), SensorQuality::Valid);
}

TEST(HardwareSampleFeed, SameSequenceIsNotANewMeasurement) {
    HardwareSampleFeed feed;
    const auto first = valid(1, 0);
    for (int cycle = 0; cycle < 5; ++cycle) {
        EXPECT_FALSE(feed.cycle(first, 10U * cycle).has_value());
    }
    EXPECT_EQ(feed.quality(), SensorQuality::Preparing);
}

TEST(HardwareSampleFeed, KeepsPeriodWhenOneCycleSeesNoNewResult) {
    HardwareSampleFeed feed;
    feed.cycle(valid(1, 0), 0);
    feed.cycle(valid(2, 100), 100);
    ASSERT_TRUE(feed.cycle(valid(3, 200), 200).has_value());
    // Worker phase drift: no new request finished in this cycle, result still fresh.
    EXPECT_TRUE(feed.cycle(valid(3, 200), 300).has_value());
    EXPECT_TRUE(feed.cycle(valid(4, 305), 400).has_value());
}

TEST(HardwareSampleFeed, ErrorPausesAndRequiresThreeNewResults) {
    HardwareSampleFeed feed;
    feed.cycle(valid(1, 0), 0);
    feed.cycle(valid(2, 100), 100);
    ASSERT_TRUE(feed.cycle(valid(3, 200), 200).has_value());

    const auto failed = error(valid(3, 200));
    EXPECT_FALSE(feed.cycle(failed, 300).has_value());
    EXPECT_EQ(feed.quality(), SensorQuality::ErrorWithValue);
    EXPECT_EQ(feed.errorCause(), HardwareSampleFeed::ErrorCause::Acquisition);

    EXPECT_FALSE(feed.cycle(valid(5, 400, 36.0f, 4), 400).has_value());
    EXPECT_FALSE(feed.cycle(valid(6, 500, 36.0f, 4), 500).has_value());
    EXPECT_TRUE(feed.cycle(valid(7, 600, 36.0f, 4), 600).has_value());
}

TEST(HardwareSampleFeed, StalledWorkerPausesAsError) {
    HardwareSampleFeed feed;
    feed.cycle(valid(1, 0), 0);
    feed.cycle(valid(2, 100), 100);
    ASSERT_TRUE(feed.cycle(valid(3, 200), 200).has_value());
    EXPECT_TRUE(feed.cycle(valid(3, 200), 200 + HardwareSampleFeed::kFreshnessMs).has_value());
    EXPECT_FALSE(feed.cycle(valid(3, 200), 201 + HardwareSampleFeed::kFreshnessMs).has_value());
    EXPECT_EQ(feed.quality(), SensorQuality::ErrorWithValue);
    EXPECT_EQ(feed.errorCause(), HardwareSampleFeed::ErrorCause::Stale);
}
