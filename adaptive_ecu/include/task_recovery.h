#pragma once

#include <cstdint>

// Driven by the task owner, never by the watchdog callback thread. All task
// operations must be nonblocking. A generation is successful only when it has
// completed new work; starting a thread is not a heartbeat.
class RecoverableTask {
public:
    virtual ~RecoverableTask() = default;
    virtual void requestStop() = 0;
    virtual bool joinIfStopped() = 0;
    virtual bool snapshotValid(std::uint64_t now_ms, std::uint64_t max_age_ms) = 0;
    virtual bool startFromSnapshot(std::uint64_t generation) = 0;
    virtual bool completedWork(std::uint64_t generation) = 0;
};

class TaskRecovery {
public:
    struct Limits {
        std::uint64_t stop_ms;
        std::uint64_t heartbeat_ms;
        std::uint64_t snapshot_age_ms;
    };
    enum class State { Idle, Stopping, AwaitingHeartbeat, Exhausted, OperatorRequired };
    enum class Event { None, Started, Recovered, AttemptFailed, Exhausted,
                       StopDeadline, InvalidSnapshot, ClockError };

    // No implicit product timing policy: caller must supply all limits.
    TaskRecovery(RecoverableTask& task, Limits limits);
    bool notifyTimeout(std::uint64_t now_ms);
    Event poll(std::uint64_t now_ms);
    // Owner may defer first-work timeout only before submitting a new job.
    void awaitingInput(std::uint64_t now_ms);
    State state() const { return state_; }
    unsigned attempts() const { return attempts_; }
    unsigned consecutiveFailures() const { return failures_; }
    std::uint64_t generation() const { return generation_; }

private:
    Event failed(std::uint64_t now_ms);
    void stop(std::uint64_t now_ms);
    RecoverableTask& task_;
    Limits limits_;
    State state_ = State::Idle;
    std::uint64_t since_ = 0;
    std::uint64_t last_now_ = 0;
    std::uint64_t generation_ = 0;
    unsigned attempts_ = 0;
    unsigned failures_ = 0;
};
