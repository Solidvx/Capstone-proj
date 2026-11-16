#pragma once

#include "ekf_soc_estimator.h"
#include "sensor_simulator.h"
#include "soh_estimator.h"
#include "task_recovery.h"

#include <condition_variable>
#include <functional>
#include <mutex>
#include <optional>
#include <thread>

// Detached copies: the owner commits a completed result only after generation
// and input-age checks. A stopped/failed worker never mutates live BMS state.
struct BmsCalculation {
    SensorSimulator sensor;
    EkfSocEstimator ekf;
    SohEstimator soh;
    float capacity_ah;
    std::uint64_t sampled_at_ms;
    SensorData sample{};
    float soc_percent = 0;
    float soh_percent = 0;
    std::uint64_t generation = 0;
};

void calculateBms(BmsCalculation& work);

class BmsCalculationTask final : public RecoverableTask {
public:
    using Calculation = std::function<void(BmsCalculation&)>;
    explicit BmsCalculationTask(Calculation calculation = calculateBms);
    ~BmsCalculationTask();
    BmsCalculationTask(const BmsCalculationTask&) = delete;
    BmsCalculationTask& operator=(const BmsCalculationTask&) = delete;

    // The owner confirms the committed snapshot, not the in-flight calculation.
    void checkpointCommitted(std::uint64_t now_ms);
    bool submit(BmsCalculation work);
    std::optional<BmsCalculation> takeCompleted();
    bool faulted() const;

    void requestStop() override;
    bool joinIfStopped() override;
    bool snapshotValid(std::uint64_t now_ms, std::uint64_t max_age_ms) override;
    bool startFromSnapshot(std::uint64_t generation) override;
    bool completedWork(std::uint64_t generation) override;

private:
    void loop();
    Calculation calculation_;
    mutable std::mutex mutex_;
    std::condition_variable wake_;
    std::thread thread_;
    std::optional<BmsCalculation> pending_, completed_;
    std::optional<std::uint64_t> committed_at_, completed_generation_;
    std::uint64_t generation_ = 0;
    bool stopping_ = true;
    bool stopped_ = true;
    bool busy_ = false;
    bool faulted_ = false;
};
