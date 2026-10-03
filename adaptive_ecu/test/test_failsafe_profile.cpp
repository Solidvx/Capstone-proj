#include "ekf_soc_estimator.h"
#include "failsafe_sm.h"
#include "sensor_simulator.h"

#include <gtest/gtest.h>
#include <iostream>
#include <vector>

TEST(FailSafeProfile, ProductionEstimatorAndStateMachineReachCritical) {
    SensorSimulator sensor(SensorSimulator::Mode::PROFILE_CSV,
                           std::string(ECU_SOURCE_DIR) + "/data/failsafe_demo.csv");
    EkfSocEstimator estimator;
    FailSafeStateMachine state;
    std::vector<FailSafeEvent> events;
    int step = 0;
    state.setEventCallback([&](const FailSafeEvent& event) {
        events.push_back(event);
        std::cout << "profile step=" << step << " t=" << step * 0.1
                  << " soc=" << event.soc_percent << " next=" << int(event.new_state)
                  << " reason=" << int(event.reason) << '\n';
    });
    for (; step < 1000; ++step) {
        const auto sample = sensor.next();
        const float soc = estimator.update(0.1f, sample.current_a, sample.voltage_v) * 100.0f;
        state.evaluate(soc, sample.temperature_c);
    }
    ASSERT_EQ(events.size(), 2U);
    EXPECT_EQ(events[0].prev_state, 0);
    EXPECT_EQ(events[0].new_state, 1);
    EXPECT_EQ(events[0].reason, 1);
    EXPECT_LT(events[0].soc_percent, 20.0f);
    EXPECT_EQ(events[1].prev_state, 1);
    EXPECT_EQ(events[1].new_state, 2);
    EXPECT_EQ(events[1].reason, 2);
    EXPECT_LT(events[1].soc_percent, 5.0f);
    EXPECT_EQ(state.state(), FailSafeStateMachine::State::CRITICAL);
}
