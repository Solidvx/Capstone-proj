#pragma once
#include "can_diagnostic.h"

namespace capstone::session_v2 {
struct IdsDiagnosticSubmission {
    DiagnosticKind kind;
    std::vector<std::uint8_t> body;
    std::optional<std::uint64_t> observed_at_ms;
};
// Parsing is not authorization. The socket owner must separately validate
// sender credentials, source lifetime, freshness and its bounded TX budget.
inline std::optional<IdsDiagnosticSubmission> parseIdsDiagnosticSubmission(
    const std::vector<std::uint8_t>& packet) {
    if(packet.size()<14 || packet.size()>118 || packet[0]!='C' || packet[1]!='I' ||
       packet[2]!='D' || packet[3]!='2' || packet.size()!=14u+packet[5])return std::nullopt;
    const auto kind=static_cast<DiagnosticKind>(packet[4]);
    if(kind!=DiagnosticKind::IncidentStatus && kind!=DiagnosticKind::Observation)return std::nullopt;
    std::vector<std::uint8_t> body(packet.begin()+14,packet.end());
    if(!validDiagnosticBody(0x302,kind,body))return std::nullopt;
    std::uint64_t observed=0;for(unsigned i=6;i<14;++i)observed=(observed<<8)|packet[i];
    return IdsDiagnosticSubmission{kind,std::move(body),observed};
}
}
