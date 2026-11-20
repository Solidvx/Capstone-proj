#pragma once
#include "can_diagnostic.h"
#include <deque>
#include <stdexcept>

namespace capstone::session_v2 {
// Main-loop-owned queue. Limits are explicit deployment settings. One pump
// attempts at most its budget; never retry a failed frame or reuse a sequence.
class DiagnosticTxQueue {
public:
    DiagnosticTxQueue(std::size_t capacity,unsigned frame_budget,std::uint64_t expiry_ms)
        :capacity_(capacity),budget_(frame_budget),expiry_(expiry_ms){
        if(!capacity || capacity>8 || !frame_budget || frame_budget>36 || !expiry_ms)
            throw std::invalid_argument("invalid diagnostic TX limits");
    }
    bool offer(DiagnosticPacket packet,std::uint64_t now){
        if(packet.frames.empty() || packet.frames.size()>36 || queue_.size()>=capacity_){++dropped_;return false;}
        queue_.push_back({std::move(packet),now,0});return true;
    }
    template<class Send> void pump(const Nonce& current_session,std::uint64_t now,Send send){
        unsigned attempted=0;
        while(!queue_.empty() && attempted<budget_){
            auto& item=queue_.front();
            if(item.packet.session_id!=current_session || now<item.enqueued || now-item.enqueued>=expiry_){
                ++dropped_;queue_.pop_front();continue;
            }
            ++attempted;
            if(!send(item.packet.frames[item.next])){++dropped_;queue_.pop_front();continue;}
            if(++item.next==item.packet.frames.size())queue_.pop_front();
        }
    }
    void clear(){dropped_+=queue_.size();queue_.clear();}
    std::size_t pending()const{return queue_.size();}
    std::uint64_t dropped()const{return dropped_;}
private:
    struct Pending {DiagnosticPacket packet;std::uint64_t enqueued;std::size_t next;};
    std::deque<Pending> queue_;std::size_t capacity_;unsigned budget_;std::uint64_t expiry_,dropped_=0;
};
}
