#include "sensor_simulator.h"

#include <gtest/gtest.h>

#include <stdexcept>
#include <string>

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
