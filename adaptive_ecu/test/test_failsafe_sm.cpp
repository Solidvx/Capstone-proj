#include "failsafe_sm.h"

#include <gtest/gtest.h>

#include <vector>

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
