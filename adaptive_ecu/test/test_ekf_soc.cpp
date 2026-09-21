#include "ekf_soc_estimator.h"

#include <gtest/gtest.h>
#include <algorithm>
#include <cmath>
#include <iostream>
#include <iomanip>
#include <limits>

namespace {
double packOcv(double soc) {
    return 10.0 * (((2.1667 * soc - 3.7321) * soc + 2.7655) * soc + 3.0);
}
}

TEST(EkfSocEstimator, MaintainsSocWhenVoltageMatchesModel) {
    EkfSocEstimator estimator;

    for (int i = 0; i < 20; ++i) {
        estimator.update(0.1f, 0.0f, static_cast<float>(packOcv(0.75)));
    }

    EXPECT_NEAR(estimator.soc(), 0.75f, 1e-5f);
}

TEST(EkfSocEstimator, TracksHigherVoltageUpward) {
    EkfSocEstimator estimator;

    for (int i = 0; i < 80; ++i) {
        estimator.update(0.1f, 0.0f, static_cast<float>(packOcv(0.95)));
    }

    EXPECT_GT(estimator.soc(), 0.80f);
}

TEST(EkfSocEstimator, DischargeCurrentReducesPrediction) {
    EkfSocEstimator::Config config;
    config.initial_soc = 0.50f;
    config.measurement_noise = 100.0f;
    EkfSocEstimator estimator(config);

    estimator.update(60.0f, -5.0f, static_cast<float>(packOcv(0.50)));

    EXPECT_LT(estimator.soc(), 0.50f);
    EXPECT_NEAR(estimator.soc(), 0.50f - 300.0f / 180000.0f, 1e-5f);
}

TEST(EkfSocEstimator, MaintainsLowAndHighSocWithPackInput) {
    for (float initial : {0.05f, 0.95f}) {
        EkfSocEstimator::Config config;
        config.initial_soc = initial;
        EkfSocEstimator estimator(config);
        for (int k = 0; k < 100; ++k) {
            estimator.update(0.1f, 0.0f, static_cast<float>(packOcv(initial)));
        }
        EXPECT_NEAR(estimator.soc(), initial, 1e-5f);
    }
}

TEST(EkfSocEstimator, S21SyntheticScenarios) {
    // Frozen S-21 inputs; truth is never passed to the estimator.
    const double scenarios[][2] = {{0, 0}, {0.1, 0}, {-0.1, 0},
        {0.1, 0.01}, {0.1, -0.01}, {-0.1, 0.01}, {-0.1, -0.01}};
    for (const auto& scenario : scenarios) {
        EkfSocEstimator::Config config;
        config.initial_soc = 0.8f;
        config.capacity_ah = 50.0f;
        EkfSocEstimator estimator(config);
        double cc = config.initial_soc;
        double sum_ekf = 0, sum_cc = 0, max_ekf = 0, max_cc = 0;
        for (int k = 1; k <= 36000; ++k) {
            const double truth = 0.8 - 2.0 * (k * 0.1) / 180000.0;
            const float current = static_cast<float>(-2.0 + scenario[0]);
            const float voltage = static_cast<float>(packOcv(truth) + 10.0 * scenario[1]);
            const float estimate = estimator.update(0.1f, current, voltage);
            // Same quantized current, timestep and initial SOC as the product.
            cc += static_cast<double>(current) * static_cast<double>(0.1f) / 180000.0;
            ASSERT_TRUE(std::isfinite(estimate));
            ASSERT_GE(estimate, 0.0f);
            ASSERT_LE(estimate, 1.0f);
            const double e = 100.0 * (estimate - truth);
            const double c = 100.0 * (cc - truth);
            sum_ekf += e * e;
            sum_cc += c * c;
            max_ekf = std::max(max_ekf, std::abs(e));
            max_cc = std::max(max_cc, std::abs(c));
        }
        const double rmse_ekf = std::sqrt(sum_ekf / 36000);
        const double rmse_cc = std::sqrt(sum_cc / 36000);
        ASSERT_TRUE(std::isfinite(rmse_cc));
        ASSERT_TRUE(std::isfinite(rmse_ekf));
        std::cout << std::setprecision(12)
                  << "S21 I_bias=" << scenario[0] << " cell_V_bias=" << scenario[1]
                  << " EKF_RMSE_pp=" << rmse_ekf << " CC_RMSE_pp=" << rmse_cc
                  << " EKF_max_pp=" << max_ekf << " CC_max_pp=" << max_cc << '\n';
        if (scenario[0] != 0 && scenario[1] == 0) {
            EXPECT_LT(rmse_ekf, rmse_cc);
        }
        if (scenario[0] == 0 && scenario[1] == 0) {
            // Numerical regression guard in percentage points, not a hardware
            // accuracy requirement: accumulated float roundoff scale.
            const double roundoff_guard_pp =
                100.0 * 36000 * std::numeric_limits<float>::epsilon();
            EXPECT_LT(max_ekf, roundoff_guard_pp);
            EXPECT_LT(max_cc, roundoff_guard_pp);
        }
        // Voltage-bias cases are reported, never required to outperform CC.
    }
}

TEST(EkfSocEstimator, CorrectionUsesSocDependentJacobian) {
    for (float initial : {0.05f, 0.60f, 0.95f}) {
        EkfSocEstimator::Config config;
        config.initial_soc = initial;
        EkfSocEstimator estimator(config);
        const float pack_voltage = static_cast<float>(packOcv(initial) + 0.1);
        const double s = initial;
        // Independent double-precision single-step reference; I=0.
        const double h = 6.5001 * s * s - 7.4642 * s + 2.7655;
        const double p = static_cast<double>(config.initial_covariance) + config.process_noise;
        const double gain = p * h / (h * h * p + config.measurement_noise);
        const double expected = s + gain * (static_cast<double>(pack_voltage) / 10 - packOcv(s) / 10);
        EXPECT_NEAR(estimator.update(0.1f, 0.0f, pack_voltage), expected, 1e-5);
    }
}
