#pragma once

#include <cstdint>
#include <optional>
#include <random>
#include <string>
#include <vector>

struct SensorData {
    float voltage_v = 42.0f;
    float current_a = -2.0f;
    int8_t temperature_c = 25;
};

class SensorSimulator {
public:
    enum class Mode {
        CONSTANT,
        PROFILE_CSV,
        RANDOM_WALK,
        ADS1115_HARDWARE
    };

    // Virtual values used with ADS1115_HARDWARE: the potentiometer drives
    // only the pack voltage (D2=A, fixed so Fail-safe follows the knob alone).
    static constexpr float kHardwareCurrentA = -2.0f;
    static constexpr int8_t kHardwareTemperatureC = 25;

    // CLI names: constant, profile_csv, random_walk, ads1115. Unknown names
    // are rejected; callers must not substitute another mode.
    static std::optional<Mode> parseMode(const std::string& name);

    explicit SensorSimulator(Mode mode, std::string profile_path = {});

    SensorData next();
    // ADS1115_HARDWARE only: pack voltage from a validated, fresh conversion.
    void setHardwareVoltage(float pack_voltage_v);

private:
    void loadProfileIfNeeded();
    SensorData nextRandomWalk();

    Mode mode_;
    std::string profile_path_;
    std::vector<SensorData> profile_;
    std::size_t profile_index_ = 0;

    std::optional<float> hardware_voltage_v_;
    SensorData random_walk_state_{42.0f, -2.0f, 25};
    std::mt19937 rng_{12345};
};
