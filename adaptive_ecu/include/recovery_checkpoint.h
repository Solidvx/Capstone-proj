#pragma once

#include "ekf_soc_estimator.h"
#include "soh_estimator.h"
#include "failsafe_sm.h"
#include "sensor_simulator.h"
#include "protection_history.h"

#include <string>

struct RecoveryCheckpoint {
    unsigned version = 0; // a default/partially read object must never restore
    EkfSocEstimator::Snapshot ekf{};
    SohEstimator::Snapshot soh{};
    FailSafeStateMachine::Snapshot failsafe{};
    SensorSimulator::Snapshot sensor{};
    double soh_elapsed_s = 0;
    std::string input_identity;
    std::string soh_identity;
    // Payload v1 has no event identity. v2 explicitly records either the
    // validated continuity snapshot or its absence; no security key/counter.
    std::optional<ProtectionHistory::Snapshot> protection;
};

bool validCheckpointProtection(const RecoveryCheckpoint& checkpoint);

RecoveryCheckpoint captureCheckpoint(const EkfSocEstimator& ekf, const SohEstimator& soh,
    const FailSafeStateMachine& failsafe, SensorSimulator& sensor,
    double soh_elapsed_s, std::string input_identity, std::string soh_identity);

// Validate in detached copies first: no partially restored SOC/SOH/FSM/source.
// Identities must be computed from the expected local config/input, not trusted
// from the saved file. No key/counter or ADC-ready state is stored here.
bool restoreCheckpoint(const RecoveryCheckpoint& checkpoint,
    const std::string& expected_input_identity, const std::string& expected_soh_identity,
    EkfSocEstimator& ekf, SohEstimator& soh, FailSafeStateMachine& failsafe,
    SensorSimulator& sensor, double& soh_elapsed_s);
