#include "can_session_receiver.h"

#include <openssl/crypto.h>
#include <algorithm>
#include <stdexcept>

namespace capstone::session_v2 {
namespace {
constexpr std::array<std::uint16_t,3> originals{0x100,0x101,0x104};
constexpr std::array<std::uint16_t,3> authentications{0x102,0x103,0x105};
std::uint32_t count(const Payload& payload) {
    std::uint32_t value=0;
    for(unsigned i=4;i<8;++i)value=(value<<8)|payload[i];
    return value;
}
bool semantics(std::uint16_t id,const Payload& payload) {
    if(id==0x104)return validCurrentState(payload);
    if(id==0x100)return payload[0]<=200 && payload[1]<=200 && payload[6]<=165 && payload[7]==0;
    return id==0x101 && payload[0]<=3 && payload[1]<=3 && payload[2]>=1 && payload[2]<=7 &&
        payload[3]<=200 && payload[4]<=165 && payload[5]==0 && payload[6]==0 && payload[7]==0;
}
ReceiveDecision decision(ReceiveReason reason,std::uint16_t id,const Payload* raw=nullptr,
                         const Payload* auth=nullptr,bool verified=false) {
    ReceiveDecision out{reason,id,std::nullopt,std::nullopt,verified};
    if(raw)out.raw=*raw;
    if(auth)out.authentication=*auth;
    return out;
}
}
void validateReceiveLimits(const ReceiveLimits& limits) {
    if(!limits.pair_ms || !limits.order_ms || !limits.budget_window_ms ||
       !limits.candidates_per_stream || limits.candidates_per_stream>16 ||
       !limits.general_slots || limits.general_slots>64 || !limits.protected_slots ||
       limits.protected_slots>32 || !limits.max_mac_checks)
        throw std::invalid_argument("explicit bounded receive limits required");
}
OrderedReceiver::OrderedReceiver(std::shared_ptr<const SessionKeys> keys,std::uint64_t generation,
                                 ReceiveLimits limits,std::uint64_t started_ms)
    : keys_(std::move(keys)),generation_(generation),limits_(limits),
      last_now_(started_ms),budget_started_ms_(started_ms) {
    validateReceiveLimits(limits);
    if(!keys_ || !generation)throw std::invalid_argument("authenticated session keys and generation required");
    keys_->at(Role::Data); // refuse a moved-from/unavailable key holder
}
std::size_t OrderedReceiver::queuedGeneral() const {
    return std::count_if(ordered_.begin(),ordered_.end(),[](const auto& entry){return entry.second.id==0x100;});
}
std::size_t OrderedReceiver::queuedProtected() const { return ordered_.size()-queuedGeneral(); }
void OrderedReceiver::fail(ReceiveReason reason,std::uint16_t id,const Payload* raw,
                           const Payload* auth,bool verified,ReceiveOutcome& outcome) {
    outcome.decisions.push_back(decision(reason,id,raw,auth,verified));
    failed_=outcome.failed=true;
    ordered_.clear();batch_started_ms_.reset();
    for(auto& stream:streams_){stream.raw.clear();stream.auth.clear();}
}
bool OrderedReceiver::advance(std::uint64_t now_ms,ReceiveOutcome& outcome) {
    outcome.generation=generation_;
    outcome.failed=failed_;
    if(failed_)return false;
    if(now_ms<last_now_){fail(ReceiveReason::ClockError,0,nullptr,nullptr,false,outcome);return false;}
    last_now_=now_ms;
    if(now_ms-budget_started_ms_>=limits_.budget_window_ms){budget_started_ms_=now_ms;checks_=0;}
    for(unsigned i=0;i<streams_.size();++i){
        auto& stream=streams_[i];
        for(auto it=stream.raw.begin();it!=stream.raw.end();){
            if(now_ms-it->received_ms<limits_.pair_ms){++it;continue;}
            outcome.decisions.push_back(decision(ReceiveReason::OriginalExpired,originals[i],&it->bytes));
            it=stream.raw.erase(it);
        }
        for(auto it=stream.auth.begin();it!=stream.auth.end();){
            if(now_ms-it->received_ms<limits_.pair_ms){++it;continue;}
            outcome.decisions.push_back(decision(ReceiveReason::AuthExpired,originals[i],nullptr,&it->bytes));
            it=stream.auth.erase(it);
        }
    }
    // Expiry/flush wins at the exact boundary before a newly received frame.
    flush(now_ms,outcome);
    return !failed_;
}
void OrderedReceiver::admit(const AuthenticatedMessage& message,ReceiveOutcome& outcome) {
    const auto& payload=message.payload;
    const auto& auth=message.authentication;
    if(last_counter_ && message.counter<=*last_counter_){
        outcome.decisions.push_back(decision(ReceiveReason::Replay,message.id,&payload,&auth,true));return;
    }
    if((last_counter_ && message.counter-*last_counter_>100) || (!last_counter_ && message.counter>99)){
        outcome.decisions.push_back(decision(ReceiveReason::Ahead,message.id,&payload,&auth,true));return;
    }
    const auto same=ordered_.find(message.counter);
    if(same!=ordered_.end()){
        if(same->second.id!=message.id || same->second.payload!=payload)
            fail(ReceiveReason::Conflict,message.id,&payload,&auth,true,outcome);
        else outcome.decisions.push_back(decision(ReceiveReason::Duplicate,message.id,&payload,&auth,true));
        return;
    }
    if(!semantics(message.id,payload)){
        outcome.decisions.push_back(decision(ReceiveReason::Semantic,message.id,&payload,&auth,true));return;
    }
    if(message.id==0x100 && seen_bms_.insert(message.counter).second){
        const auto arrived=std::max(message.raw_received_ms,message.auth_received_ms);
        last_bms_at_=last_bms_at_ ? std::max(*last_bms_at_,arrived) : arrived;
    }
    if(message.id==0x100 && queuedGeneral()>=limits_.general_slots){
        outcome.decisions.push_back(decision(ReceiveReason::GeneralFull,message.id,&payload,&auth,true));return;
    }
    if(message.id!=0x100 && queuedProtected()>=limits_.protected_slots){
        fail(ReceiveReason::ProtectedFull,message.id,&payload,&auth,true,outcome);return;
    }
    ordered_.emplace(message.counter,message);
    if(!batch_started_ms_)batch_started_ms_=message.authenticated_ms;
}
void OrderedReceiver::flush(std::uint64_t now_ms,ReceiveOutcome& outcome) {
    if(!batch_started_ms_ || now_ms-*batch_started_ms_<limits_.order_ms)return;
    for(auto& [counter,message]:ordered_){
        if((last_counter_ && (counter<=*last_counter_ || counter-*last_counter_>100)) ||
           (!last_counter_ && counter>99)){
            outcome.decisions.push_back(decision(ReceiveReason::Ahead,message.id,&message.payload,&message.authentication,true));
            continue;
        }
        message.applied_ms=now_ms;
        last_counter_=counter;
        outcome.applied.push_back(message);
    }
    if(last_counter_)seen_bms_.erase(seen_bms_.begin(),seen_bms_.upper_bound(*last_counter_));
    ordered_.clear();batch_started_ms_.reset();
}
void OrderedReceiver::match(std::uint64_t now_ms,ReceiveOutcome& outcome) {
    for(unsigned channel=0;channel<streams_.size();++channel){
        auto& stream=streams_[channel];
        std::size_t a=0;
        while(a<stream.auth.size()){
            std::optional<std::size_t> matched;
            const auto auth=stream.auth[a];
            for(std::size_t r=0;r<stream.raw.size();++r){
                const auto raw=stream.raw[r];
                if(checks_>=limits_.max_mac_checks){
                    outcome.decisions.push_back(decision(ReceiveReason::MacBudget,originals[channel],&raw.bytes,&auth.bytes));
                    return;
                }
                ++checks_;
                const auto counter=count(auth.bytes);
                const auto expected=dataMac(keys_->at(Role::Data),originals[channel],counter,raw.bytes);
                if(CRYPTO_memcmp(expected.data(),auth.bytes.data(),expected.size())!=0)continue;
                if(matched && stream.raw[*matched].bytes!=raw.bytes){
                    // Truncated tags can collide. Do not resolve two distinct
                    // valid originals by their arrival order.
                    fail(ReceiveReason::Conflict,originals[channel],&raw.bytes,&auth.bytes,true,outcome);return;
                }
                matched=r;
            }
            if(!matched){++a;continue;}
            const auto raw=stream.raw[*matched];
            const auto counter=count(auth.bytes);
            AuthenticatedMessage message{originals[channel],raw.bytes,auth.bytes,counter,generation_,
                raw.received_ms,auth.received_ms,now_ms,0,raw.received_ns,auth.received_ns};
            // A replay must not consume an identical raw candidate needed
            // by the next legitimate authentication frame.
            const bool past=last_counter_ && counter<=*last_counter_;
            const bool queued=ordered_.count(counter)!=0;
            stream.auth.erase(stream.auth.begin()+a);
            admit(message,outcome);
            if(failed_)return;
            if(!past && !queued && ordered_.count(counter))stream.raw.erase(stream.raw.begin()+*matched);
        }
    }
}
ReceiveOutcome OrderedReceiver::receive(const Frame& frame,std::uint64_t now_ms,
                                        std::optional<std::uint64_t> captured_ms,
                                        std::optional<std::uint64_t> captured_ns) {
    ReceiveOutcome outcome;
    if(!advance(now_ms,outcome))return outcome;
    if(frame.extended || frame.remote || frame.error || frame.dlc!=8 || frame.id>0x7ff){
        outcome.decisions.push_back(decision(ReceiveReason::Metadata,0));return outcome;
    }
    unsigned channel=0;bool auth=false;bool found=false;
    for(;channel<originals.size();++channel){
        if(frame.id==originals[channel]){found=true;break;}
        if(frame.id==authentications[channel]){found=auth=true;break;}
    }
    if(!found){outcome.decisions.push_back(decision(ReceiveReason::UnsupportedId,0));return outcome;}
    const auto arrived=captured_ms.value_or(now_ms);
    if(arrived>now_ms){outcome.decisions.push_back(decision(ReceiveReason::Metadata,originals[channel]));return outcome;}
    if(captured_ns && *captured_ns/1000000!=arrived){
        outcome.decisions.push_back(decision(ReceiveReason::Metadata,originals[channel]));return outcome;
    }
    if(now_ms-arrived>=limits_.pair_ms){
        outcome.decisions.push_back(decision(auth ? ReceiveReason::AuthExpired : ReceiveReason::OriginalExpired,
            originals[channel],auth ? nullptr : &frame.data,auth ? &frame.data : nullptr));return outcome;
    }
    auto& candidates=auth ? streams_[channel].auth : streams_[channel].raw;
    const auto duplicate=std::find_if(candidates.begin(),candidates.end(),[&](const auto& entry){return entry.bytes==frame.data;});
    if(duplicate==candidates.end()){
        if(candidates.size()>=limits_.candidates_per_stream){
            outcome.decisions.push_back(decision(ReceiveReason::PendingFull,originals[channel],auth ? nullptr : &frame.data,
                                                 auth ? &frame.data : nullptr));return outcome;
        }
        candidates.push_back({frame.data,arrived,captured_ns.value_or(arrived*1000000)});
    }else if(arrived<duplicate->received_ms || (arrived==duplicate->received_ms && captured_ns && *captured_ns<duplicate->received_ns)){
        duplicate->received_ms=arrived;duplicate->received_ns=captured_ns.value_or(arrived*1000000);
    }
    match(now_ms,outcome);
    return outcome;
}
ReceiveOutcome OrderedReceiver::poll(std::uint64_t now_ms) {
    ReceiveOutcome outcome;
    if(advance(now_ms,outcome))match(now_ms,outcome);
    return outcome;
}
}
