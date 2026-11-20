#pragma once

#include "can_session_frames.h"
#include <deque>
#include <map>
#include <memory>
#include <set>

namespace capstone::session_v2 {
struct ReceiveLimits {
    std::uint64_t pair_ms, order_ms, budget_window_ms;
    unsigned candidates_per_stream, general_slots, protected_slots, max_mac_checks;
};
void validateReceiveLimits(const ReceiveLimits& limits);

struct AuthenticatedMessage {
    std::uint16_t id = 0;
    Payload payload{}, authentication{};
    std::uint32_t counter = 0;
    std::uint64_t generation = 0, raw_received_ms = 0, auth_received_ms = 0,
                  authenticated_ms = 0, applied_ms = 0;
    std::uint64_t raw_received_ns = 0, auth_received_ns = 0;
};
enum class ReceiveReason { Metadata, UnsupportedId, PendingFull, OriginalExpired,
    AuthExpired, MacBudget, Replay, Ahead, Duplicate, Semantic, GeneralFull,
    ProtectedFull, Conflict, ClockError, BeforeState };
struct ReceiveDecision {
    ReceiveReason reason;
    std::uint16_t original_id = 0;
    std::optional<Payload> raw, authentication;
    bool mac_verified = false;
};
struct ReceiveOutcome {
    std::vector<AuthenticatedMessage> applied;
    std::vector<ReceiveDecision> decisions;
    bool failed = false;
    std::uint64_t generation = 0;
};

// One authenticated receive session. Construct only after the handshake commit;
// a failed session cannot clear its history or reopen itself. A new authenticated
// session gets a new object. Single owner thread, bounded pairing and ordering.
class OrderedReceiver {
public:
    OrderedReceiver(std::shared_ptr<const SessionKeys> keys, std::uint64_t generation,
                    ReceiveLimits limits, std::uint64_t started_ms);
    // now_ms drives deadlines; captured_ms is the actual socket/callback arrival
    // before an owner-thread backlog. Never replace arrival with processing time.
    ReceiveOutcome receive(const Frame& frame, std::uint64_t now_ms,
                           std::optional<std::uint64_t> captured_ms = std::nullopt,
                           std::optional<std::uint64_t> captured_ns = std::nullopt);
    ReceiveOutcome poll(std::uint64_t now_ms);
    bool failed() const { return failed_; }
    std::optional<std::uint32_t> lastAppliedCounter() const { return last_counter_; }
    std::optional<std::uint64_t> lastAuthenticatedBmsAt() const { return last_bms_at_; }
    std::size_t queuedGeneral() const;
    std::size_t queuedProtected() const;
    unsigned macChecksInWindow() const { return checks_; }
private:
    struct Candidate { Payload bytes; std::uint64_t received_ms,received_ns; };
    struct Stream { std::deque<Candidate> raw, auth; };
    bool advance(std::uint64_t now_ms, ReceiveOutcome& outcome);
    void match(std::uint64_t now_ms, ReceiveOutcome& outcome);
    void fail(ReceiveReason reason, std::uint16_t id, const Payload* raw,
              const Payload* auth, bool verified, ReceiveOutcome& outcome);
    void admit(const AuthenticatedMessage& message, ReceiveOutcome& outcome);
    void flush(std::uint64_t now_ms, ReceiveOutcome& outcome);

    std::shared_ptr<const SessionKeys> keys_;
    const std::uint64_t generation_;
    const ReceiveLimits limits_;
    std::uint64_t last_now_, budget_started_ms_;
    unsigned checks_ = 0;
    bool failed_ = false;
    std::array<Stream, 3> streams_{};
    std::map<std::uint32_t, AuthenticatedMessage> ordered_;
    std::optional<std::uint64_t> batch_started_ms_, last_bms_at_;
    std::optional<std::uint32_t> last_counter_;
    // Only ordinals in the protocol's current100-number acceptance window.
    std::set<std::uint32_t> seen_bms_;
};
}
