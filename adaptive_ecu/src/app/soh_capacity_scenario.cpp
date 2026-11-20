#include "soh_capacity_scenario.h"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iterator>
#include <stdexcept>
#include <sstream>

namespace {
std::string trim(const std::string& value) {
    const auto start = value.find_first_not_of(" \t\r\n");
    if (start == std::string::npos) return {};
    return value.substr(start, value.find_last_not_of(" \t\r\n") - start + 1);
}

double number(const std::string& text) {
    const auto value = trim(text);
    std::size_t consumed = 0;
    const double result = std::stod(value, &consumed);
    if (consumed != value.size() || !std::isfinite(result)) {
        throw std::invalid_argument("expected a finite number");
    }
    return result;
}
}

SohCapacityScenario SohCapacityScenario::fromCsv(std::istream& input) {
    const auto captured=captureInput(input,"soh-v1:50Ah:");
    std::istringstream parser(captured.content);
    SohCapacityScenario scenario;
    scenario.steps_.clear();
    std::string line;
    if (!std::getline(parser, line) || trim(line) != "elapsed_s,estimated_capacity_ah") {
        throw std::invalid_argument("SOH CSV header must be elapsed_s,estimated_capacity_ah");
    }
    std::size_t line_number = 1;
    while (std::getline(parser, line)) {
        ++line_number;
        line = trim(line);
        if (line.empty()) continue;
        try {
            const auto comma = line.find(',');
            if (comma == std::string::npos || line.find(',', comma + 1) != std::string::npos) {
                throw std::invalid_argument("expected two columns");
            }
            const double time = number(line.substr(0, comma));
            const double capacity = number(line.substr(comma + 1));
            if (time < 0 || capacity <= 0 || capacity > kVirtualBatteryCapacityAh ||
                static_cast<float>(capacity) <= 0 ||
                (scenario.steps_.empty() ? time != 0 : time <= scenario.steps_.back().first)) {
                throw std::invalid_argument("first time must be zero, times strictly increasing; capacity in (0,50] Ah");
            }
            scenario.steps_.emplace_back(time, static_cast<float>(capacity));
        } catch (const std::exception& error) {
            throw std::invalid_argument("SOH CSV line " + std::to_string(line_number) + ": " + error.what());
        }
    }
    if (parser.bad() || scenario.steps_.empty()) throw std::invalid_argument("SOH CSV unreadable or empty");
    scenario.input_=captured.fingerprint;
    return scenario;
}

SohCapacityScenario SohCapacityScenario::fromFile(const std::string& path) {
    std::ifstream input(path,std::ios::binary);
    if (!input) throw std::invalid_argument("cannot open SOH CSV: " + path);
    return fromCsv(input);
}

float SohCapacityScenario::capacityAt(double elapsed_s) const {
    if (!std::isfinite(elapsed_s) || elapsed_s < 0) throw std::invalid_argument("invalid SOH elapsed time");
    auto step = std::upper_bound(steps_.begin(), steps_.end(), elapsed_s,
        [](double time, const auto& item) { return time < item.first; });
    return std::prev(step)->second;
}
