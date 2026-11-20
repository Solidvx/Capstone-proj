#pragma once
#include "can_diagnostic.h"
#include "can_session_receiver.h"
#include <algorithm>

namespace capstone::session_v2 {
inline Nonce diagnosticUuid(){auto id=freshNonce();id[6]=(id[6]&15)|0x40;id[8]=(id[8]&63)|0x80;return id;}
// A record describes this verifier's actual decision. It does not attribute an
// IDS incident or infer a failed MAC from a missing/expired candidate.
inline std::optional<std::vector<std::uint8_t>> rejectionRecord(const ReceiveDecision& decision,
    const std::optional<Context>& context,const Nonce& instance,const Nonce& record_id){
    unsigned reason=0;
    switch(decision.reason){
    case ReceiveReason::Metadata:reason=1;break;case ReceiveReason::UnsupportedId:reason=2;break;
    case ReceiveReason::PendingFull:reason=3;break;case ReceiveReason::OriginalExpired:reason=4;break;
    case ReceiveReason::AuthExpired:reason=5;break;case ReceiveReason::MacBudget:reason=6;break;
    case ReceiveReason::Replay:reason=7;break;case ReceiveReason::Ahead:reason=8;break;
    case ReceiveReason::Duplicate:reason=9;break;case ReceiveReason::Semantic:reason=10;break;
    case ReceiveReason::GeneralFull:reason=11;break;case ReceiveReason::ProtectedFull:reason=12;break;
    case ReceiveReason::Conflict:reason=13;break;case ReceiveReason::ClockError:reason=14;break;
    case ReceiveReason::BeforeState:reason=15;break;
    }
    std::vector<std::uint8_t> body(instance.begin(),instance.end());
    body.insert(body.end(),record_id.begin(),record_id.end());body.resize(80,0);
    body[32]=reason;body[33]=decision.mac_verified;
    body[34]=reason==4||reason==5 ? 4 : reason==6 ? 2 : reason==9 ? 3 : reason>=12&&reason<=14 ? 5 : 1;
    auto be32=[&](unsigned at,std::uint32_t value){for(unsigned i=0;i<4;++i)body[at+i]=static_cast<std::uint8_t>(value>>(24-8*i));};
    const auto raw_id=decision.original_id;
    const bool paired=raw_id==0x100 || raw_id==0x101 || raw_id==0x104;
    const auto auth_id=raw_id==0x104 ? 0x105 : raw_id+2;
    if(decision.raw && decision.authentication && context && paired){
        body[36]=2;body[37]=body[38]=8;be32(40,raw_id);be32(44,auth_id);
        const auto session=contextId(*context);std::copy(session.begin(),session.end(),body.begin()+48);
        std::copy(decision.raw->begin(),decision.raw->end(),body.begin()+64);
        std::copy(decision.authentication->begin(),decision.authentication->end(),body.begin()+72);
    }else if(paired && (decision.raw || decision.authentication)){
        body[36]=1;body[37]=8;be32(40,decision.raw ? raw_id : auth_id);
        const auto& bytes=decision.raw ? *decision.raw : *decision.authentication;
        std::copy(bytes.begin(),bytes.end(),body.begin()+64);
    }
    if(!validDiagnosticBody(0x303,DiagnosticKind::Rejection,body))return std::nullopt;
    return body;
}
}
