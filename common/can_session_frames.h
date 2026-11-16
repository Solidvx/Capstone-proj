#pragma once

#include "can_session_crypto.h"
#include <optional>

namespace capstone::session_v2 {
enum class Kind : std::uint8_t { Request, Challenge, Offer, Confirm, Ack, Ready, Receipt };
bool validCurrentState(const Payload& payload);
struct Frame {
    std::uint32_t id = 0;
    Payload data{};
    std::uint8_t dlc = 8;
    bool extended = false;
    bool remote = false;
    bool error = false;
};
std::vector<Frame> fragment(Kind kind, std::uint16_t transfer_id,
                            const std::vector<std::uint8_t>& body);

// One logical message in one already selected exchange. Bounded to eight
// fragments, no attacker-selected allocation or replacement of an exchange.
// A completed body is NOT authenticated until its role MAC is verified.
class Assembly {
public:
    enum class State { Pending, Complete, Conflict, Expired, ClockError };
    Assembly(Kind kind, std::uint16_t transfer_id, std::uint64_t started_ms,
             std::uint64_t timeout_ms);
    std::optional<std::vector<std::uint8_t>> accept(const Frame& frame, std::uint64_t now_ms);
    State poll(std::uint64_t now_ms);
    State state() const { return state_; }
private:
    Kind kind_;
    std::uint16_t transfer_id_;
    std::uint64_t started_ms_, last_ms_, timeout_ms_;
    State state_ = State::Pending;
    std::array<std::array<std::uint8_t, 4>, 8> chunks_{};
    std::array<bool, 8> seen_{};
};
}
