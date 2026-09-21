#pragma once

class EkfSocEstimator {
public:
    struct Config {
        float initial_soc = 0.75f;
        float capacity_ah = 50.0f;
        float process_noise = 1.0e-5f;
        float measurement_noise = 0.02f;
        float initial_covariance = 0.01f;
    };

    EkfSocEstimator();
    explicit EkfSocEstimator(const Config& config);

    // Receives pack voltage; conversion to cell voltage occurs internally once.
    float update(float dt_s, float current_a, float voltage_pack_v);
    float soc() const;

private:
    static constexpr int kCellsInSeries = 10;
    static constexpr float kA3 = 2.1667f;
    static constexpr float kA2 = -3.7321f;
    static constexpr float kA1 = 2.7655f;
    static constexpr float kA0 = 3.0f;
    float ocvFromSoc(float soc) const;
    float dOcvDSoc(float soc) const;

    float soc_ = 0.75f;
    float covariance_ = 0.01f;
    float capacity_ah_ = 50.0f;
    float process_noise_ = 1.0e-5f;
    float measurement_noise_ = 0.02f;
};
