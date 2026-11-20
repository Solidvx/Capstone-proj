#include "bms_calculation_task.h"
#include "failsafe_sm.h"
#include <gtest/gtest.h>
#include <future>
#include <atomic>
#include <chrono>

using namespace std::chrono_literals;
namespace {
BmsCalculation input(){return {SensorSimulator(SensorSimulator::Mode::CONSTANT),EkfSocEstimator{},SohEstimator{},45,10};}
bool join(BmsCalculationTask& task){
    for(int i=0;i<1000;++i){if(task.joinIfStopped())return true;std::this_thread::sleep_for(1ms);}return false;
}
}
TEST(BmsCalculationTask, ActualCalculationCommitsOnlyDetachedResultAndNewGenerationWork){
    BmsCalculationTask task;task.checkpointCommitted(10);
    ASSERT_TRUE(task.startFromSnapshot(7));EXPECT_FALSE(task.completedWork(7));
    auto original=input();ASSERT_TRUE(task.submit(original));
    std::optional<BmsCalculation> result;
    for(int i=0;i<1000 && !result;++i){result=task.takeCompleted();std::this_thread::sleep_for(1ms);}
    ASSERT_TRUE(result);EXPECT_EQ(result->generation,7u);EXPECT_FLOAT_EQ(result->soh_percent,90);
    EXPECT_FLOAT_EQ(original.soh.soh(),1);EXPECT_TRUE(task.completedWork(7));EXPECT_FALSE(task.completedWork(6));
    EXPECT_TRUE(task.snapshotValid(60,50));EXPECT_FALSE(task.snapshotValid(61,50));EXPECT_FALSE(task.snapshotValid(9,50));
    task.requestStop();EXPECT_TRUE(join(task));
}
TEST(BmsCalculationTask, InFlightStopCannotSpawnDuplicateOrPublishLateOldWork){
    std::promise<void> entered,release;auto gate=release.get_future().share();
    BmsCalculationTask task([&](BmsCalculation& work){entered.set_value();gate.wait();calculateBms(work);});
    ASSERT_TRUE(task.startFromSnapshot(1));ASSERT_TRUE(task.submit(input()));
    EXPECT_EQ(entered.get_future().wait_for(1s),std::future_status::ready);
    EXPECT_FALSE(task.submit(input()));task.requestStop();
    EXPECT_FALSE(task.joinIfStopped());EXPECT_FALSE(task.startFromSnapshot(2));
    release.set_value();EXPECT_TRUE(join(task));
    EXPECT_FALSE(task.takeCompleted());EXPECT_FALSE(task.completedWork(1));
}
TEST(BmsCalculationTask, ThreeRealFailedWorkerGenerationsExhaustBeforeWarning){
    std::atomic<unsigned> executions{0};
    BmsCalculationTask task([&](BmsCalculation&){++executions;throw std::runtime_error("calculation failure");});
    task.checkpointCommitted(0);TaskRecovery recovery(task,{100,50,1000});
    ASSERT_TRUE(recovery.notifyTimeout(0));FailSafeStateMachine risk;
    TaskRecovery::Event last=TaskRecovery::Event::None;
    for(std::uint64_t now=1;now<1000;++now){
        last=recovery.poll(now);
        if(last==TaskRecovery::Event::Started){EXPECT_TRUE(task.submit(input()));}
        if(last==TaskRecovery::Event::Exhausted)break;
        EXPECT_EQ(risk.state(),FailSafeStateMachine::State::NORMAL);
        std::this_thread::sleep_for(1ms);
    }
    EXPECT_EQ(last,TaskRecovery::Event::Exhausted);EXPECT_EQ(executions,3u);
    EXPECT_EQ(recovery.attempts(),3u);EXPECT_TRUE(task.joinIfStopped());
    EXPECT_TRUE(risk.watchdogRestartsFailed(75,25));
    EXPECT_EQ(risk.exportState().reason,FailSafeStateMachine::REASON_WATCHDOG_RESTART_FAILED);
}
