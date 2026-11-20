#include "sensor_simulator.h"
#include "ekf_soc_estimator.h"
#include "failsafe_sm.h"
#include "input_lineage.h"

#include <gtest/gtest.h>

#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
#include <fstream>
#include <filesystem>
#include <sstream>
#include <limits>
#include <chrono>
#include <iostream>

TEST(SensorSimulator, ConstantModeReturnsNominalData) {
    SensorSimulator simulator(SensorSimulator::Mode::CONSTANT);
    const auto data = simulator.next();

    EXPECT_FLOAT_EQ(data.voltage_v, 42.0f);
    EXPECT_FLOAT_EQ(data.current_a, -2.0f);
    EXPECT_EQ(data.temperature_c, 25);
}

// Replaces the removed POTENTIOMETER clamp test (I-5=B). Real ADC readings are
// range-checked and rejected by convertAds1115Voltage, never clamped here.
TEST(SensorSimulator, Ads1115ModeUsesValidatedVoltageWithVirtualCurrentAndTemperature) {
    SensorSimulator simulator(SensorSimulator::Mode::ADS1115_HARDWARE);
    EXPECT_THROW(simulator.next(), std::logic_error);

    simulator.setHardwareVoltage(36.0f);
    const auto data = simulator.next();

    EXPECT_FLOAT_EQ(data.voltage_v, 36.0f);
    EXPECT_FLOAT_EQ(data.current_a, SensorSimulator::kHardwareCurrentA);
    EXPECT_EQ(data.temperature_c, SensorSimulator::kHardwareTemperatureC);
}

TEST(SensorSimulator, ParseModeAcceptsOnlyOfficialNames) {
    EXPECT_EQ(SensorSimulator::parseMode("constant"), SensorSimulator::Mode::CONSTANT);
    EXPECT_EQ(SensorSimulator::parseMode("profile_csv"), SensorSimulator::Mode::PROFILE_CSV);
    EXPECT_EQ(SensorSimulator::parseMode("random_walk"), SensorSimulator::Mode::RANDOM_WALK);
    EXPECT_EQ(SensorSimulator::parseMode("ads1115"), SensorSimulator::Mode::ADS1115_HARDWARE);
    EXPECT_FALSE(SensorSimulator::parseMode("potentiometer").has_value());
    EXPECT_FALSE(SensorSimulator::parseMode("").has_value());
    EXPECT_FALSE(SensorSimulator::parseMode("ADS1115").has_value());
}

TEST(SensorSimulator, ProfileCsvReturnsRowsThenHoldsLast) {
    const std::string path = std::string(ECU_SOURCE_DIR) + "/data/battery_profile.csv";
    SensorSimulator simulator(SensorSimulator::Mode::PROFILE_CSV, path);

    const auto first = simulator.next();
    const auto second = simulator.next();
    const auto third = simulator.next();

    EXPECT_FLOAT_EQ(first.voltage_v, 42.0f);
    EXPECT_FLOAT_EQ(second.voltage_v, 41.8f);
    EXPECT_FLOAT_EQ(third.voltage_v, 41.5f);
}

TEST(SensorSimulator, FailSafeDemoProducesSeparatedWarningAndCriticalTransitions) {
    const std::string path = std::string(ECU_SOURCE_DIR) + "/data/failsafe_demo.csv";
    SensorSimulator simulator(SensorSimulator::Mode::PROFILE_CSV, path);
    EkfSocEstimator estimator;
    FailSafeStateMachine failsafe;
    std::vector<std::pair<int, FailSafeEvent>> events;
    int cycle = 0;
    failsafe.setEventCallback([&](const FailSafeEvent& event) {
        events.emplace_back(cycle, event);
    });

    for (; cycle < 310; ++cycle) {
        const auto sample = simulator.next();
        const float soc = estimator.update(0.1f, sample.current_a, sample.voltage_v) * 100.0f;
        failsafe.evaluate(soc, sample.temperature_c);
    }

    ASSERT_EQ(events.size(), 2U);
    EXPECT_EQ(events[0].second.prev_state, 0U);
    EXPECT_EQ(events[0].second.new_state, 1U);
    EXPECT_EQ(events[0].second.reason, FailSafeStateMachine::REASON_LOW_SOC_WARNING);
    EXPECT_EQ(events[1].second.prev_state, 1U);
    EXPECT_EQ(events[1].second.new_state, 2U);
    EXPECT_EQ(events[1].second.reason, FailSafeStateMachine::REASON_LOW_SOC_CRITICAL);
    EXPECT_GE(events[1].first - events[0].first, 100);
}

TEST(SensorSimulator, RandomWalkStaysInExpectedRange) {
    SensorSimulator simulator(SensorSimulator::Mode::RANDOM_WALK);

    for (int i = 0; i < 100; ++i) {
        const auto data = simulator.next();
        EXPECT_GE(data.voltage_v, 30.0f);
        EXPECT_LE(data.voltage_v, 42.0f);
        EXPECT_GE(data.current_a, -10.0f);
        EXPECT_LE(data.current_a, 5.0f);
        EXPECT_GE(data.temperature_c, -10);
        EXPECT_LE(data.temperature_c, 70);
    }
}

TEST(SensorSimulator, RestoresCompleteRandomGeneratorAndWalkState) {
    SensorSimulator source(SensorSimulator::Mode::RANDOM_WALK);
    for(int i=0;i<37;++i) source.next();
    const auto saved=source.exportState();
    SensorSimulator recovered(SensorSimulator::Mode::RANDOM_WALK);
    ASSERT_TRUE(recovered.restoreState(saved));
    for(int i=0;i<100;++i) {
        const auto a=source.next(),b=recovered.next();
        EXPECT_FLOAT_EQ(a.voltage_v,b.voltage_v);
        EXPECT_FLOAT_EQ(a.current_a,b.current_a);
        EXPECT_EQ(a.temperature_c,b.temperature_c);
    }
    auto bad=saved;bad.profile_index=1;
    const auto before=recovered.exportState();
    EXPECT_FALSE(recovered.restoreState(bad));
    EXPECT_EQ(recovered.exportState().rng,before.rng);
}

TEST(SensorSimulator, RestoresCsvPositionAndRequiresNewAdcInput) {
    const std::string path=std::string(ECU_SOURCE_DIR)+"/data/battery_profile.csv";
    SensorSimulator source(SensorSimulator::Mode::PROFILE_CSV,path);
    source.next();source.next();
    const auto saved=source.exportState();
    SensorSimulator recovered(SensorSimulator::Mode::PROFILE_CSV,path);
    ASSERT_TRUE(recovered.restoreState(saved));
    EXPECT_FLOAT_EQ(source.next().voltage_v,recovered.next().voltage_v);
    auto bad=saved;bad.profile_index=bad.profile_size;
    EXPECT_FALSE(recovered.restoreState(bad));
    SensorSimulator wrong(SensorSimulator::Mode::PROFILE_CSV,"/nonexistent/recovery-source.csv");
    EXPECT_FALSE(wrong.restoreState(saved));
    SensorSimulator adc(SensorSimulator::Mode::ADS1115_HARDWARE);
    adc.setHardwareVoltage(36);
    const auto adc_saved=adc.exportState();
    ASSERT_TRUE(adc.restoreState(adc_saved));
    EXPECT_THROW(adc.next(),std::logic_error);
    adc.setHardwareVoltage(37);
    EXPECT_FLOAT_EQ(adc.next().voltage_v,37);
}

namespace {
struct LineageProfile {
    std::filesystem::path directory=std::filesystem::temp_directory_path()/
        ("capstone-input-"+inputSha256(std::to_string(std::chrono::steady_clock::now().time_since_epoch().count())).substr(0,16));
    std::filesystem::path path=directory/"profile.csv";
    LineageProfile(){std::filesystem::create_directory(directory);}
    ~LineageProfile(){std::error_code error;std::filesystem::remove_all(directory,error);}
    void write(const std::string& content){std::ofstream out(path,std::ios::binary);out<<content;}
};
}

TEST(InputLineage, HashesExactlyParsedBytesAndPreservesLegacyRecoveryIdentity) {
    LineageProfile file;
    const std::string content="# recorded input\r\nvoltage,current,temperature\r\n36,-2,25.5\r\n35,-1,80\r\n";
    file.write(content);
    SensorSimulator source(SensorSimulator::Mode::PROFILE_CSV,file.path.string());
    const auto state=source.exportState();
    ASSERT_TRUE(source.profileInput());
    EXPECT_EQ(source.profileInput()->bytes,content.size());
    EXPECT_EQ(source.profileInput()->sha256,inputSha256(content));
    EXPECT_EQ(source.profileInput()->recovery_identity,inputSha256("sensor-v1:profile_csv:"+content));
    EXPECT_EQ(state.profile_index,0U);
    // Replacing the path after loading does not relabel or change the loaded rows.
    file.write("voltage,current,temperature\n40,0,10\n");
    EXPECT_FLOAT_EQ(source.next().voltage_v,36);
    EXPECT_EQ(source.next().temperature_c,70);
    EXPECT_EQ(source.profileInput()->sha256,inputSha256(content));
    SensorSimulator next(SensorSimulator::Mode::PROFILE_CSV,file.path.string());
    EXPECT_FLOAT_EQ(next.next().voltage_v,40);
    EXPECT_NE(next.profileInput()->sha256,source.profileInput()->sha256);
}

TEST(InputLineage, DescribingFreshAndRestoredWalkDoesNotConsumeRandomState) {
    SensorSimulator source(SensorSimulator::Mode::RANDOM_WALK);
    for(int i=0;i<12;++i)source.next();
    const auto saved=source.exportState();
    SensorSimulator recovered(SensorSimulator::Mode::RANDOM_WALK);
    ASSERT_TRUE(recovered.restoreState(saved));
    const auto record=inputLineageJson("00000000000040008000000000000001","resume",
        SensorSimulator::Mode::RANDOM_WALK,recovered,recovered.exportState(),SohCapacityScenario{},12.5);
    std::cout<<record<<'\n';
    EXPECT_NE(record.find("\"seed\":12345"),std::string::npos);
    EXPECT_NE(record.find("\"soh_elapsed_s\":12.5"),std::string::npos);
    const auto before=recovered.exportState();
    EXPECT_EQ(before.rng,saved.rng);
    const auto a=source.next(),b=recovered.next();
    EXPECT_FLOAT_EQ(a.voltage_v,b.voltage_v);
    EXPECT_FLOAT_EQ(a.current_a,b.current_a);
    EXPECT_EQ(a.temperature_c,b.temperature_c);
}

TEST(InputLineage, CapturedInputsRejectReadErrorsAndExistingSizeCeiling) {
    std::istringstream bad("valid-looking-data");bad.setstate(std::ios::badbit);
    EXPECT_THROW(captureInput(bad,"dummy:"),std::runtime_error);
    std::istringstream large(std::string(kInputSourceMaxBytes+1,'x'));
    EXPECT_THROW(captureInput(large,"dummy:"),std::runtime_error);
    EXPECT_EQ(inputSha256("abc"),"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
}

TEST(InputLineage, AdcDescriptionExposesVirtualFieldsWithoutCreatingAValidSample) {
    SensorSimulator sensor(SensorSimulator::Mode::ADS1115_HARDWARE);
    const auto state=sensor.exportState();
    EXPECT_THROW(inputLineageJson("00000000000040008000000000000001","standalone",
        state.mode,sensor,state,SohCapacityScenario{},0),std::invalid_argument);
    const auto record=inputLineageJson("00000000000040008000000000000001","standalone",
        state.mode,sensor,state,SohCapacityScenario{},0,inputSha256("DUMMY-I2C-BINDING"));
    std::cout<<record<<'\n';
    EXPECT_NE(record.find("\"virtual_current_a\":-2"),std::string::npos);
    EXPECT_NE(record.find("\"virtual_temperature_degC\":25"),std::string::npos);
    EXPECT_EQ(record.find("DUMMY-I2C-BINDING"),std::string::npos);
    EXPECT_THROW(sensor.next(),std::logic_error);
}

TEST(InputLineage, RejectsNonfiniteProfileValuesWithoutPartialRowsOrIntegerConversion) {
    LineageProfile file;
    for(const std::string bad:{"nan,-2,25","36,inf,25","36,-2,nan","36,-2,inf"}) {
        file.write("voltage,current,temperature\n36,-2,25\n"+bad+"\n");
        SensorSimulator source(SensorSimulator::Mode::PROFILE_CSV,file.path.string());
        EXPECT_THROW(source.exportState(),std::invalid_argument);
        EXPECT_FALSE(source.profileInput());
    }
    file.write("voltage,current,temperature\n36,-2,1e20\n");
    SensorSimulator extreme(SensorSimulator::Mode::PROFILE_CSV,file.path.string());
    EXPECT_EQ(extreme.next().temperature_c,70);
}
