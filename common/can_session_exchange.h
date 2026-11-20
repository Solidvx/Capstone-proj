#pragma once

#include "can_session_receiver.h"
#include "can_diagnostic.h"
#include <functional>
#include <memory>

namespace capstone::session_v2 {
enum class Endpoint { Ecu, Ivi };
enum class Phase { Dormant, WaitChallenge, WaitOffer, WaitConfirm, WaitAck,
                   WaitReady, WaitState, WaitReceipt, Open, Failed };

// Explicit test/deployment limits; there are deliberately no product defaults.
struct ExchangeLimits {
    std::uint64_t retry_ms, phase_ms, total_ms, assembly_ms, cache_ms, backoff_ms;
    unsigned max_batches, max_verifications;
    ReceiveLimits receive;
    DiagnosticLimits diagnostic;
};

// Owner-thread state machine. Returned frames are bounded send ATTEMPTS, not
// proof of peer receipt. Local BMS/protection must run regardless of this gate.
// session-v2 is separate from the explicitly selected legacy fixed-key profile.
class Exchange {
public:
    using NonceSource = std::function<Nonce()>;
    Exchange(Endpoint endpoint, const Key& key, ExchangeLimits limits,
             NonceSource nonce_source = freshNonce);
    ~Exchange();
    Exchange(const Exchange&) = delete;
    Exchange& operator=(const Exchange&) = delete;

    std::vector<Frame> start(std::uint64_t now_ms);
    std::vector<Frame> receive(const Frame& frame, std::uint64_t now_ms,
                              std::optional<std::uint64_t> captured_ms = std::nullopt,
                              std::optional<std::uint64_t> captured_ns = std::nullopt);
    std::vector<Frame> poll(std::uint64_t now_ms);
    std::vector<Frame> setCurrentState(const Payload& state, std::uint64_t now_ms);
    std::vector<Frame> publishData(std::uint16_t original_id, const Payload& payload,
                                   std::uint64_t now_ms);

    Phase phase() const { return phase_; }
    Endpoint endpoint() const {return endpoint_;}
    bool dataOpen() const { return gate_open_; }
    std::uint64_t nextCounter() const { return next_counter_; }
    unsigned transmissions() const { return transmissions_; }
    unsigned verifications() const { return verifications_; }
    const std::optional<Payload>& receivedState() const { return received_state_; }
    unsigned stateApplications() const { return state_applications_; }
    const std::optional<Context>& activeContext() const { return active_context_; }
    std::uint64_t generation() const { return generation_; }
    // Bounded result of the latest receive()/poll(); consume on this owner
    // thread before the next call. Arrival and application times are separate.
    const ReceiveOutcome& lastReceiveOutcome() const { return receive_outcome_; }
    const std::optional<Context>& lastReceiveContext() const { return receive_context_; }
    std::optional<std::uint64_t> lastAuthenticatedBmsAt() const {
        return receiver_ ? receiver_->lastAuthenticatedBmsAt() : std::nullopt;
    }
    std::optional<DiagnosticPacket> makeDiagnostic(DiagnosticKind kind,const std::vector<std::uint8_t>& body);
    const DiagnosticResult& lastDiagnosticResult() const {return diagnostic_result_;}
    // State receipt does not assert fresh BMS or healthy battery/sensor values.

private:
    bool observe(std::uint64_t now_ms);
    bool waiting() const;
    void fail(std::uint64_t now_ms, bool close_gate = false);
    void begin(std::uint64_t now_ms);
    void phase(Phase phase, std::uint64_t now_ms);
    bool verifyBudget(std::uint64_t now_ms);
    std::vector<Frame> send(std::vector<Frame> frames, std::uint64_t now_ms, bool remember = true);
    std::vector<Frame> sendState(std::uint64_t now_ms);
    std::vector<Frame> control(Kind kind, const std::vector<std::uint8_t>& body,
                                std::uint64_t now_ms, bool remember = true);
    std::vector<Frame> handle(Kind kind, const std::vector<std::uint8_t>& body,
                               std::uint64_t now_ms);
    std::vector<Frame> receiveControl(const Frame& frame, std::uint64_t now_ms);
    std::vector<Frame> applyReceived(ReceiveOutcome outcome, std::uint64_t now_ms);
    bool receiverEnabled() const;
    void commitSession(std::uint64_t now_ms);

    Endpoint endpoint_;
    Key shared_key_;
    ExchangeLimits limits_;
    NonceSource nonce_source_;
    Phase phase_ = Phase::Dormant;
    bool gate_open_ = false, clock_seen_ = false;
    std::uint64_t last_now_ = 0, started_ms_ = 0, phase_ms_ = 0, last_tx_ms_ = 0,
                  last_reply_ms_ = 0, completed_ms_ = 0, backoff_started_ms_ = 0;
    bool backoff_set_ = false;
    unsigned transmissions_ = 0, verifications_ = 0;
    std::uint16_t next_transfer_ = 0;
    std::optional<std::uint16_t> transfer_;
    std::optional<Context> context_;
    std::optional<Context> active_context_;
    std::uint64_t generation_ = 0;
    std::shared_ptr<SessionKeys> exchange_keys_, active_keys_;
    std::array<std::optional<Assembly>, 7> assemblies_{};
    std::vector<Frame> last_batch_;
    Payload current_state_{};
    std::optional<Payload> sent_state_, received_state_;
    std::optional<std::uint32_t> sent_state_counter_, received_state_counter_;
    std::uint64_t next_counter_ = 0;
    unsigned state_applications_ = 0;
    std::unique_ptr<OrderedReceiver> receiver_;
    ReceiveOutcome receive_outcome_;
    std::optional<Context> receive_context_;
    std::unique_ptr<DiagnosticSender> diagnostic_sender_;
    std::unique_ptr<DiagnosticReceiver> diagnostic_receiver_;
    DiagnosticResult diagnostic_result_;
};
}
