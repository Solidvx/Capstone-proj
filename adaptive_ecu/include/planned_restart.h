#pragma once

#include <array>
#include <cstdint>

// Local identifiers only; this does not allocate a CAN ID or define a wire
// encoding. The transport must authenticate the ACK before calling verifiedAck.
struct RestartOperation {
    std::array<std::uint8_t, 16> session{};
    std::array<std::uint8_t, 16> request{};
    bool operator==(const RestartOperation& other) const {
        return session == other.session && request == other.request;
    }
};

// Single-use owner-thread gate for a planned restart. It neither relaxes the
// protection state nor starts a process. The supervisor still has to persist
// the attempt and reclaim the old process before starting a replacement.
class PlannedRestart {
public:
    enum class State { Idle, Waiting, Ready, Consumed, ClockError };
    enum class Decision { None, Acknowledged, Deadline, ClockError };

    explicit PlannedRestart(std::uint64_t ack_wait_ms);
    bool begin(const RestartOperation& operation, std::uint64_t now_ms);
    bool verifiedAck(const RestartOperation& operation, std::uint64_t now_ms);
    Decision poll(std::uint64_t now_ms);
    State state() const { return state_; }

private:
    bool observeClock(std::uint64_t now_ms);
    const std::uint64_t ack_wait_ms_;
    RestartOperation operation_{};
    std::uint64_t started_ms_ = 0;
    std::uint64_t last_ms_ = 0;
    State state_ = State::Idle;
    Decision ready_ = Decision::None;
};
