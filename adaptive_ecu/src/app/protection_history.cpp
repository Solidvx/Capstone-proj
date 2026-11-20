#include "protection_history.h"
#include "can_diagnostic.h"
#include <algorithm>
#include <limits>
#include <stdexcept>
#include <utility>

namespace {
bool uuid(const ProtectionHistory::Id& id){return (id[6]&0xf0)==0x40&&(id[8]&0xc0)==0x80;}
std::vector<std::uint8_t> encoded(const ProtectionHistory::Snapshot& s,
                                const ProtectionHistory::Id& instance,bool resumed){
    std::vector<std::uint8_t> b(instance.begin(),instance.end());
    b.insert(b.end(),s.lineage.begin(),s.lineage.end());b.insert(b.end(),s.incident.begin(),s.incident.end());
    b.insert(b.end(),{s.state,s.reason,s.phase,static_cast<std::uint8_t>(resumed)});
    for(int shift=24;shift>=0;shift-=8)b.push_back(static_cast<std::uint8_t>(s.revision>>shift));
    return b;
}
}
bool ProtectionHistory::valid(const Snapshot& s){
    return s.version==1 && capstone::session_v2::validDiagnosticBody(0x302,
        capstone::session_v2::DiagnosticKind::ProtectionStatus,encoded(s,s.lineage,false));
}
bool ProtectionHistory::matches(const Snapshot& s,const FailSafeStateMachine::Snapshot& current){
    return valid(s)&&s.state==static_cast<std::uint8_t>(current.state)&&s.reason==current.reason;
}
ProtectionHistory::Id ProtectionHistory::nextId(const Id& previous){
    const auto id=source_();
    if(!uuid(id)||id==previous)throw std::runtime_error("protection identifier source failed");
    return id;
}
ProtectionHistory::ProtectionHistory(IdSource source,const FailSafeStateMachine::Snapshot& current,
                                     const std::optional<Snapshot>& restored):source_(std::move(source)){
    if(!source_)throw std::invalid_argument("protection identifier source required");
    if(restored){
        if(!matches(*restored,current))throw std::invalid_argument("protection checkpoint state mismatch");
        state_=*restored;resumed_=synchronized_=true;
    }else{
        state_.lineage=nextId({});
        // An old NORMAL/recovered checkpoint has no identifiable closed event.
        // Do not fabricate one. Its next observable risk may start a new event.
        observe(current);
    }
}
bool ProtectionHistory::observe(const FailSafeStateMachine::Snapshot& current){
    if(failed_)return false;
    const auto risk=static_cast<std::uint8_t>(current.state),reason=static_cast<std::uint8_t>(current.reason);
    if(synchronized_&&state_.state==risk&&state_.reason==reason)return false;
    auto next=state_;
    try{
        if(!synchronized_){
            if(risk==0&&reason!=0)return false;
            if(risk!=0){next.incident=nextId(state_.incident);next.revision=1;next.phase=1;}
        }else if(state_.phase!=1&&risk!=0){
            next.incident=nextId(state_.incident);next.revision=1;next.phase=1;
        }else{
            if(state_.phase==0 || state_.revision==std::numeric_limits<std::uint32_t>::max())
                throw std::overflow_error("protection revision exhausted or unidentifiable recovery");
            ++next.revision;next.phase=risk==0?2:1;
        }
        next.state=risk;next.reason=reason;
        if(!valid(next))throw std::invalid_argument("protection transition metadata invalid");
        state_=next;synchronized_=true;return true;
    }catch(const std::exception&){failed_=true;return false;}
}
std::optional<ProtectionHistory::Snapshot> ProtectionHistory::snapshot()const{
    if(failed_||!synchronized_)return std::nullopt;
    return state_;
}
std::optional<std::vector<std::uint8_t>> ProtectionHistory::body(const Id& instance)const{
    const auto saved=snapshot();if(!saved)return std::nullopt;
    auto result=encoded(*saved,instance,resumed_);
    if(!capstone::session_v2::validDiagnosticBody(0x302,capstone::session_v2::DiagnosticKind::ProtectionStatus,result))
        return std::nullopt;
    return result;
}
