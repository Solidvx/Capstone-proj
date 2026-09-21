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
