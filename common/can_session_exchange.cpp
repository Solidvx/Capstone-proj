#include "can_session_exchange.h"

#include <openssl/crypto.h>
#include <algorithm>
#include <limits>
#include <stdexcept>

namespace capstone::session_v2 {
namespace {
template<class Bytes> std::vector<std::uint8_t> bytes(const Bytes& data) {
    return {data.begin(), data.end()};
}
std::uint32_t counter(const Payload& data) {
    std::uint32_t result = 0;
    for (unsigned i = 4; i < 8; ++i) result = (result << 8) | data[i];
    return result;
}
Payload authentication(const Key& key, std::uint16_t id, std::uint32_t count, const Payload& payload) {
    Payload result{};
    const auto mac = dataMac(key, id, count, payload);
    std::copy(mac.begin(), mac.end(), result.begin());
    for (unsigned i = 0; i < 4; ++i) result[4+i] = static_cast<std::uint8_t>(count >> (24-i*8));
    return result;
}
Tag tag(const std::vector<std::uint8_t>& body, std::size_t offset = 0) {
    Tag result{};
    std::copy_n(body.begin()+offset, 16, result.begin());
    return result;
}
bool standard(const Frame& frame) {
    return frame.dlc == 8 && !frame.extended && !frame.remote && !frame.error && frame.id <= 0x7ff;
}
}

Exchange::Exchange(Endpoint endpoint,const Key& key,ExchangeLimits limits,NonceSource source)
    : endpoint_(endpoint), shared_key_(key), limits_(limits), nonce_source_(std::move(source)) {
    if ((endpoint!=Endpoint::Ecu && endpoint!=Endpoint::Ivi) ||
        !limits.retry_ms || !limits.phase_ms || !limits.total_ms || !limits.assembly_ms ||
        !limits.cache_ms || !limits.backoff_ms || !limits.max_batches || !limits.max_verifications ||
        limits.retry_ms > limits.phase_ms || limits.phase_ms > limits.total_ms ||
        limits.assembly_ms > limits.phase_ms || limits.receive.pair_ms > limits.phase_ms ||
        limits.receive.order_ms >= limits.phase_ms || !nonce_source_)
        throw std::invalid_argument("session exchange requires explicit valid limits and nonce source");
    validateReceiveLimits(limits.receive);
    validateDiagnosticLimits(limits.diagnostic);
}
Exchange::~Exchange() { OPENSSL_cleanse(shared_key_.data(),shared_key_.size()); }
bool Exchange::waiting() const {
    return phase_ != Phase::Dormant && phase_ != Phase::Open && phase_ != Phase::Failed;
}
void Exchange::fail(std::uint64_t now_ms,bool close_gate) {
    phase_ = Phase::Failed;
    backoff_started_ms_ = now_ms; backoff_set_ = true;
    last_batch_.clear();
    for (auto& assembly:assemblies_) assembly.reset();
    exchange_keys_.reset(); context_.reset(); transfer_.reset();
    if (close_gate) {
        gate_open_=false; active_keys_.reset(); active_context_.reset(); receiver_.reset();
        diagnostic_sender_.reset();diagnostic_receiver_.reset();
    }
}
bool Exchange::observe(std::uint64_t now_ms) {
    if (clock_seen_ && now_ms < last_now_) {
        fail(now_ms,true); return false;
    }
    last_now_=now_ms; clock_seen_=true;
    if (waiting() && (now_ms-started_ms_ >= limits_.total_ms || now_ms-phase_ms_ >= limits_.phase_ms)) {
        fail(now_ms); return false;
    }
    return true;
}
void Exchange::begin(std::uint64_t now_ms) {
    started_ms_=phase_ms_=last_tx_ms_=last_reply_ms_=backoff_started_ms_=now_ms;
    backoff_set_=true; transmissions_=verifications_=0;
    last_batch_.clear(); exchange_keys_.reset(); context_.reset(); transfer_.reset();
    sent_state_.reset(); sent_state_counter_.reset();
    for (auto& assembly:assemblies_) assembly.reset();
}
void Exchange::phase(Phase value,std::uint64_t now_ms) {
    phase_=value; phase_ms_=now_ms;
    for (auto& assembly:assemblies_) assembly.reset();
}
bool Exchange::verifyBudget(std::uint64_t now_ms) {
    if (verifications_ >= limits_.max_verifications) { fail(now_ms); return false; }
    ++verifications_; return true;
}
std::vector<Frame> Exchange::send(std::vector<Frame> frames,std::uint64_t now_ms,bool remember) {
    if (!remember && now_ms-last_reply_ms_ < limits_.retry_ms) return {};
    if (transmissions_ >= limits_.max_batches) { fail(now_ms); return {}; }
    ++transmissions_;
    if (remember) { last_batch_=frames; last_tx_ms_=now_ms; }
    else last_reply_ms_=now_ms;
    return frames;
}
std::vector<Frame> Exchange::control(Kind kind,const std::vector<std::uint8_t>& body,
                                     std::uint64_t now_ms,bool remember) {
    return send(fragment(kind,kind==Kind::Request ? 0 : transfer_.value(),body),now_ms,remember);
}
std::vector<Frame> Exchange::start(std::uint64_t now_ms) {
    if (!observe(now_ms) || waiting() ||
        (backoff_set_ && now_ms-backoff_started_ms_ < limits_.backoff_ms)) return {};
    begin(now_ms);
    if (endpoint_==Endpoint::Ecu) {
        phase(Phase::WaitChallenge,now_ms);
        return control(Kind::Request,std::vector<std::uint8_t>(4),now_ms);
    }
    try {
        Context ctx{++next_transfer_,nonce_source_(),{}};
        context_=ctx; transfer_=ctx.transfer_id;
        phase(Phase::WaitOffer,now_ms);
        return control(Kind::Challenge,bytes(ctx.nonce_b),now_ms);
    } catch (...) { fail(now_ms); throw; }
}
std::vector<Frame> Exchange::poll(std::uint64_t now_ms) {
    receive_outcome_={};
    diagnostic_result_={};
    receive_context_=active_context_;
    if (!observe(now_ms)) return {};
    if(diagnostic_receiver_){
        try{diagnostic_result_=diagnostic_receiver_->poll(now_ms);}
        catch(const std::runtime_error&){diagnostic_result_.code=DiagnosticResultCode::InternalError;diagnostic_receiver_.reset();}
    }
    std::vector<Frame> tx;
    try { if(receiverEnabled())tx=applyReceived(receiver_->poll(now_ms),now_ms); }
    catch(...) { fail(now_ms,true);throw; }
    if (phase_==Phase::Dormant || phase_==Phase::Failed || (phase_==Phase::Open && !gate_open_))
    {
        auto extra=start(now_ms);tx.insert(tx.end(),extra.begin(),extra.end());
    } else if (waiting() && !last_batch_.empty() && now_ms-last_tx_ms_ >= limits_.retry_ms) {
        auto extra=send(last_batch_,now_ms);tx.insert(tx.end(),extra.begin(),extra.end());
    }
    return tx;
}
std::vector<Frame> Exchange::sendState(std::uint64_t now_ms) {
    const auto next=takeCounter(next_counter_);
    if(!next){fail(now_ms,true);return {};}
    sent_state_=current_state_;sent_state_counter_=next;
    const auto auth=authentication(active_keys_->at(Role::Data),0x104,*sent_state_counter_,*sent_state_);
    return send({Frame{0x104,*sent_state_},Frame{0x105,auth}},now_ms);
}
std::vector<Frame> Exchange::setCurrentState(const Payload& payload,std::uint64_t now_ms) {
    if (endpoint_!=Endpoint::Ecu || !validCurrentState(payload))
        throw std::invalid_argument("ECU current state and reason must be valid");
    const bool changed=current_state_!=payload;
    current_state_=payload;
    if (!observe(now_ms) || !changed) return {};
    // Once general traffic is open, actual new transitions use 0x101/103.
    // Updating the current snapshot must not close the gate for every event.
    return phase_==Phase::WaitReceipt ? sendState(now_ms) : std::vector<Frame>{};
}
std::vector<Frame> Exchange::publishData(std::uint16_t id,const Payload& payload,std::uint64_t now_ms) {
    if (endpoint_!=Endpoint::Ecu || (id!=0x100 && id!=0x101))
        throw std::invalid_argument("ECU BMS or transition ID required");
    if (!observe(now_ms) || !gate_open_ || !active_keys_) return {};
    const auto next=takeCounter(next_counter_);
    if(!next) {
        gate_open_=false; return start(now_ms);
    }
    const auto count=*next;
    return {Frame{id,payload},Frame{static_cast<std::uint32_t>(id+2),
                                   authentication(active_keys_->at(Role::Data),id,count,payload)}};
}

std::vector<Frame> Exchange::handle(Kind kind,const std::vector<std::uint8_t>& body,std::uint64_t now_ms) {
    if (endpoint_==Endpoint::Ecu && kind==Kind::Challenge && phase_==Phase::WaitChallenge) {
        Context ctx{*transfer_,{},nonce_source_()};
        std::copy(body.begin(),body.end(),ctx.nonce_b.begin());
        auto keys=std::make_shared<SessionKeys>(deriveKeys(shared_key_,ctx));
        context_=ctx; exchange_keys_=std::move(keys);
        auto offer=bytes(ctx.nonce_a); const auto proof=controlTag(*exchange_keys_,ctx,Role::Offer);
        offer.insert(offer.end(),proof.begin(),proof.end());
        phase(Phase::WaitConfirm,now_ms);
        return control(Kind::Offer,offer,now_ms);
    }
    if (endpoint_==Endpoint::Ivi && kind==Kind::Offer && phase_==Phase::WaitOffer) {
        if (!verifyBudget(now_ms)) return {};
        auto ctx=*context_; std::copy_n(body.begin(),16,ctx.nonce_a.begin());
        auto keys=std::make_shared<SessionKeys>(deriveKeys(shared_key_,ctx));
        if (!tagMatches(controlTag(*keys,ctx,Role::Offer),tag(body,16))) return {};
        context_=ctx; exchange_keys_=std::move(keys);
        phase(Phase::WaitAck,now_ms);
        return control(Kind::Confirm,bytes(controlTag(*exchange_keys_,ctx,Role::Confirm)),now_ms);
    }
    if (!exchange_keys_ || !context_) return {};
    if (endpoint_==Endpoint::Ecu && kind==Kind::Confirm &&
        (phase_==Phase::WaitConfirm || phase_==Phase::WaitReady || phase_==Phase::WaitReceipt || phase_==Phase::Open)) {
        if (!verifyBudget(now_ms) || !tagMatches(controlTag(*exchange_keys_,*context_,Role::Confirm),tag(body))) return {};
        if (phase_==Phase::WaitConfirm) {
            // Authenticated commit boundary: never fall back to the old key.
            if (generation_==std::numeric_limits<std::uint64_t>::max()) { fail(now_ms,true); return {}; }
            commitSession(now_ms);
            phase(Phase::WaitReady,now_ms);
            return control(Kind::Ack,bytes(controlTag(*exchange_keys_,*context_,Role::Ack)),now_ms);
        }
        return control(Kind::Ack,bytes(controlTag(*exchange_keys_,*context_,Role::Ack)),now_ms,false);
    }
    if (endpoint_==Endpoint::Ivi && kind==Kind::Ack &&
        (phase_==Phase::WaitAck || phase_==Phase::WaitState || phase_==Phase::Open)) {
        if (!verifyBudget(now_ms) || !tagMatches(controlTag(*exchange_keys_,*context_,Role::Ack),tag(body))) return {};
        if (phase_==Phase::WaitAck) {
            if (generation_==std::numeric_limits<std::uint64_t>::max()) { fail(now_ms,true); return {}; }
            commitSession(now_ms);
            phase(Phase::WaitState,now_ms);
            return control(Kind::Ready,bytes(controlTag(*exchange_keys_,*context_,Role::Ready)),now_ms);
        }
        return control(Kind::Ready,bytes(controlTag(*exchange_keys_,*context_,Role::Ready)),now_ms,false);
    }
    if (endpoint_==Endpoint::Ecu && kind==Kind::Ready &&
        (phase_==Phase::WaitReady || phase_==Phase::WaitReceipt)) {
        if (!verifyBudget(now_ms) || !tagMatches(controlTag(*exchange_keys_,*context_,Role::Ready),tag(body))) return {};
        if (phase_==Phase::WaitReady) { phase(Phase::WaitReceipt,now_ms); return sendState(now_ms); }
        return send(last_batch_,now_ms,false);
    }
    if (endpoint_==Endpoint::Ecu && kind==Kind::Receipt && phase_==Phase::WaitReceipt) {
        Payload encoded{}; std::copy_n(body.begin(),4,encoded.begin()+4);
        if (counter(encoded)!=sent_state_counter_ || sent_state_!=current_state_) return {};
        if (!verifyBudget(now_ms) || !tagMatches(stateReceiptTag(*exchange_keys_,*context_,*sent_state_counter_,*sent_state_),tag(body,4)))
            return {};
        gate_open_=true; completed_ms_=now_ms; phase(Phase::Open,now_ms);
        last_batch_.clear(); return {};
    }
    return {};
}

bool Exchange::receiverEnabled() const {
    return endpoint_==Endpoint::Ivi && receiver_ && (gate_open_ || phase_==Phase::WaitState);
}
std::vector<Frame> Exchange::applyReceived(ReceiveOutcome outcome,std::uint64_t now_ms) {
    receive_context_=active_context_;
    receive_outcome_=std::move(outcome);
    bool changed=false,duplicate=false;
    for(const auto& message:receive_outcome_.applied){
        if(message.id!=0x104)continue;
        received_state_=message.payload;received_state_counter_=message.counter;++state_applications_;
        changed=true;
    }
    if(receive_outcome_.failed){fail(now_ms,true);return {};}
    for(const auto& decision:receive_outcome_.decisions){
        if(decision.reason!=ReceiveReason::Replay || !decision.mac_verified || decision.original_id!=0x104 ||
           !decision.raw || !decision.authentication || !received_state_counter_)continue;
        if(*decision.raw==received_state_ && counter(*decision.authentication)==received_state_counter_)duplicate=true;
    }
    if(!changed && !duplicate)return {};
    if(phase_==Phase::WaitState && changed){
        completed_ms_=now_ms;gate_open_=true;phase(Phase::Open,now_ms);last_batch_.clear();
    }
    // A pending rekey must not receive an old session receipt under its new
    // transfer ID. Only the active exchange's completed/current state is acked.
    if(phase_!=Phase::Open || !active_context_ || !active_keys_ ||
       now_ms-completed_ms_>=limits_.cache_ms)return {};
    const auto proof=stateReceiptTag(*active_keys_,*active_context_,*received_state_counter_,*received_state_);
    std::vector<std::uint8_t> receipt(4);
    for(unsigned i=0;i<4;++i)receipt[i]=static_cast<std::uint8_t>(*received_state_counter_>>(24-i*8));
    receipt.insert(receipt.end(),proof.begin(),proof.end());
    return send(fragment(Kind::Receipt,active_context_->transfer_id,receipt),now_ms,changed);
}
std::vector<Frame> Exchange::receive(const Frame& frame,std::uint64_t now_ms,
                                    std::optional<std::uint64_t> captured_ms,
                                    std::optional<std::uint64_t> captured_ns) {
    receive_outcome_={};
    diagnostic_result_={};
    receive_context_=active_context_;
    if(!observe(now_ms))return {};
    if(frame.id==(endpoint_==Endpoint::Ecu ? 0x303u : 0x302u)){
        if(diagnostic_receiver_){
            try{diagnostic_result_=diagnostic_receiver_->receive(frame,now_ms,captured_ms);}
            catch(const std::runtime_error&){diagnostic_result_.code=DiagnosticResultCode::InternalError;diagnostic_receiver_.reset();}
        }
        // The side channel cannot close/reopen the BMS gate or reset counters.
        if(receiverEnabled())return applyReceived(receiver_->poll(now_ms),now_ms);
        return {};
    }
    const bool state=frame.id==0x104 || frame.id==0x105;
    const bool general=frame.id==0x100 || frame.id==0x101 || frame.id==0x102 || frame.id==0x103;
    if(endpoint_==Endpoint::Ivi && (state || general)){
        const bool accept_state=phase_==Phase::WaitState ||
            (phase_==Phase::Open && now_ms-completed_ms_<limits_.cache_ms);
        if(!receiverEnabled() || (state && !accept_state) || (general && !gate_open_)){
            receive_outcome_.decisions.push_back({ReceiveReason::BeforeState,
                static_cast<std::uint16_t>(frame.id),std::nullopt,std::nullopt,false});
            return {};
        }
        try{return applyReceived(receiver_->receive(frame,now_ms,captured_ms,captured_ns),now_ms);}
        catch(...){fail(now_ms,true);throw;}
    }
    // Process authenticated commits before flushing the old generation's
    // ordered queue at this boundary. ACK replaces that queue atomically.
    auto tx=receiveControl(frame,now_ms);
    if(receiverEnabled()){
        try {
            auto extra=applyReceived(receiver_->poll(now_ms),now_ms);
            tx.insert(tx.end(),extra.begin(),extra.end());
        } catch(...) {fail(now_ms,true);throw;}
    }
    return tx;
}

void Exchange::commitSession(std::uint64_t now_ms){
    // Authentication has succeeded: the old data path is now irrevocably shut.
    // Prepare replacement objects before publishing a new generation/ordinal.
    gate_open_=false;diagnostic_sender_.reset();diagnostic_receiver_.reset();receiver_.reset();
    const auto sender=endpoint_==Endpoint::Ecu ? 0x302 : 0x303;
    auto tx=std::make_unique<DiagnosticSender>(exchange_keys_,*context_,sender);
    auto rx=std::make_unique<DiagnosticReceiver>(exchange_keys_,*context_,
        endpoint_==Endpoint::Ecu ? 0x303 : 0x302,limits_.diagnostic,now_ms);
    auto data=endpoint_==Endpoint::Ivi ?
        std::make_unique<OrderedReceiver>(exchange_keys_,generation_+1,limits_.receive,now_ms) : nullptr;
    active_keys_=exchange_keys_;active_context_=context_;++generation_;
    if(endpoint_==Endpoint::Ecu)next_counter_=0;
    else received_state_counter_.reset();
    diagnostic_sender_=std::move(tx);diagnostic_receiver_=std::move(rx);receiver_=std::move(data);
}
std::optional<DiagnosticPacket> Exchange::makeDiagnostic(DiagnosticKind kind,const std::vector<std::uint8_t>& body){
    if(!diagnostic_sender_)return std::nullopt;
    return diagnostic_sender_->encode(kind,body);
}

std::vector<Frame> Exchange::receiveControl(const Frame& frame,std::uint64_t now_ms) {
    if(!standard(frame))return {};
    if (frame.id!=(endpoint_==Endpoint::Ecu ? 0x301u : 0x300u) || (frame.data[0]>>4)!=2 || frame.data[1]>=8) return {};
    const auto type=frame.data[0]&0xf;
    if (type>6) return {};
    const unsigned count=type==0 ? 1 : type==2 ? 8 : type==6 ? 5 : 4;
    if (frame.data[1]>=count) return {};
    const auto kind=static_cast<Kind>(type);
    const auto tid=static_cast<std::uint16_t>((frame.data[2]<<8)|frame.data[3]);
    if (kind==Kind::Request && endpoint_==Endpoint::Ivi && frame.data[1]==0 && tid==0 &&
        std::all_of(frame.data.begin()+4,frame.data.end(),[](auto value){return value==0;})) return start(now_ms);
    if (kind==Kind::Challenge && endpoint_==Endpoint::Ecu && !waiting()) {
        if (backoff_set_ && now_ms-backoff_started_ms_<limits_.backoff_ms) return {};
        begin(now_ms); phase(Phase::WaitChallenge,now_ms);
    }
    if (phase_==Phase::Open && now_ms-completed_ms_>=limits_.cache_ms) return {};
    if (endpoint_==Endpoint::Ecu && phase_==Phase::WaitChallenge && kind==Kind::Challenge && !transfer_) transfer_=tid;
    if (!transfer_ || *transfer_!=tid || phase_==Phase::Dormant || phase_==Phase::Failed) return {};
    auto& assembly=assemblies_[type];
    if (assembly && assembly->poll(now_ms)!=Assembly::State::Pending) assembly.reset();
    if (!assembly) assembly.emplace(kind,tid,now_ms,limits_.assembly_ms);
    const auto body=assembly->accept(frame,now_ms);
    if (!body) return {};
    assembly.reset();
    try { return handle(kind,*body,now_ms); }
    catch (...) { fail(now_ms); throw; }
}
}
