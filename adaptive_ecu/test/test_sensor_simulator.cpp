#include "sensor_simulator.h"

#include <gtest/gtest.h>

#include <string>

TEST(SensorSimulator, ConstantModeReturnsNominalData) {
    SensorSimulator simulator(SensorSimulator::Mode::CONSTANT);
    const auto data = simulator.next();

    EXPECT_FLOAT_EQ(data.voltage_v, 42.0f);
    EXPECT_FLOAT_EQ(data.current_a, -2.0f);
    EXPECT_EQ(data.temperature_c, 25);
}

TEST(SensorSimulator, PotentiometerModeReturnsClampedAdcData) {
    SensorSimulator simulator(SensorSimulator::Mode::POTENTIOMETER);
    simulator.setAdcVoltage(45.0f);
    simulator.setAdcCurrent(-20.0f);
    simulator.setAdcTemperature(80.0f);

    const auto data = simulator.next();

    EXPECT_FLOAT_EQ(data.voltage_v, 42.0f);
    EXPECT_FLOAT_EQ(data.current_a, -10.0f);
    EXPECT_EQ(data.temperature_c, 70);
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
