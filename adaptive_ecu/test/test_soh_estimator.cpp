#include "soh_estimator.h"

#include <gtest/gtest.h>

TEST(SohEstimator, StartsAtFullHealth) {
    SohEstimator estimator(2.6f);

    EXPECT_FLOAT_EQ(estimator.soh(), 1.0f);
    EXPECT_FLOAT_EQ(estimator.initialCapacityAh(), 2.6f);
}

TEST(SohEstimator, UsesMeasuredCapacityRatio) {
    SohEstimator estimator(2.6f);

    estimator.recordCycle(2.34f);

    EXPECT_NEAR(estimator.soh(), 0.90f, 0.001f);
    EXPECT_NEAR(estimator.estimatedCapacityAh(), 2.34f, 0.001f);
}

TEST(SohEstimator, ClampsCapacityAboveInitial) {
    SohEstimator estimator(2.6f);

    estimator.recordCycle(3.0f);

    EXPECT_FLOAT_EQ(estimator.soh(), 1.0f);
}
