#pragma once

#include "can_session_exchange.h"
#include "../adaptive_ecu/include/planned_restart.h"

namespace capstone::session_v2 {
struct RestartNoticeLimits {
    std::uint64_t retry_ms;
    unsigned attempts;
};
struct RestartNoticePoll {
    PlannedRestart::Decision decision=PlannedRestart::Decision::None;
    std::vector<Frame> frames;
};
// Only coordinates authenticated notification/ACK and bounded waiting. The
// process owner must durably record the attempt and reclaim the old process.
// No shutdown protection is delayed by this notification.
class RestartNotice {
public:
    explicit RestartNotice(RestartNoticeLimits limits);
    bool begin(Exchange& exchange,const std::vector<std::uint8_t>& plan_body,std::uint64_t now_ms);
    bool accept(const DiagnosticResult& result,std::uint64_t now_ms);
    RestartNoticePoll poll(const Exchange& exchange,std::uint64_t now_ms);
    unsigned transmissions() const {return transmissions_;}
    bool notificationUnavailable() const {return !packet_;}
    PlannedRestart::State state() const;
private:
    const RestartNoticeLimits limits_;
    std::unique_ptr<PlannedRestart> waiting_;
    std::vector<std::uint8_t> plan_body_;
    std::optional<DiagnosticPacket> packet_;
    std::uint64_t last_send_ms_=0;
    unsigned transmissions_=0;
};

// Return a schema-checked response body only for an authenticated ECU plan.
// Re-ACKing the same plan must not create a second UI/restart operation.
}
