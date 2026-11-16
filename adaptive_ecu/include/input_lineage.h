#pragma once

#include "sensor_simulator.h"
#include "soh_capacity_scenario.h"

#include <string>

// Local log metadata only. Does not advance sources or change CAN/HAL contracts.
// Inputs must already be loaded/restored. UUID and intent are validated here.
std::string inputLineageJson(const std::string& instance_hex, const std::string& intent,
    SensorSimulator::Mode mode, const SensorSimulator& sensor,
    const SensorSimulator::Snapshot& state, const SohCapacityScenario& soh,
    double restored_soh_elapsed_s, const std::string& i2c_binding_sha256 = {});
