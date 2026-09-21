#pragma once

class SohEstimator {
public:
    explicit SohEstimator(float initial_capacity_ah = 2.6f);

    void recordDischarge(float discharged_ah);
    void recordCycle(float measured_capacity_ah);
    float soh() const;
    float initialCapacityAh() const;
    float estimatedCapacityAh() const;

private:
    float initial_capacity_ah_ = 2.6f;
    float estimated_capacity_ah_ = 2.6f;
    float accumulated_discharge_ah_ = 0.0f;
};
