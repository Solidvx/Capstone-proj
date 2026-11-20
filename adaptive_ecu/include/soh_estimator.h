#pragma once
#include "virtual_battery.h"

class SohEstimator {
public:
    explicit SohEstimator(float initial_capacity_ah = kVirtualBatteryCapacityAh);

    void recordDischarge(float discharged_ah);
    void recordCycle(float measured_capacity_ah);
    float soh() const;
    float initialCapacityAh() const;
    float estimatedCapacityAh() const;

    struct Snapshot {
        unsigned version = 1;
        float initial_capacity_ah;
        float estimated_capacity_ah;
        float accumulated_discharge_ah;
    };
    Snapshot exportState() const;
    bool restoreState(const Snapshot& snapshot);

private:
    float initial_capacity_ah_ = kVirtualBatteryCapacityAh;
    float estimated_capacity_ah_ = kVirtualBatteryCapacityAh;
    float accumulated_discharge_ah_ = 0.0f;
};
