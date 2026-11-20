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
    if (!std::isfinite(temperature_c)) throw std::invalid_argument("nonfinite profile temperature");
    // Bound before rounding to avoid overflowing an integer for a finite CSV value.
    if (temperature_c<=kMinTemp) return kMinTemp;
    if (temperature_c>=kMaxTemp) return kMaxTemp;
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
    if (!std::isfinite(values[0]) || !std::isfinite(values[1]))
        throw std::invalid_argument("nonfinite profile voltage/current");
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
    // Range and endpoint tolerance belong to convertAds1115Voltage; no clamp here.
    hardware_voltage_v_ = pack_voltage_v;
}

SensorSimulator::Snapshot SensorSimulator::exportState() {
    if (mode_ == Mode::PROFILE_CSV) loadProfileIfNeeded();
    return {1, mode_, profile_index_, profile_.size(), random_walk_state_, rng_};
}

bool SensorSimulator::restoreState(const Snapshot& snapshot) {
    const auto& walk = snapshot.random_walk_state;
    if (snapshot.version != 1 || snapshot.mode != mode_ ||
        !std::isfinite(walk.voltage_v) || walk.voltage_v < kMinVoltage || walk.voltage_v > kMaxVoltage ||
        !std::isfinite(walk.current_a) || walk.current_a < kMinCurrent || walk.current_a > kMaxCurrent ||
        walk.temperature_c < kMinTemp || walk.temperature_c > kMaxTemp) return false;
    auto next_profile = profile_;
    auto next_input = profile_input_;
    if (mode_ == Mode::PROFILE_CSV) {
        if (next_profile.empty()) {
            SensorSimulator loader(mode_, profile_path_);
            try { loader.loadProfileIfNeeded(); } catch (const std::exception&) { return false; }
            next_profile = std::move(loader.profile_);
            next_input = std::move(loader.profile_input_);
        }
        if (next_profile.empty() || snapshot.profile_size != next_profile.size() ||
            snapshot.profile_index >= next_profile.size()) return false;
    } else if (snapshot.profile_index != 0 || snapshot.profile_size != 0) {
        return false;
    }
    profile_ = std::move(next_profile);
    profile_input_ = std::move(next_input);
    profile_index_ = snapshot.profile_index;
    random_walk_state_ = walk;
    rng_ = snapshot.rng;
    // Old ADC readiness/quality is not a fresh conversion after restart.
    hardware_voltage_v_.reset();
    return true;
}

void SensorSimulator::loadProfileIfNeeded() {
    if (profile_input_ || profile_path_.empty()) {
        return;
    }

    std::ifstream input(profile_path_,std::ios::binary);
    if (!input) {
        throw std::runtime_error("failed to open battery profile: " + profile_path_);
    }

    const auto captured=captureInput(input,"sensor-v1:profile_csv:");
    std::istringstream parser(captured.content);
    std::vector<SensorData> loaded;
    std::string line;
    while (std::getline(parser, line)) {
        if (line.empty() || line[0] == '#') {
            continue;
        }
        if (line.find("voltage") != std::string::npos) {
            continue;
        }
        loaded.push_back(parseCsvLine(line));
    }
    profile_=std::move(loaded);
    profile_input_=captured.fingerprint;
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
