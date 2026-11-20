#include "ads1115_acquirer.h"

#include <gtest/gtest.h>

#include <chrono>
#include <atomic>
#include <thread>

namespace {
// Fake ADS1115 on a fake monotonic clock. Reading the conversion register
// advances time by conversion_delay to model a slow transfer.
class Bus : public Ads1115Transport {
public:
    std::uint64_t time = 0;
    unsigned conversion_delay = 0;
    std::uint16_t raw = 13200;
    bool fail = false, waiting = false, hold_busy = false;
    bool write(const std::uint8_t*, std::size_t) override {
        if (hold_busy) waiting = true;
        return !fail;
    }
    bool readRegister(std::uint8_t pointer, std::uint8_t* bytes, std::size_t) override {
        if (fail) return false;
        const std::uint16_t word = pointer == 0 ? raw : (waiting ? 0x4383 : 0xc383);
        if (pointer == 0) time += conversion_delay;
        bytes[0] = word >> 8;
        bytes[1] = word & 255;
        return true;
    }
};

struct Fixture {
    Bus bus;
    Ads1115Acquirer acquirer{bus, [this] { return bus.time; }};
    // Ticks once per millisecond from..to inclusive; returns finished requests.
    unsigned run(std::uint64_t from, std::uint64_t to) {
        unsigned finished = 0;
        for (auto t = from; t <= to; ++t) {
            bus.time = t;
            finished += acquirer.tick() ? 1U : 0U;
        }
        return finished;
    }
};
}  // namespace

TEST(Ads1115Acquirer, PublishesOneResultPerRequestInterval) {
    Fixture f;
    EXPECT_EQ(f.run(0, 1), 1U);  // start at 0 ms, first poll completes at 1 ms
    auto s = f.acquirer.snapshot();
    EXPECT_EQ(s.sequence, 1U);
    EXPECT_EQ(s.last_valid_sequence, 1U);
    EXPECT_EQ(s.last_error_sequence, 0U);
    EXPECT_EQ(s.last_valid_ms, 1U);
    EXPECT_EQ(s.raw, 13200);
    EXPECT_FLOAT_EQ(s.pack_v, 36.0f);

    EXPECT_EQ(f.run(2, 99), 0U);  // no new request before 100 ms
    EXPECT_EQ(f.run(100, 101), 1U);
    s = f.acquirer.snapshot();
    EXPECT_EQ(s.sequence, 2U);
    EXPECT_EQ(s.last_valid_sequence, 2U);
}

TEST(Ads1115Acquirer, LateResultIsRejectedNotPublishedAsValid) {
    Fixture f;
    f.bus.conversion_delay = 19;  // poll at 1 ms returns at 20 ms: expired
    EXPECT_EQ(f.run(0, 1), 1U);
    const auto s = f.acquirer.snapshot();
    EXPECT_EQ(s.last_error_sequence, 1U);
    EXPECT_EQ(s.last_valid_sequence, 0U);
    EXPECT_EQ(s.last_error, AdcError::Late);
    EXPECT_EQ(s.last_error_elapsed_ms, 20U);
    EXPECT_EQ(describeAdcError(s), "reason=late 20ms");
}

TEST(Ads1115Acquirer, ReadFailureWhilePollingIsRecorded) {
    Fixture f;
    ASSERT_EQ(f.run(0, 0), 0U);  // request started
    f.bus.fail = true;
    EXPECT_EQ(f.run(1, 1), 1U);
    const auto s = f.acquirer.snapshot();
    EXPECT_EQ(s.last_error, AdcError::ReadFailed);
    EXPECT_EQ(describeAdcError(s), "reason=i2c-read");
}

TEST(Ads1115Acquirer, IoErrorIsRecordedAndRetriedAfterInterval) {
    Fixture f;
    f.bus.fail = true;
    EXPECT_EQ(f.run(0, 0), 1U);
    EXPECT_EQ(f.acquirer.snapshot().last_error_sequence, 1U);
    EXPECT_EQ(f.acquirer.snapshot().last_error, AdcError::StartFailed);
    EXPECT_EQ(describeAdcError(f.acquirer.snapshot()), "reason=i2c-start");
    EXPECT_EQ(f.run(1, 99), 0U);  // a failure still respects the request interval
    f.bus.fail = false;
    EXPECT_EQ(f.run(100, 101), 1U);
    const auto s = f.acquirer.snapshot();
    EXPECT_EQ(s.last_valid_sequence, 2U);
    EXPECT_EQ(s.last_error_sequence, 1U);
}

TEST(Ads1115Acquirer, UnfinishedConversionExpiresAt20msAndRecovers) {
    Fixture f;
    f.bus.hold_busy = true;
    EXPECT_EQ(f.run(0, 19), 0U);
    EXPECT_EQ(f.run(20, 20), 1U);
    EXPECT_EQ(f.acquirer.snapshot().last_error_sequence, 1U);
    EXPECT_EQ(f.acquirer.snapshot().last_error, AdcError::Timeout);
    EXPECT_EQ(describeAdcError(f.acquirer.snapshot()), "reason=timeout");
    f.bus.hold_busy = f.bus.waiting = false;
    EXPECT_EQ(f.run(21, 99), 0U);
    EXPECT_EQ(f.run(100, 101), 1U);
    EXPECT_EQ(f.acquirer.snapshot().last_valid_sequence, 2U);
}

TEST(Ads1115Acquirer, OutOfRangeRawIsRejectedAndKeepsLastValidValue) {
    Fixture f;
    ASSERT_EQ(f.run(0, 1), 1U);
    f.bus.raw = static_cast<std::uint16_t>(-33);  // beyond the endpoint tolerance
    EXPECT_EQ(f.run(100, 101), 1U);
    const auto s = f.acquirer.snapshot();
    EXPECT_EQ(s.last_error_sequence, 2U);
    EXPECT_EQ(s.last_valid_sequence, 1U);
    EXPECT_EQ(s.raw, 13200);
    EXPECT_EQ(s.last_error, AdcError::OutOfRange);
    EXPECT_EQ(s.last_error_raw, -33);
    EXPECT_EQ(describeAdcError(s), "reason=range raw=-33");
}

TEST(Ads1115AcquisitionWorker, PublishesResultsFromItsOwnThread) {
    Bus bus;
    const auto owner = std::this_thread::get_id();
    std::atomic<std::uint64_t> time{0};
    std::atomic<bool> worker_clock_used{false}, owner_clock_used{false};
    // This checks threading/publication, not host scheduling latency. The
    // deterministic acquirer cases above still enforce the real 20ms policy.
    Ads1115AcquisitionWorker worker(bus, [&] {
        if (std::this_thread::get_id() == owner) owner_clock_used = true;
        else worker_clock_used = true;
        return time.fetch_add(1);
    });
    worker.start();
    AdcSnapshot s;
    for (int i = 0; i < 200 && s.last_valid_sequence < 2; ++i) {
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
        s = worker.snapshot();
    }
    worker.stop();
    EXPECT_GE(s.last_valid_sequence, 2U);
    EXPECT_EQ(s.last_error_sequence, 0U);
    EXPECT_FLOAT_EQ(s.pack_v, 36.0f);
    EXPECT_TRUE(worker_clock_used);
    EXPECT_FALSE(owner_clock_used);
}
