#pragma once

#include <cstdint>
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
        POTENTIOMETER,
        PROFILE_CSV,
        RANDOM_WALK,
        ADS1115_HARDWARE
    };

    explicit SensorSimulator(Mode mode, std::string profile_path = {});

    SensorData next();
    void setAdcVoltage(float voltage_v);
    void setAdcCurrent(float current_a);
    void setAdcTemperature(float temperature_c);

private:
    void loadProfileIfNeeded();
    SensorData nextRandomWalk();

    Mode mode_;
    std::string profile_path_;
    std::vector<SensorData> profile_;
    std::size_t profile_index_ = 0;

    SensorData adc_data_{42.0f, -2.0f, 25};
    SensorData random_walk_state_{42.0f, -2.0f, 25};
    std::mt19937 rng_{12345};
};
