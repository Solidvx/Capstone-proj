#pragma once
#include "can_session_exchange.h"
#include "diagnostic_tx_queue.h"

namespace capstone::session_v2 {
// Owner-thread only. At most one pending message and one frame per pump.
// Call offer on normal state updates; pump never waits for peer or disk I/O.
class ProtectionPublisher {
public:
    ProtectionPublisher(std::uint64_t heartbeat_ms,std::uint64_t expiry_ms)
        :tx_(1,1,expiry_ms),heartbeat_ms_(heartbeat_ms){
        if(!heartbeat_ms)throw std::invalid_argument("explicit protection heartbeat required");
    }
    bool offer(Exchange& exchange,const std::optional<std::vector<std::uint8_t>>& body,std::uint64_t now){
        if(!synchronize(exchange,now))return false;
        if(!body){tx_.clear();last_body_.reset();last_offer_.reset();return false;}
        if(tx_.pending())return false; // retain latest state at the owner, not in another queue
        if(last_body_==body && last_offer_ && now-*last_offer_<heartbeat_ms_)return false;
        try{
            auto packet=exchange.makeDiagnostic(DiagnosticKind::ProtectionStatus,*body);
            if(!packet || !tx_.offer(std::move(*packet),now))return false;
            last_body_=body;last_offer_=now;return true;
        }catch(const std::exception&){
            disabled_=true;tx_.clear();++failures_;return false;
        }
    }
    template<class Send>void pump(Exchange& exchange,std::uint64_t now,Send send){
        if(synchronize(exchange,now))tx_.pump(contextId(*exchange.activeContext()),now,send);
    }
    std::size_t pending()const{return tx_.pending();}
    std::uint64_t dropped()const{return tx_.dropped();}
    std::uint64_t failures()const{return failures_;}
private:
    bool synchronize(const Exchange& exchange,std::uint64_t now){
        if(generation_!=exchange.generation()){
            tx_.clear();last_body_.reset();last_offer_.reset();last_now_.reset();
            generation_=exchange.generation();disabled_=false;
        }
        if(last_now_ && now<*last_now_){
            if(!disabled_)++failures_;
            disabled_=true;tx_.clear();
        }
        last_now_=now;
        if(!exchange.dataOpen() || !exchange.activeContext()){
            tx_.clear();last_body_.reset();last_offer_.reset();return false;
        }
        return !disabled_;
    }
    DiagnosticTxQueue tx_;
    std::uint64_t heartbeat_ms_,generation_=0,failures_=0;
    bool disabled_=false;
    std::optional<std::uint64_t> last_offer_,last_now_;
    std::optional<std::vector<std::uint8_t>> last_body_;
};
}
