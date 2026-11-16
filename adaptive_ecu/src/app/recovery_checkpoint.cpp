#include "recovery_checkpoint.h"

#include <cmath>
#include <utility>

bool validCheckpointProtection(const RecoveryCheckpoint& cp){
    if(cp.version==1)return !cp.protection;
    return cp.version==2&&(!cp.protection||ProtectionHistory::matches(*cp.protection,cp.failsafe));
}

RecoveryCheckpoint captureCheckpoint(const EkfSocEstimator& ekf, const SohEstimator& soh,
    const FailSafeStateMachine& failsafe, SensorSimulator& sensor,
    double soh_elapsed_s, std::string input_identity, std::string soh_identity) {
    return {1, ekf.exportState(), soh.exportState(), failsafe.exportState(), sensor.exportState(),
            soh_elapsed_s, std::move(input_identity), std::move(soh_identity)};
}

bool restoreCheckpoint(const RecoveryCheckpoint& checkpoint,
    const std::string& expected_input_identity, const std::string& expected_soh_identity,
    EkfSocEstimator& ekf, SohEstimator& soh, FailSafeStateMachine& failsafe,
    SensorSimulator& sensor, double& soh_elapsed_s) {
    if (!validCheckpointProtection(checkpoint) || !std::isfinite(checkpoint.soh_elapsed_s) || checkpoint.soh_elapsed_s < 0 ||
        expected_input_identity.empty() || expected_soh_identity.empty() ||
        checkpoint.input_identity != expected_input_identity || checkpoint.soh_identity != expected_soh_identity)
        return false;
    auto next_ekf = ekf;
    auto next_soh = soh;
    auto next_failsafe = failsafe;
    auto next_sensor = sensor;
    if (!next_ekf.restoreState(checkpoint.ekf) || !next_soh.restoreState(checkpoint.soh) ||
        !next_failsafe.restoreState(checkpoint.failsafe) || !next_sensor.restoreState(checkpoint.sensor))
        return false;
    ekf = std::move(next_ekf);
    soh = std::move(next_soh);
    failsafe = std::move(next_failsafe);
    sensor = std::move(next_sensor);
    soh_elapsed_s = checkpoint.soh_elapsed_s;
    return true;
}
