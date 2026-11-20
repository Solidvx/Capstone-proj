#include "planned_restart.h"

#include <algorithm>
#include <stdexcept>

namespace {
bool nonzero(const std::array<std::uint8_t, 16>& bytes) {
    return std::any_of(bytes.begin(), bytes.end(), [](auto byte) { return byte != 0; });
}
}

PlannedRestart::PlannedRestart(std::uint64_t ack_wait_ms) : ack_wait_ms_(ack_wait_ms) {
    if (!ack_wait_ms) throw std::invalid_argument("restart ACK wait must be positive");
}

bool PlannedRestart::begin(const RestartOperation& operation, std::uint64_t now_ms) {
    if (state_ != State::Idle || !nonzero(operation.session) || !nonzero(operation.request))
        return false;
    operation_ = operation;
    started_ms_ = last_ms_ = now_ms;
    state_ = State::Waiting;
    return true;
}

bool PlannedRestart::observeClock(std::uint64_t now_ms) {
    if (now_ms < last_ms_) {
        state_ = State::ClockError;
        return false;
    }
    last_ms_ = now_ms;
    return true;
}

bool PlannedRestart::verifiedAck(const RestartOperation& operation, std::uint64_t now_ms) {
    if (state_ != State::Waiting) return false;
    if (!observeClock(now_ms)) return false;
    // An ACK at the boundary is accepted if it is observed before poll.
    // An unrelated/late ACK never postpones the original deadline.
    if (!(operation == operation_) || now_ms - started_ms_ > ack_wait_ms_) return false;
    ready_ = Decision::Acknowledged;
    state_ = State::Ready;
    return true;
}

PlannedRestart::Decision PlannedRestart::poll(std::uint64_t now_ms) {
    if (state_ == State::Idle || state_ == State::Consumed) return Decision::None;
    if (state_ == State::ClockError || !observeClock(now_ms)) {
        state_ = State::Consumed;
        return Decision::ClockError;
    }
    if (state_ == State::Ready) {
        state_ = State::Consumed;
        return ready_;
    }
    if (now_ms - started_ms_ >= ack_wait_ms_) {
        state_ = State::Consumed;
        return Decision::Deadline;
    }
    return Decision::None;
}
