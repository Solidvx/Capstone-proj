#pragma once

#include "can_session_frames.h"
#include <map>
#include <memory>

namespace capstone::session_v2 {
enum class DiagnosticKind : std::uint8_t { NodeStatus=1, RestartPlan, RestartReceipt,
    IncidentStatus, Rejection, Metrics, Observation, ProtectionStatus };
bool validDiagnosticBody(std::uint16_t sender_id,DiagnosticKind kind,
                         const std::vector<std::uint8_t>& body);
struct DiagnosticPacket { std::uint32_t sequence;Nonce session_id;std::vector<Frame> frames; };
DiagnosticPacket encodeDiagnostic(const SessionKeys& keys,const Context& context,
    std::uint16_t sender_id,std::uint32_t sequence,DiagnosticKind kind,
    const std::vector<std::uint8_t>& body);

// Construct only at an authenticated session boundary; keep the same object
// throughout that session. Retry an existing packet instead of resetting it.
class DiagnosticSender {
public:
    DiagnosticSender(std::shared_ptr<const SessionKeys> keys,Context context,std::uint16_t sender_id);
    DiagnosticPacket encode(DiagnosticKind kind,const std::vector<std::uint8_t>& body);
private:
    std::shared_ptr<const SessionKeys> keys_;
    Context context_;
    std::uint16_t sender_id_;
    std::uint64_t next_=0;
};
struct DiagnosticLimits {
    std::uint64_t assembly_ms,verification_window_ms;
    unsigned assemblies,max_verifications;
};
void validateDiagnosticLimits(const DiagnosticLimits& limits);
enum class DiagnosticResultCode { Ignored,Pending,Message,Duplicate,Expired,Invalid,
    AuthFailed,ForeignSession,Replay,Conflict,Limit,ClockError,InternalError };
struct DiagnosticMessage {
    DiagnosticKind kind;
    std::uint32_t sequence;
    std::uint16_t sender_id;
    Nonce session_id;
    std::vector<std::uint8_t> body;
    std::uint64_t received_ms,verified_ms;
    bool duplicate=false;
};
struct DiagnosticResult {
    DiagnosticResultCode code=DiagnosticResultCode::Ignored;
    std::optional<DiagnosticMessage> message;
    unsigned expired_assemblies=0;
};
std::optional<std::vector<std::uint8_t>> restartReceiptBody(const DiagnosticResult& result);
// Independent diagnostic channel: failures must not stop BMS or protection.
// Duplicate messages are for bounded re-ACK only, never new UI state/liveness.
class DiagnosticReceiver {
public:
    DiagnosticReceiver(std::shared_ptr<const SessionKeys> keys,Context context,
        std::uint16_t peer_id,DiagnosticLimits limits,std::uint64_t started_ms);
    DiagnosticResult receive(const Frame& frame,std::uint64_t now_ms,
                             std::optional<std::uint64_t> captured_ms=std::nullopt);
    DiagnosticResult poll(std::uint64_t now_ms);
    bool failed() const {return failed_;}
    std::size_t pending() const {return assemblies_.size();}
private:
    struct Assembly {
        std::array<std::uint8_t,144> storage{}; // exactly36 four-byte fragments
        std::array<bool,36> seen{};
        std::optional<unsigned> count;
        std::uint64_t first_ms,last_ms;
    };
    bool advance(std::uint64_t now_ms,DiagnosticResult& result);
    std::shared_ptr<const SessionKeys> keys_;
    Nonce context_id_;
    std::uint16_t peer_id_;
    DiagnosticLimits limits_;
    std::uint64_t last_now_,window_ms_;
    unsigned checks_=0;
    bool failed_=false;
    DiagnosticResultCode failure_=DiagnosticResultCode::Conflict;
    std::map<std::uint16_t,Assembly> assemblies_;
    std::optional<std::uint32_t> highest_;
    std::map<std::uint32_t,std::array<std::uint8_t,32>> seen_;
};
}
