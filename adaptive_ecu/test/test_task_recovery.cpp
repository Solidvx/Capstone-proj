#include "task_recovery.h"
#include "planned_restart.h"
#include "failsafe_sm.h"
#include "can_publisher.h"
#include "protection_history.h"
#include <gtest/gtest.h>
#include <limits>
#include <stdexcept>
#include <vector>
#include <algorithm>

namespace {
ProtectionHistory::IdSource protectionIds(unsigned start=1){
    return [start]()mutable{
        ProtectionHistory::Id id{};id.fill(static_cast<std::uint8_t>(start++));
        id[6]=(id[6]&15)|0x40;id[8]=(id[8]&63)|0x80;return id;
    };
}
FailSafeStateMachine::Snapshot protectionRisk(unsigned state,unsigned reason){
    return {2,static_cast<FailSafeStateMachine::State>(state),static_cast<FailSafeStateMachine::Reason>(reason),state==2};
}
}

TEST(ProtectionHistory, ContinuousRiskRecoveryAndRecurrenceHaveExplicitIdentities){
    ProtectionHistory history(protectionIds(),protectionRisk(0,0));
    ASSERT_TRUE(history.snapshot());EXPECT_EQ(history.snapshot()->phase,0);EXPECT_EQ(history.snapshot()->revision,0u);
    const auto lineage=history.snapshot()->lineage;
    ASSERT_TRUE(history.observe(protectionRisk(1,3)));
    const auto warning=*history.snapshot();EXPECT_EQ(warning.revision,1u);EXPECT_EQ(warning.phase,1);
    EXPECT_FALSE(history.observe(protectionRisk(1,3)));EXPECT_EQ(history.snapshot()->revision,1u);
    ASSERT_TRUE(history.observe(protectionRisk(3,4)));
    EXPECT_EQ(history.snapshot()->incident,warning.incident);EXPECT_EQ(history.snapshot()->revision,2u);
    ASSERT_TRUE(history.observe(protectionRisk(0,5)));
    EXPECT_EQ(history.snapshot()->incident,warning.incident);EXPECT_EQ(history.snapshot()->phase,2);
    EXPECT_EQ(history.snapshot()->revision,3u);
    ASSERT_TRUE(history.observe(protectionRisk(1,1)));
    EXPECT_NE(history.snapshot()->incident,warning.incident);EXPECT_EQ(history.snapshot()->revision,1u);
    EXPECT_EQ(history.snapshot()->lineage,lineage);EXPECT_FALSE(history.resumed());
}
TEST(ProtectionHistory, VerifiedResumePreservesEventAndDoesNotAllocateReplacementIdentity){
    ProtectionHistory old(protectionIds(),protectionRisk(1,7));const auto stored=*old.snapshot();
    ProtectionHistory resumed([]()->ProtectionHistory::Id{throw std::runtime_error("must not allocate on resume");},
                              protectionRisk(1,7),stored);
    ASSERT_TRUE(resumed.snapshot());EXPECT_EQ(resumed.snapshot()->lineage,stored.lineage);
    EXPECT_EQ(resumed.snapshot()->incident,stored.incident);EXPECT_EQ(resumed.snapshot()->revision,stored.revision);
    EXPECT_TRUE(resumed.resumed());
    auto instance=protectionIds(40)();const auto body=resumed.body(instance);ASSERT_TRUE(body);
    EXPECT_EQ(body->size(),56u);EXPECT_EQ((*body)[51],1);
    EXPECT_TRUE(std::equal(instance.begin(),instance.end(),body->begin()));
    EXPECT_FALSE(resumed.body({}));
    ProtectionHistory fresh(protectionIds(50),protectionRisk(0,0));
    EXPECT_NE(fresh.snapshot()->lineage,stored.lineage);EXPECT_EQ(fresh.snapshot()->phase,0);
}
TEST(ProtectionHistory, LegacyNormalRecoveryDoesNotInventAClosedEvent){
    ProtectionHistory legacy(protectionIds(),protectionRisk(0,5));
    EXPECT_FALSE(legacy.snapshot());EXPECT_FALSE(legacy.failed());EXPECT_FALSE(legacy.resumed());
    EXPECT_FALSE(legacy.observe(protectionRisk(0,5)));
    ASSERT_TRUE(legacy.observe(protectionRisk(1,1)));ASSERT_TRUE(legacy.snapshot());
    EXPECT_EQ(legacy.snapshot()->phase,1);EXPECT_EQ(legacy.snapshot()->revision,1u);
    EXPECT_FALSE(legacy.resumed());
}
TEST(ProtectionHistory, MismatchedCorruptAndExhaustedMetadataNeverBecomesContinuity){
    ProtectionHistory old(protectionIds(),protectionRisk(1,1));auto saved=*old.snapshot();
    EXPECT_THROW(ProtectionHistory(protectionIds(),protectionRisk(2,2),saved),std::invalid_argument);
    auto bad=saved;bad.lineage={};EXPECT_FALSE(ProtectionHistory::valid(bad));
    EXPECT_THROW(ProtectionHistory(protectionIds(),protectionRisk(1,1),bad),std::invalid_argument);
    saved.revision=std::numeric_limits<std::uint32_t>::max();
    ProtectionHistory exhausted(protectionIds(),protectionRisk(1,1),saved);
    EXPECT_FALSE(exhausted.observe(protectionRisk(1,3)));EXPECT_TRUE(exhausted.failed());
    EXPECT_FALSE(exhausted.snapshot());EXPECT_FALSE(exhausted.body(protectionIds(40)()));
    EXPECT_FALSE(exhausted.observe(protectionRisk(0,5))); // no wrap or silent new lineage
}
TEST(ProtectionHistory, IdentifierFailuresAreBoundedAndIsolateEventMetadata){
    EXPECT_THROW(ProtectionHistory({},protectionRisk(0,0)),std::invalid_argument);
    EXPECT_THROW(ProtectionHistory([](){return ProtectionHistory::Id{};},protectionRisk(0,0)),std::runtime_error);
    auto source=protectionIds();const auto same=source();
    ProtectionHistory history([same](){return same;},protectionRisk(1,1));
    EXPECT_TRUE(history.observe(protectionRisk(0,5)));
    EXPECT_FALSE(history.observe(protectionRisk(1,1)));EXPECT_TRUE(history.failed());
    ProtectionHistory invalid(protectionIds(),protectionRisk(1,1));
    EXPECT_FALSE(invalid.observe(protectionRisk(1,4)));EXPECT_TRUE(invalid.failed());
}

namespace {
struct Task final : RecoverableTask {
    bool stopped = true, valid = true, starts = true, complete = false;
    unsigned stops = 0, launches = 0;
    std::uint64_t active = 0, completed = 0;
    void requestStop() override { ++stops; }
    bool joinIfStopped() override { return stopped; }
    bool snapshotValid(std::uint64_t, std::uint64_t) override { return valid; }
    bool startFromSnapshot(std::uint64_t g) override { ++launches; active = g; return starts; }
    bool completedWork(std::uint64_t g) override { return complete && completed == g; }
};
using Event = TaskRecovery::Event;
using State = TaskRecovery::State;
RestartOperation operation() {
    RestartOperation result;
    result.session[0] = 1;
    result.request[0] = 2;
    return result;
}
}

TEST(PlannedRestart, NoAckStillPermitsOneRestartAtDeadline) {
    EXPECT_THROW(PlannedRestart(0), std::invalid_argument);
    PlannedRestart restart(100); // synthetic test limit, not a product setting
    EXPECT_EQ(restart.poll(0), PlannedRestart::Decision::None);
    EXPECT_FALSE(restart.begin({}, 10));
    ASSERT_TRUE(restart.begin(operation(), 10));
    EXPECT_FALSE(restart.begin(operation(), 50));
    EXPECT_EQ(restart.poll(109), PlannedRestart::Decision::None);
    EXPECT_EQ(restart.poll(110), PlannedRestart::Decision::Deadline);
    EXPECT_FALSE(restart.verifiedAck(operation(), 110));
    EXPECT_EQ(restart.poll(200), PlannedRestart::Decision::None);
    EXPECT_FALSE(restart.begin(operation(), 200));
}

TEST(PlannedRestart, OnlyVerifiedAckForThisSessionAndRequestMayShortenWait) {
    PlannedRestart restart(100);
    ASSERT_TRUE(restart.begin(operation(), 10));
    auto unrelated = operation(); unrelated.session[1] = 9;
    EXPECT_FALSE(restart.verifiedAck(unrelated, 20));
    unrelated = operation(); unrelated.request[1] = 9;
    EXPECT_FALSE(restart.verifiedAck(unrelated, 30));
    EXPECT_EQ(restart.poll(40), PlannedRestart::Decision::None);
    EXPECT_TRUE(restart.verifiedAck(operation(), 50));
    EXPECT_FALSE(restart.verifiedAck(operation(), 60));
    EXPECT_EQ(restart.poll(60), PlannedRestart::Decision::Acknowledged);
    EXPECT_EQ(restart.poll(60), PlannedRestart::Decision::None);
}

TEST(PlannedRestart, LateOrUnrelatedAckCannotExtendDeadline) {
    PlannedRestart restart(100);
    ASSERT_TRUE(restart.begin(operation(), 10));
    auto unrelated = operation(); unrelated.request[1] = 1;
    EXPECT_FALSE(restart.verifiedAck(unrelated, 109));
    EXPECT_FALSE(restart.verifiedAck(operation(), 111));
    EXPECT_EQ(restart.poll(111), PlannedRestart::Decision::Deadline);
    PlannedRestart boundary(100);
    ASSERT_TRUE(boundary.begin(operation(), 10));
    EXPECT_TRUE(boundary.verifiedAck(operation(), 110));
    EXPECT_EQ(boundary.poll(110), PlannedRestart::Decision::Acknowledged);
}

TEST(PlannedRestart, ClockRegressionRequiresOperatorAndCannotBeMisreadAsTimeout) {
    PlannedRestart restart(100);
    ASSERT_TRUE(restart.begin(operation(), 10));
    EXPECT_EQ(restart.poll(9), PlannedRestart::Decision::ClockError);
    EXPECT_EQ(restart.poll(200), PlannedRestart::Decision::None);
    PlannedRestart on_ack(100);
    ASSERT_TRUE(on_ack.begin(operation(), 10));
    EXPECT_FALSE(on_ack.verifiedAck(operation(), 9));
    EXPECT_EQ(on_ack.poll(10), PlannedRestart::Decision::ClockError);
}

TEST(PlannedRestart, DeadlineUsesElapsedTimeWithoutAdditionOverflow) {
    PlannedRestart restart(100);
    const auto now = std::numeric_limits<std::uint64_t>::max() - 150;
    ASSERT_TRUE(restart.begin(operation(), now));
    EXPECT_EQ(restart.poll(now + 99), PlannedRestart::Decision::None);
    EXPECT_EQ(restart.poll(now + 100), PlannedRestart::Decision::Deadline);
}

TEST(TaskRecovery, RequiresExplicitPositiveLimits) {
    Task task;
    EXPECT_THROW((TaskRecovery(task, {0, 10, 20})), std::invalid_argument);
    EXPECT_THROW((TaskRecovery(task, {10, 0, 20})), std::invalid_argument);
    EXPECT_THROW((TaskRecovery(task, {10, 20, 0})), std::invalid_argument);
}

TEST(TaskRecovery, SuccessRequiresNewGenerationCompletionAndResetsFailures) {
    Task task;
    TaskRecovery recovery(task, {10, 30, 50});
    EXPECT_EQ(recovery.poll(0), Event::None);
    ASSERT_TRUE(recovery.notifyTimeout(0));
    EXPECT_FALSE(recovery.notifyTimeout(0));
    task.starts = false;
    EXPECT_EQ(recovery.poll(1), Event::AttemptFailed);
    EXPECT_EQ(recovery.consecutiveFailures(), 1u);
    task.starts = true;
    EXPECT_EQ(recovery.poll(2), Event::Started);
    task.complete = true;
    task.completed = 1; // Delayed completion from the old generation.
    EXPECT_EQ(recovery.poll(3), Event::None);
    task.completed = 2;
    EXPECT_EQ(recovery.poll(32), Event::Recovered); // Inclusive heartbeat bound.
    EXPECT_EQ(recovery.consecutiveFailures(), 0u);
    EXPECT_EQ(recovery.state(), State::Idle);
    EXPECT_TRUE(recovery.notifyTimeout(100));
    EXPECT_EQ(recovery.poll(100), Event::Started);
    EXPECT_EQ(recovery.generation(), 3u);
}

TEST(TaskRecovery, ThreeFailedRestartsEmitOneWarningAfterReclaim) {
    Task task;
    TaskRecovery recovery(task, {10, 30, 200});
    FailSafeStateMachine fsm;
    std::vector<FailSafeEvent> events;
    fsm.setEventCallback([&](const FailSafeEvent& e) { events.push_back(e); });
    recovery.notifyTimeout(0);
    for (unsigned i = 0; i < 3; ++i) {
        EXPECT_EQ(recovery.poll(i * 30), Event::Started);
        EXPECT_EQ(recovery.poll((i + 1) * 30), Event::AttemptFailed);
        EXPECT_EQ(recovery.consecutiveFailures(), i + 1);
        EXPECT_TRUE(events.empty());
    }
    ASSERT_EQ(recovery.poll(90), Event::Exhausted);
    EXPECT_TRUE(fsm.watchdogRestartsFailed(75, 25));
    ASSERT_EQ(events.size(), 1u);
    const auto frame = encodeFailSafeFrame(events[0]);
    EXPECT_EQ(frame.id, 0x101u);
    EXPECT_EQ(frame.data[0], 0);
    EXPECT_EQ(frame.data[1], 1);
    EXPECT_EQ(frame.data[2], 7);
    EXPECT_EQ(recovery.attempts(), 3u);
    EXPECT_EQ(recovery.poll(100), Event::None);
    EXPECT_FALSE(recovery.notifyTimeout(100));
    EXPECT_FALSE(fsm.watchdogRestartsFailed(75, 25));
    EXPECT_EQ(events.size(), 1u);
}

TEST(TaskRecovery, UnreclaimedWorkerNeverStartsReplacementOrFakesFailures) {
    for (const auto now : {10u, 11u}) {
        Task task; task.stopped = false;
        TaskRecovery recovery(task, {10, 30, 50});
        recovery.notifyTimeout(0);
        EXPECT_EQ(recovery.poll(9), Event::None);
        EXPECT_EQ(recovery.poll(now), Event::StopDeadline);
        EXPECT_EQ(recovery.state(), State::OperatorRequired);
        EXPECT_EQ(task.launches, 0u);
        EXPECT_EQ(recovery.consecutiveFailures(), 0u);
        EXPECT_EQ(recovery.poll(100), Event::None);
    }
}

TEST(TaskRecovery, BoundaryStopIsAllowedAndInvalidSnapshotCannotLaunch) {
    Task task;
    TaskRecovery recovery(task, {10, 30, 50});
    recovery.notifyTimeout(0);
    task.valid = false;
    EXPECT_EQ(recovery.poll(10), Event::InvalidSnapshot);
    EXPECT_EQ(task.launches, 0u);
    EXPECT_EQ(recovery.attempts(), 0u);
}

TEST(TaskRecovery, RejectsBackwardClockAndLateHeartbeat) {
    Task task;
    TaskRecovery recovery(task, {10, 30, 50});
    recovery.notifyTimeout(10);
    EXPECT_EQ(recovery.poll(9), Event::ClockError);
    EXPECT_EQ(recovery.state(), State::OperatorRequired);
    TaskRecovery other(task, {10, 30, 50});
    other.notifyTimeout(0);
    EXPECT_EQ(other.poll(0), Event::Started);
    task.complete = true; task.completed = task.active;
    EXPECT_EQ(other.poll(31), Event::AttemptFailed);
}

#include "recovery_checkpoint.h"
#include <limits>

TEST(RecoveryCheckpoint, WholeStateRestoreRejectsPartialCorruptionAndChangedInputs) {
    EkfSocEstimator ekf;
    SohEstimator soh;
    FailSafeStateMachine failsafe;
    SensorSimulator sensor(SensorSimulator::Mode::RANDOM_WALK);
    for(int i=0;i<20;++i) { auto s=sensor.next();ekf.update(.1f,s.current_a,s.voltage_v); }
    soh.recordCycle(45);soh.recordDischarge(5);
    failsafe.evaluate(4,25);failsafe.evaluate(4,25);
    const auto saved=captureCheckpoint(ekf,soh,failsafe,sensor,23.5,"test-input-sha","test-soh-sha");
    EkfSocEstimator next_ekf;
    SohEstimator next_soh;
    FailSafeStateMachine next_failsafe;
    SensorSimulator next_sensor(SensorSimulator::Mode::RANDOM_WALK);
    double elapsed=0;
    int transitions=0;
    next_failsafe.setEventCallback([&](const auto&){++transitions;});
    auto bad=saved;bad.sensor.random_walk_state.current_a=std::numeric_limits<float>::infinity();
    EXPECT_FALSE(restoreCheckpoint(bad,"test-input-sha","test-soh-sha",next_ekf,next_soh,next_failsafe,next_sensor,elapsed));
    EXPECT_FLOAT_EQ(next_ekf.soc(),.75f);
    EXPECT_FLOAT_EQ(next_soh.soh(),1);
    EXPECT_EQ(next_failsafe.state(),FailSafeStateMachine::State::NORMAL);
    EXPECT_EQ(elapsed,0);
    EXPECT_FALSE(restoreCheckpoint(saved,"changed-input","test-soh-sha",next_ekf,next_soh,next_failsafe,next_sensor,elapsed));
    EXPECT_FALSE(restoreCheckpoint(RecoveryCheckpoint{},"test-input-sha","test-soh-sha",next_ekf,next_soh,next_failsafe,next_sensor,elapsed));
    ASSERT_TRUE(restoreCheckpoint(saved,"test-input-sha","test-soh-sha",next_ekf,next_soh,next_failsafe,next_sensor,elapsed));
    EXPECT_EQ(elapsed,23.5);
    EXPECT_EQ(transitions,0);
    EXPECT_EQ(next_failsafe.state(),FailSafeStateMachine::State::CRITICAL);
    EXPECT_FLOAT_EQ(next_soh.exportState().accumulated_discharge_ah,5);
    const auto a=sensor.next(),b=next_sensor.next();
    EXPECT_FLOAT_EQ(a.voltage_v,b.voltage_v);
    EXPECT_FLOAT_EQ(ekf.update(.1f,a.current_a,a.voltage_v),next_ekf.update(.1f,b.current_a,b.voltage_v));
    next_failsafe.evaluate(4,61);
    EXPECT_EQ(transitions,1); // restored owner callback is still connected
}

#include "checkpoint_store.h"
#include <filesystem>
#include <fstream>
#include <chrono>

TEST(RecoveryCheckpoint, CodecRoundTripAndCorruptionDoNotBecomeFreshStart) {
    EkfSocEstimator ekf;
    SohEstimator soh;
    FailSafeStateMachine fsm;
    SensorSimulator sensor(SensorSimulator::Mode::RANDOM_WALK);
    sensor.next();ekf.update(.1f,-2,36);soh.recordCycle(45);soh.recordDischarge(7);
    fsm.evaluate(4,25);fsm.evaluate(4,25);
    const auto original=captureCheckpoint(ekf,soh,fsm,sensor,123.456789012345,"input-sha","soh-sha");
    const auto bytes=encodeCheckpoint(original);
    const auto restored=decodeCheckpoint(bytes);
    EXPECT_EQ(restored.sensor.rng,original.sensor.rng);
    EXPECT_FLOAT_EQ(restored.ekf.covariance,original.ekf.covariance);
    EXPECT_FLOAT_EQ(restored.soh.accumulated_discharge_ah,7);
    EXPECT_DOUBLE_EQ(restored.soh_elapsed_s,original.soh_elapsed_s);
    EXPECT_EQ(restored.failsafe.state,FailSafeStateMachine::State::CRITICAL);
    auto corrupt=bytes;corrupt[corrupt.size()-20]^=1;
    EXPECT_THROW(decodeCheckpoint(corrupt),std::invalid_argument);
    EXPECT_THROW(decodeCheckpoint(bytes.substr(0,bytes.size()/2)),std::invalid_argument);
    EXPECT_THROW(decodeCheckpoint(bytes+"extra"),std::invalid_argument);
    EXPECT_THROW(decodeCheckpoint(std::string(65537,'x')),std::invalid_argument);
    EXPECT_THROW(encodeCheckpoint(RecoveryCheckpoint{}),std::invalid_argument);
    auto bad=original;bad.ekf.soc=std::numeric_limits<float>::quiet_NaN();
    EXPECT_THROW(encodeCheckpoint(bad),std::invalid_argument);
    bad=original;bad.input_identity=std::string(1000,'x');
    EXPECT_THROW(encodeCheckpoint(bad),std::invalid_argument);
}

TEST(RecoveryCheckpoint, AtomicPrivateFilePreservesPreviousStateOnInvalidReplacement) {
    const auto dir=std::filesystem::temp_directory_path()/
        ("capstone-checkpoint-test-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    struct Cleanup { std::filesystem::path path; ~Cleanup(){std::error_code e;std::filesystem::remove_all(path,e);} } cleanup{dir};
    ASSERT_TRUE(std::filesystem::create_directory(dir));
    const auto path=(dir/"state.dat").string();
    EkfSocEstimator ekf;
    SohEstimator soh;
    FailSafeStateMachine fsm;
    SensorSimulator sensor(SensorSimulator::Mode::CONSTANT);
    auto cp=captureCheckpoint(ekf,soh,fsm,sensor,20,"input-sha","soh-sha");
    saveCheckpointAtomic(path,cp);
    EXPECT_DOUBLE_EQ(loadCheckpoint(path).soh_elapsed_s,20);
    auto bad=cp;bad.soh.estimated_capacity_ah=999;
    EXPECT_THROW(saveCheckpointAtomic(path,bad),std::invalid_argument);
    EXPECT_DOUBLE_EQ(loadCheckpoint(path).soh_elapsed_s,20);
    cp.soh_elapsed_s=25;saveCheckpointAtomic(path,cp);
    EXPECT_DOUBLE_EQ(loadCheckpoint(path).soh_elapsed_s,25);
    EXPECT_EQ(std::filesystem::status(path).permissions() & std::filesystem::perms::group_read,
              std::filesystem::perms::none);
    std::filesystem::create_symlink(path,dir/"link.dat");
    EXPECT_THROW(loadCheckpoint((dir/"link.dat").string()),std::runtime_error);
    std::filesystem::permissions(path,std::filesystem::perms::group_read,std::filesystem::perm_options::add);
    EXPECT_THROW(loadCheckpoint(path),std::runtime_error);
    std::filesystem::permissions(path,std::filesystem::perms::owner_read | std::filesystem::perms::owner_write);
    { std::ofstream broken(path,std::ios::binary|std::ios::trunc);broken<<"incomplete"; }
    EXPECT_THROW(loadCheckpoint(path),std::invalid_argument);
    EXPECT_THROW(loadCheckpoint((dir/"missing").string()),std::runtime_error);
}

#include "checkpoint_writer.h"
#include <future>
#include <mutex>
#include <vector>

TEST(CheckpointWriter, SlowDiskDoesNotBlockSubmissionAndWaitingQueueKeepsLatest) {
    std::promise<void> entered,release;
    auto released=release.get_future().share();
    auto started=entered.get_future();
    std::mutex lock;
    std::vector<double> written;
    CheckpointWriter writer([&](const RecoveryCheckpoint& checkpoint){
        if(checkpoint.soh_elapsed_s==1){entered.set_value();released.wait_for(std::chrono::seconds(2));}
        std::lock_guard<std::mutex> guard(lock);written.push_back(checkpoint.soh_elapsed_s);
    });
    RecoveryCheckpoint first;first.soh_elapsed_s=1;
    const auto one=writer.submit(first);
    ASSERT_EQ(started.wait_for(std::chrono::seconds(1)),std::future_status::ready);
    first.soh_elapsed_s=2;writer.submit(first);
    first.soh_elapsed_s=3;const auto last=writer.submit(first);
    EXPECT_EQ(writer.status().committed,0u);
    EXPECT_TRUE(writer.status().busy);
    EXPECT_EQ(writer.status().requested,last);
    release.set_value();
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(2);
    while(writer.status().committed<last && std::chrono::steady_clock::now()<deadline)std::this_thread::yield();
    ASSERT_EQ(writer.status().committed,last);
    EXPECT_LT(one,last);
    std::lock_guard<std::mutex> guard(lock);
    ASSERT_EQ(written.size(),2u);EXPECT_EQ(written[0],1);EXPECT_EQ(written[1],3);
}

TEST(CheckpointWriter, FailedStoreIsVisibleAndSuccessfulNewerCommitRestoresHealth) {
    CheckpointWriter writer([](const RecoveryCheckpoint& checkpoint){
        if(checkpoint.soh_elapsed_s==1)throw std::runtime_error("simulated disk failure");
    });
    RecoveryCheckpoint snapshot;snapshot.soh_elapsed_s=1;
    const auto failed=writer.submit(snapshot);
    auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(2);
    while(writer.status().failed<failed && std::chrono::steady_clock::now()<deadline)std::this_thread::yield();
    ASSERT_EQ(writer.status().failed,failed);
    EXPECT_TRUE(writer.status().storageFailed());EXPECT_EQ(writer.status().committed,0u);
    snapshot.soh_elapsed_s=2;const auto saved=writer.submit(snapshot);
    deadline=std::chrono::steady_clock::now()+std::chrono::seconds(2);
    while(writer.status().committed<saved && std::chrono::steady_clock::now()<deadline)std::this_thread::yield();
    ASSERT_EQ(writer.status().committed,saved);EXPECT_FALSE(writer.status().storageFailed());
}

TEST(RecoveryCheckpoint, ThermalCriticalHistorySurvivesCodecAndCoolingRestarts){
    EkfSocEstimator ekf;SohEstimator soh;FailSafeStateMachine fsm;
    SensorSimulator sensor(SensorSimulator::Mode::RANDOM_WALK);sensor.next();
    fsm.evaluate(4,25,0);fsm.evaluate(4,25,100);fsm.evaluate(80,61,200);
    auto cp=captureCheckpoint(ekf,soh,fsm,sensor,1,"input-sha","soh-sha");
    const auto decoded=decodeCheckpoint(encodeCheckpoint(cp));
    EXPECT_TRUE(decoded.failsafe.critical_latched);
    FailSafeStateMachine restored;ASSERT_TRUE(restored.restoreState(decoded.failsafe));
    for(unsigned t=1000;t<6000;t+=100)EXPECT_FALSE(restored.evaluate(80,55,t));
    EXPECT_TRUE(restored.evaluate(80,55,6000));
    EXPECT_EQ(restored.state(),FailSafeStateMachine::State::CRITICAL);
    // Historical files lack prior-low-SOC evidence; restore conservatively.
    cp.failsafe.version=1;cp.failsafe.critical_latched=false;
    ASSERT_TRUE(restored.restoreState(decodeCheckpoint(encodeCheckpoint(cp)).failsafe));
    EXPECT_TRUE(restored.exportState().critical_latched);
}

TEST(TaskRecovery, WaitingForInputIsNotThreeFailedCalculations) {
    Task task;TaskRecovery recovery(task,{10,30,50});
    ASSERT_TRUE(recovery.notifyTimeout(0));ASSERT_EQ(recovery.poll(1),Event::Started);
    recovery.awaitingInput(100);EXPECT_EQ(recovery.poll(100),Event::None);
    EXPECT_EQ(recovery.consecutiveFailures(),0u);
    // Once submitted, the owner must stop deferring this deadline.
    EXPECT_EQ(recovery.poll(130),Event::AttemptFailed);
    EXPECT_EQ(recovery.consecutiveFailures(),1u);
}

TEST(RecoveryCheckpoint, VersionTwoPreservesEventWithTheSameCalculationAndRisk){
    EkfSocEstimator ekf;SohEstimator soh;FailSafeStateMachine fsm;
    SensorSimulator sensor(SensorSimulator::Mode::CONSTANT);
    fsm.evaluate(50,56);
    ProtectionHistory history(protectionIds(),fsm.exportState());
    auto cp=captureCheckpoint(ekf,soh,fsm,sensor,12.5,"input-sha","soh-sha");
    const auto legacy=decodeCheckpoint(encodeCheckpoint(cp));
    EXPECT_EQ(legacy.version,1u);EXPECT_FALSE(legacy.protection);
    cp.version=2;cp.protection=history.snapshot();
    const auto bytes=encodeCheckpoint(cp);const auto loaded=decodeCheckpoint(bytes);
    ASSERT_TRUE(loaded.protection);EXPECT_EQ(loaded.version,2u);
    EXPECT_EQ(loaded.protection->incident,cp.protection->incident);
    EXPECT_EQ(loaded.protection->lineage,cp.protection->lineage);
    EXPECT_EQ(loaded.protection->revision,cp.protection->revision);
    EkfSocEstimator next_ekf;SohEstimator next_soh;FailSafeStateMachine next_fsm;
    SensorSimulator next_sensor(SensorSimulator::Mode::CONSTANT);double elapsed=0;
    ASSERT_TRUE(restoreCheckpoint(loaded,"input-sha","soh-sha",next_ekf,next_soh,next_fsm,next_sensor,elapsed));
    ProtectionHistory next(protectionIds(80),next_fsm.exportState(),loaded.protection);
    EXPECT_TRUE(next.resumed());EXPECT_EQ(next.snapshot()->incident,cp.protection->incident);
    EXPECT_EQ(elapsed,12.5);EXPECT_EQ(encodeCheckpoint(loaded),bytes);
    // Missing metadata is explicit in v2; it is never a validated old event.
    cp.protection.reset();const auto unknown=decodeCheckpoint(encodeCheckpoint(cp));
    EXPECT_EQ(unknown.version,2u);EXPECT_FALSE(unknown.protection);
    ProtectionHistory migrated(protectionIds(90),unknown.failsafe,unknown.protection);
    EXPECT_FALSE(migrated.resumed());EXPECT_NE(migrated.snapshot()->lineage,loaded.protection->lineage);
}
TEST(RecoveryCheckpoint, EventStateMismatchRejectsBeforeAnyCalculationMutation){
    EkfSocEstimator ekf;SohEstimator soh;FailSafeStateMachine fsm;
    SensorSimulator sensor(SensorSimulator::Mode::CONSTANT);
    fsm.evaluate(50,56);ProtectionHistory history(protectionIds(),fsm.exportState());
    auto cp=captureCheckpoint(ekf,soh,fsm,sensor,12.5,"input-sha","soh-sha");
    cp.version=2;cp.protection=history.snapshot();
    cp.protection->state=2;cp.protection->reason=2; // valid metadata, wrong saved battery state
    EXPECT_TRUE(ProtectionHistory::valid(*cp.protection));
    EXPECT_THROW(encodeCheckpoint(cp),std::invalid_argument);
    EkfSocEstimator next_ekf;SohEstimator next_soh;FailSafeStateMachine next_fsm;
    SensorSimulator next_sensor(SensorSimulator::Mode::CONSTANT);double elapsed=999;
    EXPECT_FALSE(restoreCheckpoint(cp,"input-sha","soh-sha",next_ekf,next_soh,next_fsm,next_sensor,elapsed));
    EXPECT_FLOAT_EQ(next_ekf.soc(),.75f);EXPECT_EQ(next_fsm.state(),FailSafeStateMachine::State::NORMAL);
    EXPECT_EQ(elapsed,999);
    cp.protection=history.snapshot();cp.version=1;
    EXPECT_THROW(encodeCheckpoint(cp),std::invalid_argument); // cannot silently discard new identity
    cp.version=3;EXPECT_THROW(encodeCheckpoint(cp),std::invalid_argument);
}

#include <openssl/sha.h>
#include <iomanip>
#include <sstream>
TEST(RecoveryCheckpoint, ValidChecksumDoesNotHideMalformedProtectionTail){
    EkfSocEstimator ekf;SohEstimator soh;FailSafeStateMachine fsm;
    SensorSimulator sensor(SensorSimulator::Mode::CONSTANT);
    fsm.evaluate(50,56);ProtectionHistory history(protectionIds(),fsm.exportState());
    auto cp=captureCheckpoint(ekf,soh,fsm,sensor,1,"input-sha","soh-sha");
    cp.version=2;cp.protection=history.snapshot();const auto encoded=encodeCheckpoint(cp);
    const auto hash_start=encoded.find('\n')+1,body_start=encoded.find('\n',hash_start)+1;
    const auto body=encoded.substr(body_start);
    auto with_checksum=[&](const std::string& changed){
        unsigned char hash[SHA256_DIGEST_LENGTH];SHA256(reinterpret_cast<const unsigned char*>(changed.data()),changed.size(),hash);
        std::ostringstream out;out<<encoded.substr(0,hash_start)<<std::hex<<std::setfill('0');
        for(auto byte:hash)out<<std::setw(2)<<static_cast<unsigned>(byte);
        return out.str()+'\n'+changed;
    };
    auto changed=body;const auto tail=changed.find("protection 1\n");ASSERT_NE(tail,std::string::npos);
    changed.replace(tail,13,"protection 2\n");EXPECT_THROW(decodeCheckpoint(with_checksum(changed)),std::invalid_argument);
    const auto last_space=body.find_last_of(' ');
    for(const std::string revision:{"-1","4294967296","1x",""}){
        changed=body.substr(0,last_space+1)+revision+'\n';
        EXPECT_THROW(decodeCheckpoint(with_checksum(changed)),std::invalid_argument);
    }
    changed=body.substr(0,body.find("protection 1\n"));
    EXPECT_THROW(decodeCheckpoint(with_checksum(changed)),std::invalid_argument);
}
