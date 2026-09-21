#include "soh_estimator.h"

#include <algorithm>

SohEstimator::SohEstimator(float initial_capacity_ah)
    : initial_capacity_ah_(std::max(initial_capacity_ah, 0.1f)),
      estimated_capacity_ah_(initial_capacity_ah_) {}

void SohEstimator::recordDischarge(float discharged_ah) {
    if (discharged_ah > 0.0f) {
        accumulated_discharge_ah_ += discharged_ah;
    }
}

void SohEstimator::recordCycle(float measured_capacity_ah) {
    if (measured_capacity_ah <= 0.0f) {
        return;
    }

    estimated_capacity_ah_ =
        std::clamp(measured_capacity_ah, 0.0f, initial_capacity_ah_);
}

float SohEstimator::soh() const {
    return std::clamp(estimated_capacity_ah_ / initial_capacity_ah_, 0.0f, 1.0f);
}

float SohEstimator::initialCapacityAh() const {
    return initial_capacity_ah_;
}

float SohEstimator::estimatedCapacityAh() const {
    return estimated_capacity_ah_;
}
