#include "ads1115_sample.h"
#include "sensor_quality.h"
#include "can_publisher.h"
#include <gtest/gtest.h>

namespace {
class Bus : public Ads1115Transport {
public:
    std::uint64_t time = 0;
    unsigned conversion_delay = 0;
    std::uint16_t raw = 13200;
    bool fail = false, waiting = false, wrong_config = false, hold_busy = false;
    bool write(const std::uint8_t*, std::size_t) override {
        if (hold_busy) waiting = true;
        return !fail;
    }
    bool readRegister(std::uint8_t pointer, std::uint8_t* bytes, std::size_t) override {
        if (fail) return false;
        const std::uint16_t word = pointer == 0 ? raw :
            (wrong_config ? 0xc583 : (waiting ? 0x4383 : 0xc383));
        if (pointer == 0) time += conversion_delay;
        bytes[0] = word >> 8;
        bytes[1] = word & 255;
        return true;
    }
    bool sample(Ads1115Registers& adc, Ads1115Sample& output) {
        return acquireAds1115Sample(adc, [&] { return time; }, [&] { ++time; }, output);
    }
};
}

TEST(Ads1115Sample, PhysicalEndpointsEncodeLegacyVoltage) {
    Bus bus; Ads1115Registers adc(bus);
    for (const auto raw : {0, 13200, 26400}) {
        bus.raw = raw;
        Ads1115Sample sample;
        ASSERT_TRUE(bus.sample(adc, sample));
        const auto frame = encodeBmsStatusFrame({50, 100, sample.pack_v, -2, 25});
        const unsigned expected = raw == 0 ? 3000 : (raw == 13200 ? 3600 : 4200);
        EXPECT_EQ((frame.data[2] << 8) | frame.data[3], expected);
        EXPECT_EQ(frame.data[7], 0);
    }
}
TEST(Ads1115Sample, LateConversionIsRejectedAndCanRecover) {
    Bus bus; Ads1115Registers adc(bus); Ads1115Sample output{123, 1, 34};
    bus.conversion_delay = 19; // 1ms poll + 19ms I/O = expiry boundary.
    EXPECT_FALSE(bus.sample(adc, output));
    EXPECT_EQ(output.raw, 123);
    bus.conversion_delay = 0;
    EXPECT_TRUE(bus.sample(adc, output));
}
TEST(Ads1115Sample, IoAndRangeErrorsPreserveOutput) {
    Bus bus; Ads1115Registers adc(bus); Ads1115Sample output{123, 1, 34};
    bus.fail = true;
    EXPECT_FALSE(bus.sample(adc, output));
    bus.fail = false;
    for (const auto raw : {26401, 65535}) {
        bus.raw = raw;
        EXPECT_FALSE(bus.sample(adc, output));
        EXPECT_EQ(output.raw, 123);
    }
    bus.wrong_config = true;
    EXPECT_FALSE(bus.sample(adc, output));
}
TEST(Ads1115Sample, ThreeFreshResultsRequiredAfterError) {
    Bus bus; Ads1115Registers adc(bus); Ads1115Sample output;
    SensorQualityTracker quality;
    for (int i = 0; i < 3; ++i) {
        ASSERT_TRUE(bus.sample(adc, output));
        EXPECT_EQ(quality.accept(true), i == 2);
    }
    bus.fail = true;
    ASSERT_FALSE(bus.sample(adc, output));
    quality.error();
    EXPECT_EQ(quality.state(), SensorQuality::ErrorWithValue);
    bus.fail = false;
    for (int i = 0; i < 3; ++i) {
        ASSERT_TRUE(bus.sample(adc, output));
        EXPECT_EQ(quality.accept(true), i == 2);
    }
}

TEST(Ads1115Sample, BusyConversionExpiresWithoutPublishingAndRecovers) {
    Bus bus; Ads1115Registers adc(bus); Ads1115Sample output{123, 1, 34};
    bus.hold_busy = true;
    EXPECT_FALSE(bus.sample(adc, output));
    EXPECT_EQ(bus.time, 20u);
    EXPECT_EQ(output.raw, 123);
    bus.waiting = bus.hold_busy = false;
    EXPECT_TRUE(bus.sample(adc, output));
}
