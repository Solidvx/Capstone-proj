#include "sensor_simulator.h"
#include "ekf_soc_estimator.h"
#include "failsafe_sm.h"

#include <gtest/gtest.h>

#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

TEST(SensorSimulator, ConstantModeReturnsNominalData) {
    SensorSimulator simulator(SensorSimulator::Mode::CONSTANT);
    const auto data = simulator.next();

    EXPECT_FLOAT_EQ(data.voltage_v, 42.0f);
    EXPECT_FLOAT_EQ(data.current_a, -2.0f);
    EXPECT_EQ(data.temperature_c, 25);
}

// Replaces the removed POTENTIOMETER clamp test (I-5=B). Real ADC readings are
// range-checked and rejected by convertAds1115Voltage, never clamped here.
TEST(SensorSimulator, Ads1115ModeUsesValidatedVoltageWithVirtualCurrentAndTemperature) {
    SensorSimulator simulator(SensorSimulator::Mode::ADS1115_HARDWARE);
    EXPECT_THROW(simulator.next(), std::logic_error);

    simulator.setHardwareVoltage(36.0f);
    const auto data = simulator.next();

    EXPECT_FLOAT_EQ(data.voltage_v, 36.0f);
    EXPECT_FLOAT_EQ(data.current_a, SensorSimulator::kHardwareCurrentA);
    EXPECT_EQ(data.temperature_c, SensorSimulator::kHardwareTemperatureC);
}

TEST(SensorSimulator, ParseModeAcceptsOnlyOfficialNames) {
    EXPECT_EQ(SensorSimulator::parseMode("constant"), SensorSimulator::Mode::CONSTANT);
    EXPECT_EQ(SensorSimulator::parseMode("profile_csv"), SensorSimulator::Mode::PROFILE_CSV);
    EXPECT_EQ(SensorSimulator::parseMode("random_walk"), SensorSimulator::Mode::RANDOM_WALK);
    EXPECT_EQ(SensorSimulator::parseMode("ads1115"), SensorSimulator::Mode::ADS1115_HARDWARE);
    EXPECT_FALSE(SensorSimulator::parseMode("potentiometer").has_value());
    EXPECT_FALSE(SensorSimulator::parseMode("").has_value());
    EXPECT_FALSE(SensorSimulator::parseMode("ADS1115").has_value());
}

TEST(SensorSimulator, ProfileCsvReturnsRowsThenHoldsLast) {
    const std::string path = std::string(ECU_SOURCE_DIR) + "/data/battery_profile.csv";
    SensorSimulator simulator(SensorSimulator::Mode::PROFILE_CSV, path);

    const auto first = simulator.next();
    const auto second = simulator.next();
    const auto third = simulator.next();

    EXPECT_FLOAT_EQ(first.voltage_v, 42.0f);
    EXPECT_FLOAT_EQ(second.voltage_v, 41.8f);
    EXPECT_FLOAT_EQ(third.voltage_v, 41.5f);
}

TEST(SensorSimulator, FailSafeDemoProducesSeparatedWarningAndCriticalTransitions) {
    const std::string path = std::string(ECU_SOURCE_DIR) + "/data/failsafe_demo.csv";
    SensorSimulator simulator(SensorSimulator::Mode::PROFILE_CSV, path);
    EkfSocEstimator estimator;
    FailSafeStateMachine failsafe;
    std::vector<std::pair<int, FailSafeEvent>> events;
    int cycle = 0;
    failsafe.setEventCallback([&](const FailSafeEvent& event) {
        events.emplace_back(cycle, event);
    });

    for (; cycle < 310; ++cycle) {
        const auto sample = simulator.next();
        const float soc = estimator.update(0.1f, sample.current_a, sample.voltage_v) * 100.0f;
        failsafe.evaluate(soc, sample.temperature_c);
    }

    ASSERT_EQ(events.size(), 2U);
    EXPECT_EQ(events[0].second.prev_state, 0U);
    EXPECT_EQ(events[0].second.new_state, 1U);
    EXPECT_EQ(events[0].second.reason, FailSafeStateMachine::REASON_LOW_SOC_WARNING);
    EXPECT_EQ(events[1].second.prev_state, 1U);
    EXPECT_EQ(events[1].second.new_state, 2U);
    EXPECT_EQ(events[1].second.reason, FailSafeStateMachine::REASON_LOW_SOC_CRITICAL);
    EXPECT_GE(events[1].first - events[0].first, 100);
}

TEST(SensorSimulator, RandomWalkStaysInExpectedRange) {
    SensorSimulator simulator(SensorSimulator::Mode::RANDOM_WALK);

    for (int i = 0; i < 100; ++i) {
        const auto data = simulator.next();
        EXPECT_GE(data.voltage_v, 30.0f);
        EXPECT_LE(data.voltage_v, 42.0f);
        EXPECT_GE(data.current_a, -10.0f);
        EXPECT_LE(data.current_a, 5.0f);
        EXPECT_GE(data.temperature_c, -10);
        EXPECT_LE(data.temperature_c, 70);
    }
}
