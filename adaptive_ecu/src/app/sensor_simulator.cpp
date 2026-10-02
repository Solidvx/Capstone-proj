#include "sensor_simulator.h"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace {
constexpr float kMinVoltage = 30.0f;
constexpr float kMaxVoltage = 42.0f;
constexpr float kMinCurrent = -10.0f;
constexpr float kMaxCurrent = 5.0f;
constexpr int kMinTemp = -10;
constexpr int kMaxTemp = 70;

int8_t clampTemp(float temperature_c) {
    const auto rounded = static_cast<int>(std::lround(temperature_c));
    return static_cast<int8_t>(std::clamp(rounded, kMinTemp, kMaxTemp));
}

SensorData parseCsvLine(const std::string& line) {
    std::stringstream stream(line);
    std::string item;
    std::vector<float> values;
    while (std::getline(stream, item, ',')) {
        values.push_back(std::stof(item));
    }
    if (values.size() < 3) {
        throw std::runtime_error("battery profile row must contain voltage,current,temperature");
    }
    return {values[0], values[1], clampTemp(values[2])};
}
}

std::optional<SensorSimulator::Mode> SensorSimulator::parseMode(const std::string& name) {
    if (name == "constant") return Mode::CONSTANT;
    if (name == "profile_csv") return Mode::PROFILE_CSV;
    if (name == "random_walk") return Mode::RANDOM_WALK;
    if (name == "ads1115") return Mode::ADS1115_HARDWARE;
    return std::nullopt;
}

SensorSimulator::SensorSimulator(Mode mode, std::string profile_path)
    : mode_(mode), profile_path_(std::move(profile_path)) {}

SensorData SensorSimulator::next() {
    switch (mode_) {
    case Mode::CONSTANT:
        return {42.0f, -2.0f, 25};
    case Mode::ADS1115_HARDWARE:
        if (!hardware_voltage_v_) {
            throw std::logic_error("ADS1115 mode has no validated ADC voltage");
        }
        return {*hardware_voltage_v_, kHardwareCurrentA, kHardwareTemperatureC};
    case Mode::PROFILE_CSV:
        loadProfileIfNeeded();
        if (profile_.empty()) {
            return {42.0f, -2.0f, 25};
        }
        if (profile_index_ < profile_.size() - 1) {
            return profile_[profile_index_++];
        }
        return profile_.back();
    case Mode::RANDOM_WALK:
        return nextRandomWalk();
    }
    return {42.0f, -2.0f, 25};
}

void SensorSimulator::setHardwareVoltage(float pack_voltage_v) {
    // Range is validated by convertAds1115Voltage; never clamp a real reading.
    hardware_voltage_v_ = pack_voltage_v;
}

void SensorSimulator::loadProfileIfNeeded() {
    if (!profile_.empty() || profile_path_.empty()) {
        return;
    }

    std::ifstream input(profile_path_);
    if (!input) {
        throw std::runtime_error("failed to open battery profile: " + profile_path_);
    }

    std::string line;
    while (std::getline(input, line)) {
        if (line.empty() || line[0] == '#') {
            continue;
        }
        if (line.find("voltage") != std::string::npos) {
            continue;
        }
        profile_.push_back(parseCsvLine(line));
    }
}

SensorData SensorSimulator::nextRandomWalk() {
    std::normal_distribution<float> voltage_delta(0.0f, 0.08f);
    std::normal_distribution<float> current_delta(0.0f, 0.25f);
    std::normal_distribution<float> temp_delta(0.0f, 0.20f);

    random_walk_state_.voltage_v =
        std::clamp(random_walk_state_.voltage_v + voltage_delta(rng_), kMinVoltage, kMaxVoltage);
    random_walk_state_.current_a =
        std::clamp(random_walk_state_.current_a + current_delta(rng_), kMinCurrent, kMaxCurrent);
    random_walk_state_.temperature_c =
        clampTemp(static_cast<float>(random_walk_state_.temperature_c) + temp_delta(rng_));

    return random_walk_state_;
}
