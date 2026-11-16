#include "failsafe_sm.h"

#include <gtest/gtest.h>

#include <vector>
#include <stdexcept>
#include <limits>

TEST(FailSafeStateMachine, CoversIcdTransitions) {
    FailSafeStateMachine fsm;
    std::vector<FailSafeEvent> events;
    fsm.setEventCallback([&](const FailSafeEvent& event) { events.push_back(event); });

    EXPECT_TRUE(fsm.evaluate(19.0f, 30));
    ASSERT_EQ(events.back().reason, FailSafeStateMachine::REASON_LOW_SOC_WARNING);
    EXPECT_EQ(fsm.state(), FailSafeStateMachine::State::WARNING);

    EXPECT_TRUE(fsm.evaluate(4.0f, 30));
    ASSERT_EQ(events.back().reason, FailSafeStateMachine::REASON_LOW_SOC_CRITICAL);
    EXPECT_EQ(fsm.state(), FailSafeStateMachine::State::CRITICAL);

    EXPECT_TRUE(fsm.evaluate(10.0f, 61));
    ASSERT_EQ(events.back().reason, FailSafeStateMachine::REASON_HIGH_TEMP_SHUTDOWN);
    EXPECT_EQ(fsm.state(), FailSafeStateMachine::State::SHUTDOWN);

    EXPECT_TRUE(fsm.manualReset());
    ASSERT_EQ(events.back().reason, FailSafeStateMachine::REASON_MANUAL_RESET);
    EXPECT_EQ(fsm.state(), FailSafeStateMachine::State::NORMAL);

    EXPECT_TRUE(fsm.evaluate(60.0f, 56));
    ASSERT_EQ(events.back().reason, FailSafeStateMachine::REASON_HIGH_TEMP_WARNING);
    EXPECT_EQ(fsm.state(), FailSafeStateMachine::State::WARNING);

    EXPECT_TRUE(fsm.evaluate(25.0f, 30));
    ASSERT_EQ(events.back().reason, FailSafeStateMachine::REASON_RECOVERED);
    EXPECT_EQ(fsm.state(), FailSafeStateMachine::State::NORMAL);

    EXPECT_FALSE(fsm.evaluate(60.0f, 30));
    EXPECT_EQ(fsm.state(), FailSafeStateMachine::State::NORMAL);
}

TEST(FailSafeStateMachine, WarningCanEscalateDirectlyToShutdownOnHighTemperature) {
    FailSafeStateMachine fsm;

    ASSERT_TRUE(fsm.evaluate(19.0f, 30));
    EXPECT_TRUE(fsm.evaluate(19.0f, 61));

    EXPECT_EQ(fsm.state(), FailSafeStateMachine::State::SHUTDOWN);
}

TEST(FailSafeStateMachine, ThresholdBoundariesDoNotEscalateEarly) {
    FailSafeStateMachine fsm;
    EXPECT_FALSE(fsm.evaluate(20.0f, 55));
    EXPECT_FALSE(fsm.manualReset());
    ASSERT_TRUE(fsm.evaluate(19.0f, 55));
    EXPECT_FALSE(fsm.evaluate(5.0f, 55));
    EXPECT_EQ(fsm.state(), FailSafeStateMachine::State::WARNING);
    EXPECT_FALSE(fsm.evaluate(25.0f, 56));
    EXPECT_TRUE(fsm.evaluate(20.0f, 55));
    EXPECT_EQ(fsm.state(), FailSafeStateMachine::State::NORMAL);
}

TEST(FailSafeStateMachine, RestoredStatesPreserveHighTemperatureBoundaryAndEvent) {
    using Fsm = FailSafeStateMachine;
    struct Case {
        Fsm::State before;
        Fsm::Reason before_reason;
        bool critical;
        int8_t temperature;
        bool changed;
        Fsm::State after;
        Fsm::Reason after_reason;
    };
    const Case cases[] = {
        {Fsm::State::NORMAL, Fsm::REASON_NONE, false, 60, true,
         Fsm::State::WARNING, Fsm::REASON_HIGH_TEMP_WARNING},
        {Fsm::State::NORMAL, Fsm::REASON_NONE, false, 61, true,
         Fsm::State::WARNING, Fsm::REASON_HIGH_TEMP_WARNING},
        {Fsm::State::WARNING, Fsm::REASON_HIGH_TEMP_WARNING, false, 60, false,
         Fsm::State::WARNING, Fsm::REASON_HIGH_TEMP_WARNING},
        {Fsm::State::WARNING, Fsm::REASON_HIGH_TEMP_WARNING, false, 61, true,
         Fsm::State::SHUTDOWN, Fsm::REASON_HIGH_TEMP_SHUTDOWN},
        {Fsm::State::WARNING, Fsm::REASON_WATCHDOG_RESTART_FAILED, false, 61, true,
         Fsm::State::SHUTDOWN, Fsm::REASON_HIGH_TEMP_SHUTDOWN},
        {Fsm::State::CRITICAL, Fsm::REASON_LOW_SOC_CRITICAL, true, 60, false,
         Fsm::State::CRITICAL, Fsm::REASON_LOW_SOC_CRITICAL},
        {Fsm::State::CRITICAL, Fsm::REASON_LOW_SOC_CRITICAL, true, 61, true,
         Fsm::State::SHUTDOWN, Fsm::REASON_HIGH_TEMP_SHUTDOWN},
        {Fsm::State::SHUTDOWN, Fsm::REASON_HIGH_TEMP_SHUTDOWN, true, 61, false,
         Fsm::State::SHUTDOWN, Fsm::REASON_HIGH_TEMP_SHUTDOWN},
    };
    for (const auto& sample : cases) {
        SCOPED_TRACE(static_cast<unsigned>(sample.before));
        SCOPED_TRACE(static_cast<int>(sample.temperature));
        Fsm fsm;
        ASSERT_TRUE(fsm.restoreState({2, sample.before, sample.before_reason, sample.critical}));
        std::vector<FailSafeEvent> events;
        fsm.setEventCallback([&](const auto& event) { events.push_back(event); });
        EXPECT_EQ(fsm.evaluate(80, sample.temperature, 100), sample.changed);
        EXPECT_EQ(fsm.state(), sample.after);
        EXPECT_EQ(fsm.exportState().reason, sample.after_reason);
        EXPECT_EQ(fsm.exportState().critical_latched, sample.critical);
        ASSERT_EQ(events.size(), sample.changed ? 1u : 0u);
        if (sample.changed) {
            EXPECT_EQ(events.front().prev_state, static_cast<uint8_t>(sample.before));
            EXPECT_EQ(events.front().new_state, static_cast<uint8_t>(sample.after));
            EXPECT_EQ(events.front().reason, sample.after_reason);
        }
    }
}

TEST(FailSafeStateMachine, CriticalRemainsLatchedWhenInputsRecover) {
    FailSafeStateMachine fsm;
    std::vector<FailSafeEvent> events;
    fsm.setEventCallback([&](const FailSafeEvent& event) { events.push_back(event); });
    ASSERT_TRUE(fsm.evaluate(19.0f, 25));
    ASSERT_TRUE(fsm.evaluate(4.0f, 25));
    EXPECT_FALSE(fsm.evaluate(90.0f, 25));
    EXPECT_FALSE(fsm.evaluate(90.0f, 60));
    EXPECT_FALSE(fsm.manualReset(90.0f, 25));
    EXPECT_EQ(fsm.state(), FailSafeStateMachine::State::CRITICAL);
    ASSERT_EQ(events.size(), 2u);
    EXPECT_EQ(events.back().reason, FailSafeStateMachine::REASON_LOW_SOC_CRITICAL);
}

TEST(FailSafeStateMachine, HighTemperatureEscalatesInTwoEvaluationsThenStaysShutdown) {
    FailSafeStateMachine fsm;
    std::vector<FailSafeEvent> events;
    fsm.setEventCallback([&](const FailSafeEvent& event) { events.push_back(event); });
    ASSERT_TRUE(fsm.evaluate(80.0f, 61));
    EXPECT_EQ(fsm.state(), FailSafeStateMachine::State::WARNING);
    ASSERT_TRUE(fsm.evaluate(80.0f, 61));
    EXPECT_EQ(fsm.state(), FailSafeStateMachine::State::SHUTDOWN);
    EXPECT_FALSE(fsm.evaluate(80.0f, 61));
    EXPECT_FALSE(fsm.evaluate(80.0f, 25));
    ASSERT_EQ(events.size(), 2u);
    EXPECT_EQ(events.front().reason, FailSafeStateMachine::REASON_HIGH_TEMP_WARNING);
    EXPECT_EQ(events.back().reason, FailSafeStateMachine::REASON_HIGH_TEMP_SHUTDOWN);
    ASSERT_TRUE(fsm.manualReset(80.0f, 25));
    EXPECT_FALSE(fsm.manualReset(80.0f, 25));
    ASSERT_EQ(events.size(), 3u);
    EXPECT_EQ(events.back().reason, FailSafeStateMachine::REASON_MANUAL_RESET);
    EXPECT_EQ(fsm.state(), FailSafeStateMachine::State::NORMAL);
}

TEST(FailSafeStateMachine, ClearingCallbackDoesNotStopStateTransitions) {
    FailSafeStateMachine fsm;
    unsigned callbacks = 0;
    fsm.setEventCallback([&](const FailSafeEvent&) { ++callbacks; });
    ASSERT_TRUE(fsm.evaluate(19.0f, 25));
    EXPECT_EQ(callbacks, 1u);
    fsm.setEventCallback({});
    ASSERT_TRUE(fsm.evaluate(4.0f, 25));
    EXPECT_EQ(fsm.state(), FailSafeStateMachine::State::CRITICAL);
    EXPECT_EQ(callbacks, 1u);
}

TEST(FailSafeStateMachine, WatchdogDoesNotDowngradeCriticalOrShutdown) {
    FailSafeStateMachine fsm;
    ASSERT_TRUE(fsm.evaluate(19, 25));
    ASSERT_TRUE(fsm.evaluate(4, 25));
    EXPECT_FALSE(fsm.watchdogRestartsFailed(75, 25));
    EXPECT_EQ(fsm.state(), FailSafeStateMachine::State::CRITICAL);
    ASSERT_TRUE(fsm.evaluate(4, 61));
    EXPECT_FALSE(fsm.watchdogRestartsFailed(75, 25));
    EXPECT_EQ(fsm.state(), FailSafeStateMachine::State::SHUTDOWN);
}

TEST(FailSafeStateMachine, CallbackExceptionPropagatesAfterStateCommit) {
    FailSafeStateMachine fsm;
    unsigned attempts=0;
    fsm.setEventCallback([&](const FailSafeEvent&) { ++attempts; throw std::runtime_error("sink failed"); });
    EXPECT_THROW(fsm.evaluate(19, 25), std::runtime_error);
    EXPECT_EQ(fsm.state(), FailSafeStateMachine::State::WARNING);
    EXPECT_THROW(fsm.evaluate(4, 25), std::runtime_error);
    const auto committed=fsm.exportState();
    EXPECT_EQ(committed.state,FailSafeStateMachine::State::CRITICAL);
    EXPECT_TRUE(committed.critical_latched);
    EXPECT_EQ(attempts,2u);
    EXPECT_FALSE(fsm.evaluate(80,25));
    EXPECT_EQ(attempts,2u); // No automatic notification retry or risk downgrade.
    FailSafeStateMachine restored;
    ASSERT_TRUE(restored.restoreState(committed));
    EXPECT_EQ(restored.state(),FailSafeStateMachine::State::CRITICAL);
    fsm.setEventCallback({});
    EXPECT_FALSE(fsm.evaluate(4, 25));
}

TEST(FailSafeStateMachine, RestoresRiskAndReasonWithoutEmittingFakeTransition) {
    FailSafeStateMachine original;
    original.evaluate(4,25);
    original.evaluate(4,25);
    const auto saved=original.exportState();
    ASSERT_EQ(saved.state,FailSafeStateMachine::State::CRITICAL);
    ASSERT_EQ(saved.reason,FailSafeStateMachine::REASON_LOW_SOC_CRITICAL);
    FailSafeStateMachine recovered;
    int events=0;
    recovered.setEventCallback([&](const auto&){++events;});
    ASSERT_TRUE(recovered.restoreState(saved));
    EXPECT_EQ(events,0);
    EXPECT_EQ(recovered.state(),FailSafeStateMachine::State::CRITICAL);
    EXPECT_FALSE(recovered.evaluate(95,25));
    EXPECT_EQ(events,0);
    EXPECT_TRUE(recovered.evaluate(95,61));
    EXPECT_EQ(events,1);
    const auto shutdown=recovered.exportState();
    FailSafeStateMachine next;
    ASSERT_TRUE(next.restoreState(shutdown));
    EXPECT_FALSE(next.evaluate(95,25));
    EXPECT_EQ(next.state(),FailSafeStateMachine::State::SHUTDOWN);
    auto invalid=shutdown;
    invalid.reason=FailSafeStateMachine::REASON_RECOVERED;
    EXPECT_FALSE(next.restoreState(invalid));
    EXPECT_EQ(next.state(),FailSafeStateMachine::State::SHUTDOWN);
    invalid=shutdown;invalid.version=9;
    EXPECT_FALSE(next.restoreState(invalid));
    invalid=shutdown;invalid.state=static_cast<FailSafeStateMachine::State>(255);
    EXPECT_FALSE(next.restoreState(invalid));
}

namespace {
void enterThermal(FailSafeStateMachine& fsm){
    ASSERT_TRUE(fsm.evaluate(80,61,0));ASSERT_TRUE(fsm.evaluate(80,61,100));
}
void coolUntil(FailSafeStateMachine& fsm,std::uint64_t first,std::uint64_t last,float soc=80){
    for(auto t=first;t<=last;t+=100)EXPECT_FALSE(fsm.evaluate(soc,55,t));
}
}
TEST(FailSafeStateMachine, ThermalRecoveryRequiresFullFiveSecondsAndEmitsOnce){
    FailSafeStateMachine fsm;enterThermal(fsm);
    coolUntil(fsm,200,5100);
    EXPECT_TRUE(fsm.evaluate(80,55,5200));
    EXPECT_EQ(fsm.state(),FailSafeStateMachine::State::NORMAL);
    EXPECT_EQ(fsm.exportState().reason,FailSafeStateMachine::REASON_RECOVERED);
    EXPECT_FALSE(fsm.evaluate(80,55,5300));
}
TEST(FailSafeStateMachine, HealthyBatteryCannotClearUnrepairedTaskWarning){
    FailSafeStateMachine fsm;
    ASSERT_TRUE(fsm.watchdogRestartsFailed(75,25));
    EXPECT_FALSE(fsm.evaluate(75,25,100));
    EXPECT_EQ(fsm.exportState().reason,FailSafeStateMachine::REASON_WATCHDOG_RESTART_FAILED);
    FailSafeStateMachine restored;
    ASSERT_TRUE(restored.restoreState(fsm.exportState()));
    EXPECT_FALSE(restored.evaluate(75,25,200));
    EXPECT_TRUE(fsm.evaluate(4,25,200));
    EXPECT_EQ(fsm.state(),FailSafeStateMachine::State::CRITICAL);
}

TEST(FailSafeStateMachine, ThermalCoolingRestartsAfterHeatInvalidInputGapOrClockRegression){
    for(unsigned failure=0;failure<5;++failure){
        FailSafeStateMachine fsm;enterThermal(fsm);coolUntil(fsm,200,5000);
        std::uint64_t next=5200;
        if(failure==0)EXPECT_FALSE(fsm.evaluate(80,56,5100));
        if(failure==1)fsm.inputUnavailable();
        if(failure==2)next=5500;
        if(failure==3){EXPECT_FALSE(fsm.evaluate(80,55,4900));next=5000;}
        if(failure==4)EXPECT_FALSE(fsm.evaluate(std::numeric_limits<float>::quiet_NaN(),55,5100));
        // Regression already started a fresh interval at 4900.
        const auto first=failure==3 ? 4900 : next;
        coolUntil(fsm,next,first+4900);
        EXPECT_TRUE(fsm.evaluate(80,55,first+5000));
    }
}
TEST(FailSafeStateMachine, CoolingCannotEraseLowSocOrPriorCriticalProtection){
    for(float soc: {19.0f,4.0f}){
        FailSafeStateMachine fsm;enterThermal(fsm);coolUntil(fsm,200,5100,soc);
        EXPECT_TRUE(fsm.evaluate(soc,55,5200));
        EXPECT_EQ(fsm.state(),soc<5 ? FailSafeStateMachine::State::CRITICAL : FailSafeStateMachine::State::WARNING);
    }
    FailSafeStateMachine fsm;fsm.evaluate(4,25,0);fsm.evaluate(4,25,100);fsm.evaluate(80,61,200);
    coolUntil(fsm,300,5200);
    auto saved=fsm.exportState();EXPECT_TRUE(saved.critical_latched);
    FailSafeStateMachine restored;ASSERT_TRUE(restored.restoreState(saved));
    coolUntil(restored,6000,10900); // interrupted cooling time is never restored
    ASSERT_TRUE(restored.evaluate(80,55,11000));
    EXPECT_EQ(restored.state(),FailSafeStateMachine::State::CRITICAL);
}

TEST(FailSafeStateMachine, SnapshotReasonAndLatchValidationPreservesExistingRisk) {
    using F = FailSafeStateMachine;
    const F::Snapshot accepted[] = {
        {2,F::State::NORMAL,F::REASON_NONE,false},
        {2,F::State::NORMAL,F::REASON_RECOVERED,false},
        {2,F::State::NORMAL,F::REASON_MANUAL_RESET,false},
        {2,F::State::WARNING,F::REASON_LOW_SOC_WARNING,false},
        {2,F::State::WARNING,F::REASON_HIGH_TEMP_WARNING,false},
        {2,F::State::WARNING,F::REASON_WATCHDOG_RESTART_FAILED,false},
        {1,F::State::NORMAL,F::REASON_NONE,false},
        {1,F::State::CRITICAL,F::REASON_LOW_SOC_CRITICAL,false},
        {1,F::State::SHUTDOWN,F::REASON_HIGH_TEMP_SHUTDOWN,false},
    };
    for (const auto& snapshot : accepted) {
        F fsm;
        int events=0;
        fsm.setEventCallback([&](const auto&){++events;});
        ASSERT_TRUE(fsm.restoreState(snapshot));
        EXPECT_EQ(fsm.state(),snapshot.state);
        EXPECT_EQ(fsm.exportState().reason,snapshot.reason);
        EXPECT_EQ(events,0);
        if(snapshot.version==1)
            EXPECT_EQ(fsm.exportState().critical_latched,
                      snapshot.state==F::State::CRITICAL || snapshot.state==F::State::SHUTDOWN);
    }
    const F::Snapshot rejected[] = {
        {2,F::State::NORMAL,F::REASON_LOW_SOC_WARNING,false},
        {2,F::State::WARNING,F::REASON_RECOVERED,false},
        {2,F::State::CRITICAL,F::REASON_LOW_SOC_CRITICAL,false},
        {2,F::State::NORMAL,F::REASON_NONE,true},
        {2,F::State::WARNING,F::REASON_LOW_SOC_WARNING,true},
    };
    for(const auto& snapshot : rejected) {
        F fsm;enterThermal(fsm);
        const auto before=fsm.exportState();
        EXPECT_FALSE(fsm.restoreState(snapshot));
        const auto after=fsm.exportState();
        EXPECT_EQ(after.state,before.state);
        EXPECT_EQ(after.reason,before.reason);
        EXPECT_EQ(after.critical_latched,before.critical_latched);
    }
}

TEST(FailSafeStateMachine, OutOfRangeMeasurementsCannotCompleteCooling) {
    const std::pair<float,int8_t> invalid[] = {
        {-1,55},{101,55},{80,-11},{80,71},
        {std::numeric_limits<float>::infinity(),55},
    };
    for(const auto& sample:invalid) {
        FailSafeStateMachine fsm;enterThermal(fsm);coolUntil(fsm,200,5100);
        EXPECT_FALSE(fsm.evaluate(sample.first,sample.second,5200));
        EXPECT_EQ(fsm.state(),FailSafeStateMachine::State::SHUTDOWN);
        coolUntil(fsm,5300,10200);
        EXPECT_TRUE(fsm.evaluate(80,55,10300));
    }
}
