#include "ekf_soc_estimator.h"

#include <algorithm>

EkfSocEstimator::EkfSocEstimator() : EkfSocEstimator(Config{}) {}

EkfSocEstimator::EkfSocEstimator(const Config& config)
    : soc_(std::clamp(config.initial_soc, 0.0f, 1.0f)),
      covariance_(config.initial_covariance),
      capacity_ah_(config.capacity_ah),
      process_noise_(config.process_noise),
      measurement_noise_(config.measurement_noise) {}

float EkfSocEstimator::update(float dt_s, float current_a, float voltage_pack_v) {
    const float predicted_soc =
        std::clamp(soc_ + (current_a * dt_s) / (capacity_ah_ * 3600.0f), 0.0f, 1.0f);
    const float predicted_covariance = covariance_ + process_noise_;

    const float cell_v = voltage_pack_v / static_cast<float>(kCellsInSeries);
    const float h = dOcvDSoc(predicted_soc);
    const float innovation = cell_v - ocvFromSoc(predicted_soc);
    const float innovation_covariance = (h * predicted_covariance * h) + measurement_noise_;
    const float kalman_gain = predicted_covariance * h / innovation_covariance;

    soc_ = std::clamp(predicted_soc + kalman_gain * innovation, 0.0f, 1.0f);
    covariance_ = (1.0f - kalman_gain * h) * predicted_covariance;
    return soc_;
}

float EkfSocEstimator::soc() const {
    return soc_;
}

float EkfSocEstimator::ocvFromSoc(float soc) const {
    return ((kA3 * soc + kA2) * soc + kA1) * soc + kA0;
}

float EkfSocEstimator::dOcvDSoc(float soc) const {
    return (3.0f * kA3 * soc + 2.0f * kA2) * soc + kA1;
}
