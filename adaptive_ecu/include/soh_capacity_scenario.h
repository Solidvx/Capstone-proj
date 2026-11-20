#pragma once

#include "virtual_battery.h"
#include "input_source.h"

#include <istream>
#include <optional>
#include <string>
#include <utility>
#include <vector>

// Stepwise virtual capacity, independent of voltage/current sensor profiles.
// Time is process-relative monotonic elapsed seconds. No repeat or interpolation.
class SohCapacityScenario {
public:
    SohCapacityScenario() = default;
    static SohCapacityScenario fromCsv(std::istream& input);
    static SohCapacityScenario fromFile(const std::string& path);
    float capacityAt(double elapsed_s) const;
    std::size_t size() const { return steps_.size(); }
    const std::optional<InputFingerprint>& inputFingerprint() const { return input_; }

private:
    std::vector<std::pair<double, float>> steps_{{0.0, kVirtualBatteryCapacityAh}};
    std::optional<InputFingerprint> input_;
};
