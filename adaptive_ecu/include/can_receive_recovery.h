#pragma once
#include "can_cdd.h"
#include "task_recovery.h"

// Owner-thread adapter. Session keys/counters and the socket remain owned by
// main; restarting only the receive loop must never reset authentication state.
class CanReceiveRecovery : private RecoverableTask {
public:
    explicit CanReceiveRecovery(SocketCanCdd& driver,std::uint64_t now)
        : driver_(driver),recovery_(*this,{1000,3000,1}),checked_(now),progress_at_(now) {}
    TaskRecovery::Event poll(std::uint64_t now) {
        const auto health=driver_.receiveHealth();
        if(health.progress!=progress_){progress_=health.progress;progress_at_=now;}
        if(now>=checked_ && now-checked_>=1000){
            checked_=now;
            if(recovery_.state()==TaskRecovery::State::Idle &&
               (health.faulted || health.stopped || (now>=progress_at_ && now-progress_at_>=3000)))
                recovery_.notifyTimeout(now);
        }
        // Responsive reads without traffic mean connection waiting. A stopped
        // or stuck loop cannot renew this deadline.
        if(recovery_.state()==TaskRecovery::State::AwaitingHeartbeat && !health.faulted &&
           !health.stopped && !health.frames && now>=progress_at_ && now-progress_at_<1000)
            recovery_.awaitingInput(now);
        return recovery_.poll(now);
    }
    TaskRecovery::State state()const{return recovery_.state();}
    unsigned attempts()const{return recovery_.attempts();}
    unsigned failures()const{return recovery_.consecutiveFailures();}
    std::uint64_t generation()const{return recovery_.generation();}
private:
    void requestStop()override{driver_.requestReceiveStop();}
    bool joinIfStopped()override{return driver_.reapReceiveIfStopped();}
    // The loop owns no calculation/session snapshot. Reuse the still-owned
    // socket/callback; all authenticated state remains in the main owner.
    bool snapshotValid(std::uint64_t,std::uint64_t)override{return true;}
    bool startFromSnapshot(std::uint64_t generation)override{
        generation_=generation;
        try{driver_.startReceive();}catch(...){return false;}
        progress_=0;
        return !driver_.receiveHealth().stopped;
    }
    bool completedWork(std::uint64_t generation)override{
        const auto health=driver_.receiveHealth();
        return generation==generation_ && !health.faulted && !health.stopped && health.frames>0;
    }
    SocketCanCdd& driver_;
    TaskRecovery recovery_;
    std::uint64_t generation_=0,checked_,progress_at_,progress_=0;
};
