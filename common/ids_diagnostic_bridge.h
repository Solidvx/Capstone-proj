#pragma once
#include "ids_submission_order.h"
#include "diagnostic_tx_queue.h"
#include "can_session_exchange.h"

namespace capstone::session_v2 {
// Serialized by the ECU main loop. Socket authorization belongs to its caller.
class IdsDiagnosticBridge {
public:
    IdsDiagnosticBridge(std::size_t capacity,unsigned budget,std::uint64_t expiry)
        :tx_(capacity,budget,expiry){}
    bool submit(Exchange& exchange,const IdsDiagnosticSubmission& submission,std::uint64_t now){
        synchronize(exchange);
        if(!order_.accept(submission,now)){++rejected_;return false;}
        if(!exchange.dataOpen()){++unavailable_;return false;}
        auto packet=exchange.makeDiagnostic(submission.kind,submission.body);
        if(!packet){++unavailable_;return false;}
        return tx_.offer(std::move(*packet),now);
    }
    template<class Send>void pump(Exchange& exchange,std::uint64_t now,Send send){
        synchronize(exchange);
        if(!exchange.dataOpen() || !exchange.activeContext()){tx_.clear();return;}
        tx_.pump(contextId(*exchange.activeContext()),now,send);
    }
    std::uint64_t rejected()const{return rejected_;}
    std::uint64_t unavailable()const{return unavailable_;}
    std::uint64_t dropped()const{return tx_.dropped();}
    std::size_t pending()const{return tx_.pending();}
private:
    void synchronize(const Exchange& exchange){
        if(generation_!=exchange.generation()){tx_.clear();generation_=exchange.generation();}
    }
    IdsSubmissionOrder order_;DiagnosticTxQueue tx_;
    std::uint64_t generation_=0,rejected_=0,unavailable_=0;
};
}
