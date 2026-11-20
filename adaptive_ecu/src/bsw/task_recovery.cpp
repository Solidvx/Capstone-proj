#include "task_recovery.h"

#include <stdexcept>

TaskRecovery::TaskRecovery(RecoverableTask& task, Limits limits)
    : task_(task), limits_(limits) {
    if (!limits.stop_ms || !limits.heartbeat_ms || !limits.snapshot_age_ms) {
        throw std::invalid_argument("recovery limits must be explicitly positive");
    }
}

void TaskRecovery::stop(std::uint64_t now_ms) {
    task_.requestStop();
    since_ = now_ms;
    state_ = State::Stopping;
}

bool TaskRecovery::notifyTimeout(std::uint64_t now_ms) {
    if (state_ != State::Idle) return false;
    last_now_ = now_ms;
    attempts_ = 0;
    failures_ = 0;
    stop(now_ms);
    return true;
}

TaskRecovery::Event TaskRecovery::failed(std::uint64_t now_ms) {
    ++failures_;
    // Even the third failed worker must be reclaimed. Exhausted is emitted
    // only after joinIfStopped confirms there is no old task left alive.
    stop(now_ms);
    return Event::AttemptFailed;
}

void TaskRecovery::awaitingInput(std::uint64_t now_ms) {
    if(state_==State::AwaitingHeartbeat && now_ms>=last_now_){since_=now_ms;last_now_=now_ms;}
}

TaskRecovery::Event TaskRecovery::poll(std::uint64_t now_ms) {
    if (state_ == State::Idle || state_ == State::Exhausted ||
        state_ == State::OperatorRequired) return Event::None;
    if (now_ms < last_now_) {
        task_.requestStop();
        state_ = State::OperatorRequired;
        return Event::ClockError;
    }
    last_now_ = now_ms;
    if (state_ == State::Stopping) {
        // Deadline is inclusive. A task confirmed stopped at the boundary is
        // reclaimable; beyond it no automatic restart is allowed.
        if (now_ms - since_ > limits_.stop_ms) {
            state_ = State::OperatorRequired;
            return Event::StopDeadline;
        }
        if (!task_.joinIfStopped()) {
            if (now_ms - since_ == limits_.stop_ms) {
                state_ = State::OperatorRequired;
                return Event::StopDeadline;
            }
            return Event::None;
        }
        if (failures_ == 3) {
            state_ = State::Exhausted;
            return Event::Exhausted;
        }
        if (!task_.snapshotValid(now_ms, limits_.snapshot_age_ms)) {
            state_ = State::OperatorRequired;
            return Event::InvalidSnapshot;
        }
        ++attempts_;
        ++generation_;
        if (!task_.startFromSnapshot(generation_)) return failed(now_ms);
        since_ = now_ms;
        state_ = State::AwaitingHeartbeat;
        return Event::Started;
    }
    // Check the deadline before accepting a late completion. The owner must
    // invalidate a timed-out generation before publishing its delayed output.
    if (now_ms - since_ > limits_.heartbeat_ms) return failed(now_ms);
    if (task_.completedWork(generation_)) {
        failures_ = 0;
        state_ = State::Idle;
        return Event::Recovered;
    }
    if (now_ms - since_ == limits_.heartbeat_ms) return failed(now_ms);
    return Event::None;
}
