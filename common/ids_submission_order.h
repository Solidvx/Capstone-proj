#pragma once
#include "ids_diagnostic_ipc.h"
#include <algorithm>

namespace capstone::session_v2 {
// One object per supervised producer lifetime. A changed source is not silently
// adopted. Receive age is a local liveness bound, not proof of producer age.
class IdsSubmissionOrder {
public:
    bool accept(const IdsDiagnosticSubmission& submission,std::uint64_t now){
        if(last_now_ && now<*last_now_)return false;
        if(!validDiagnosticBody(0x302,submission.kind,submission.body))return false;
        const auto& body=submission.body;
        Nonce source{};std::copy_n(body.begin(),16,source.begin());
        if(source_ && source!=*source_)return false;
        if(submission.kind==DiagnosticKind::Observation){
            const auto tick=read(body,20);
            if(tick<=tick_)return false;
            source_=source;tick_=tick;observation_at_=now;seen_types_=0;last_now_=now;
            health_=body[16];mask_=body[48];healthy_span_=read(body,44);
            return true;
        }
        if(submission.kind!=DiagnosticKind::IncidentStatus || !observation_at_ ||
           now<*observation_at_ || now-*observation_at_>=3000 || read(body,40)!=tick_)return false;
        const unsigned bit=1u<<(body[32]-1);
        if(seen_types_&bit)return false;
        const auto state=body[33];
        if(state==1 && (health_!=1 || !(mask_&bit)))return false;
        if(state==2 && (health_!=1 || (mask_&bit) || healthy_span_<read(body,52)))return false;
        if(state==3 && health_==1)return false;
        Nonce identity{};std::copy_n(body.begin()+16,16,identity.begin());
        const auto revision=read(body,36);
        auto& previous=incidents_[body[32]-1];
        if(previous){
            if(previous->identity==identity){
                if(previous->ended || revision<=previous->revision)return false;
            }else if(!previous->ended || state==2)return false;
        }else if(state==2)return false;
        previous=Incident{identity,revision,state==2};
        seen_types_|=bit;last_now_=now;return true;
    }
private:
    static std::uint32_t read(const std::vector<std::uint8_t>& b,unsigned at){
        return (std::uint32_t(b[at])<<24)|(std::uint32_t(b[at+1])<<16)|
               (std::uint32_t(b[at+2])<<8)|b[at+3];
    }
    struct Incident {Nonce identity;std::uint32_t revision;bool ended;};
    std::array<std::optional<Incident>,4> incidents_{};
    unsigned health_=0,mask_=0;std::uint32_t healthy_span_=0;
    std::optional<Nonce> source_;
    std::optional<std::uint64_t> observation_at_,last_now_;
    std::uint32_t tick_=0;unsigned seen_types_=0;
};
}
