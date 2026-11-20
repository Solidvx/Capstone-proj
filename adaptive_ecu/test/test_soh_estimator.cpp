#include "soh_estimator.h"

#include <gtest/gtest.h>

#include "soh_capacity_scenario.h"
#include "ekf_soc_estimator.h"
#include "bms_middleware.h"
#include "mock_can_driver.h"
#include "vehicle_data_service.h"

#include <limits>
#include <sstream>

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

namespace {
SohCapacityScenario scenario(const std::string& contents) {
    std::istringstream input(contents);
    return SohCapacityScenario::fromCsv(input);
}
}

TEST(SohScenario, SharedNominalCapacityAndFullHealthDefault) {
    SohEstimator estimator;
    EXPECT_FLOAT_EQ(estimator.initialCapacityAh(), EkfSocEstimator::Config{}.capacity_ah);
    EXPECT_FLOAT_EQ(estimator.initialCapacityAh(), 50.0f);
    SohCapacityScenario full;
    EXPECT_FLOAT_EQ(full.capacityAt(0), 50);
    EXPECT_FLOAT_EQ(full.capacityAt(100000), 50);
    estimator.recordCycle(45);
    EXPECT_NEAR(estimator.soh() * 100, 90, .01);
    estimator.recordDischarge(5); // discharge throughput is not capacity degradation
    EXPECT_NEAR(estimator.soh() * 100, 90, .01);
}

TEST(SohScenario, StepsAtBoundaryHoldsLastAndRestartsAtZero) {
    const auto s = scenario("elapsed_s,estimated_capacity_ah\r\n0,50\r\n10,47.5\r\n20,45\r\n");
    EXPECT_FLOAT_EQ(s.capacityAt(0), 50);
    EXPECT_FLOAT_EQ(s.capacityAt(9.999), 50);
    EXPECT_FLOAT_EQ(s.capacityAt(10), 47.5);
    EXPECT_FLOAT_EQ(s.capacityAt(19.999), 47.5);
    EXPECT_FLOAT_EQ(s.capacityAt(20), 45);
    EXPECT_FLOAT_EQ(s.capacityAt(10000), 45);
    EXPECT_FLOAT_EQ(s.capacityAt(0), 50); // no hidden cursor, deterministic replay
    EXPECT_THROW(s.capacityAt(-1), std::invalid_argument);
    EXPECT_THROW(s.capacityAt(std::numeric_limits<double>::quiet_NaN()), std::invalid_argument);
}

TEST(SohScenario, FingerprintAttestsParsedBytesAndLegacyRecoveryPrefixWithoutAdvancing) {
    const std::string contents="elapsed_s,estimated_capacity_ah\r\n0,50\r\n10,45\r\n";
    const auto s=scenario(contents);
    ASSERT_TRUE(s.inputFingerprint());
    EXPECT_EQ(s.inputFingerprint()->bytes,contents.size());
    EXPECT_EQ(s.inputFingerprint()->sha256,inputSha256(contents));
    EXPECT_EQ(s.inputFingerprint()->recovery_identity,inputSha256("soh-v1:50Ah:"+contents));
    EXPECT_FLOAT_EQ(s.capacityAt(10),45);
    EXPECT_FLOAT_EQ(s.capacityAt(0),50);
    EXPECT_FALSE(SohCapacityScenario{}.inputFingerprint());
}

TEST(SohScenario, RejectsInvalidInputRatherThanClampingToHealthy) {
    const std::string header="elapsed_s,estimated_capacity_ah\n";
    for (const std::string body : {"", "1,45\n", "-1,45\n", "0,0\n", "0,-5\n",
            "0,51\n", "0,nan\n", "0,inf\n", "nan,45\n", "0,45extra\n",
            "0,45,1\n", "0\n", "0,50\n0,45\n", "0,50\n-1,45\n",
            "0,50\n10,45\n9,40\n", "0,1e-100\n"}) {
        EXPECT_THROW(scenario(header+body), std::invalid_argument) << body;
    }
    EXPECT_THROW(scenario("time,capacity\n0,45\n"), std::invalid_argument);
    EXPECT_THROW(SohCapacityScenario::fromFile("/nonexistent/soh-capacity-test.csv"), std::invalid_argument);
}

TEST(SohScenario, DemoFileTravelsThroughProductMiddlewareAndAuthenticatedIviService) {
    const auto profile = SohCapacityScenario::fromFile(std::string(ECU_SOURCE_DIR)+"/data/soh_demo.csv");
    SohEstimator estimator;
    MockCanDriver driver;
    ASSERT_TRUE(driver.open("mock"));
    std::array<uint8_t, 32> dummy_key{};
    dummy_key.fill(1); // explicit test key, never a device key
    SecOcModule signer;
    signer.setKey(dummy_key);
    BmsMiddleware middleware(driver, signer, true);
    ivi::VehicleDataService service(dummy_key);
    const auto base = ivi::VehicleDataService::Clock::now();
    const double times[]{0, 9.999, 10, 19.999, 20, 100};
    const double expected[]{100, 100, 95, 95, 90, 90};
    for (std::size_t i=0; i<6; ++i) {
        estimator.recordCycle(profile.capacityAt(times[i]));
        driver.clear();
        middleware.publishBms({75, estimator.soh()*100, 36, -2, 25});
        const auto frames=driver.sentFrames();
        ASSERT_EQ(frames.size(), 2U);
        EXPECT_EQ(frames[0].data[1], static_cast<uint8_t>(expected[i]*2));
        const auto now=base+std::chrono::milliseconds(static_cast<int>(times[i]*1000));
        EXPECT_EQ(service.processFrame(frames[0].id, frames[0].data, now),
                  ivi::ProcessResult::kPendingAuthentication);
        // The raw update alone must not publish a changed SOH.
        if (i>0) EXPECT_DOUBLE_EQ(service.latest().vehicle.soh_percent, expected[i-1]);
        EXPECT_EQ(service.processFrame(frames[1].id, frames[1].data, now+std::chrono::milliseconds(1)),
                  ivi::ProcessResult::kPublished);
        EXPECT_TRUE(service.latest().vehicle.valid);
        EXPECT_DOUBLE_EQ(service.latest().vehicle.soh_percent, expected[i]);
        EXPECT_DOUBLE_EQ(service.latest().vehicle.soc_percent, 75);
        EXPECT_DOUBLE_EQ(service.latest().vehicle.current_a, -2);
    }
}

TEST(SohEstimator, SnapshotPreservesCapacityAndDischargeWithoutInventingDegradation) {
    SohEstimator original;
    original.recordCycle(45);
    original.recordDischarge(7.5f);
    auto saved=original.exportState();
    SohEstimator recovered;
    ASSERT_TRUE(recovered.restoreState(saved));
    EXPECT_FLOAT_EQ(recovered.estimatedCapacityAh(),45);
    EXPECT_FLOAT_EQ(recovered.exportState().accumulated_discharge_ah,7.5f);
    recovered.recordDischarge(.5f);
    EXPECT_FLOAT_EQ(recovered.exportState().accumulated_discharge_ah,8.0f);
    EXPECT_NEAR(recovered.soh()*100,90,.01);
    for(int i=0;i<6;++i) {
        auto bad=saved;
        switch(i) {
        case 0: bad.version=3; break;
        case 1: bad.initial_capacity_ah=2.6f; break;
        case 2: bad.estimated_capacity_ah=51; break;
        case 3: bad.estimated_capacity_ah=std::numeric_limits<float>::quiet_NaN(); break;
        case 4: bad.accumulated_discharge_ah=-1; break;
        case 5: bad.accumulated_discharge_ah=std::numeric_limits<float>::infinity(); break;
        }
        EXPECT_FALSE(recovered.restoreState(bad));
        EXPECT_FLOAT_EQ(recovered.exportState().accumulated_discharge_ah,8.0f);
        EXPECT_FLOAT_EQ(recovered.estimatedCapacityAh(),45);
    }
}
