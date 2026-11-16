#include "can_restart_notice.h"

#include <algorithm>
#include <stdexcept>

namespace capstone::session_v2 {
namespace {
std::uint32_t read32(const std::vector<std::uint8_t>& body,unsigned offset){
    std::uint32_t value=0;for(unsigned i=0;i<4;++i)value=(value<<8)|body[offset+i];return value;
}
bool authenticated(const DiagnosticResult& result){
    return (result.code==DiagnosticResultCode::Message||result.code==DiagnosticResultCode::Duplicate)&&result.message;
}
}
RestartNotice::RestartNotice(RestartNoticeLimits limits):limits_(limits){
    if(!limits.retry_ms||!limits.attempts)throw std::invalid_argument("restart notice requires explicit positive retry limits");
}
PlannedRestart::State RestartNotice::state()const{
    return waiting_ ? waiting_->state() : PlannedRestart::State::Idle;
}
bool RestartNotice::begin(Exchange& exchange,const std::vector<std::uint8_t>& plan,std::uint64_t now){
    if(waiting_)return false; // single use; duplicates cannot extend the deadline
    if(exchange.endpoint()!=Endpoint::Ecu||!validDiagnosticBody(0x302,DiagnosticKind::RestartPlan,plan))
        throw std::invalid_argument("invalid restart notice body");
    // Even when no session exists, the owner must eventually continue after
    // the explicit wait. An unsent plan cannot receive an ACK.
    auto waiting=std::make_unique<PlannedRestart>(read32(plan,52));
    RestartOperation operation{};
    if(exchange.activeContext())operation.session=contextId(*exchange.activeContext());
    else operation.session[0]=1; // local unsent sentinel; never transmitted/ACKed
    std::copy_n(plan.begin()+16,16,operation.request.begin());
    if(!waiting->begin(operation,now))throw std::invalid_argument("invalid restart operation");
    plan_body_=plan;waiting_=std::move(waiting);
    try {packet_=exchange.makeDiagnostic(DiagnosticKind::RestartPlan,plan);}
    catch(const std::runtime_error&) {packet_.reset();} // reported unavailable; bounded wait still applies
    last_send_ms_=now;
    return true;
}
bool RestartNotice::accept(const DiagnosticResult& result,std::uint64_t now){
    if(!waiting_||!packet_||!authenticated(result))return false;
    const auto& message=*result.message;
    if(message.kind!=DiagnosticKind::RestartReceipt||message.sender_id!=0x303||
       message.session_id!=packet_->session_id||
       !validDiagnosticBody(0x303,message.kind,message.body)||
       !std::equal(plan_body_.begin(),plan_body_.begin()+32,message.body.begin())||
       read32(message.body,36)!=packet_->sequence)return false;
    RestartOperation operation{packet_->session_id,{}};
    std::copy_n(plan_body_.begin()+16,16,operation.request.begin());
    return waiting_->verifiedAck(operation,now);
}
RestartNoticePoll RestartNotice::poll(const Exchange& exchange,std::uint64_t now){
    RestartNoticePoll result;
    if(!waiting_)return result;
    result.decision=waiting_->poll(now);
    if(result.decision!=PlannedRestart::Decision::None||waiting_->state()!=PlannedRestart::State::Waiting)return result;
    // Never re-encode the old request after a session switch: a new envelope
    // must not refresh an already-running restart deadline or UI incident.
    if(!packet_||!exchange.activeContext()||contextId(*exchange.activeContext())!=packet_->session_id||
       transmissions_>=limits_.attempts)return result;
    if(transmissions_&&now-last_send_ms_<limits_.retry_ms)return result;
    result.frames=packet_->frames;++transmissions_;last_send_ms_=now;
    return result;
}
}
