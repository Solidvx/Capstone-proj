#include "can_session_exchange.h"

#include <algorithm>
#include <deque>
#include <iostream>
#include <stdexcept>
#include <string>

using namespace capstone::session_v2;
namespace {
void require(bool condition,const char* message) {
    if (!condition) throw std::runtime_error(message);
}
Key dummyKey() { Key key{}; for(unsigned i=0;i<32;++i)key[i]=i; return key; }
Exchange::NonceSource source(unsigned seed) {
    return [seed]() mutable { Nonce value{};value.fill(static_cast<std::uint8_t>(++seed));return value; };
}
ExchangeLimits limits() { return {20,200,800,60,500,50,64,512,{60,5,100,4,8,4,256},{1000,100,4,64}}; }
std::uint32_t counter(const Frame& frame) {
    std::uint32_t out=0;for(unsigned i=4;i<8;++i)out=(out<<8)|frame.data[i];return out;
}
struct Wire {
    struct Delivery { bool to_ecu; Frame frame; };
    Exchange ecu;
    Exchange ivi;
    explicit Wire(ExchangeLimits bound=limits())
        : ecu(Endpoint::Ecu,dummyKey(),bound,source(0x40)),
          ivi(Endpoint::Ivi,dummyKey(),bound,source(0x41)) {}
    Exchange* ecu_target=&ecu;
    Exchange* ivi_target=&ivi;
    std::deque<Delivery> queue;
    std::uint64_t now=0;
    bool reverse=false;
    std::function<bool(bool,const Frame&)> drop;
    std::vector<Frame> captured_state;
    bool hold_state=false;
    std::vector<AuthenticatedMessage> publications;
    void collect() {
        const auto& batch=ivi_target->lastReceiveOutcome().applied;
        publications.insert(publications.end(),batch.begin(),batch.end());
    }
    void enqueue(bool to_ecu,std::vector<Frame> frames) {
        if (hold_state && !to_ecu && !frames.empty() && frames.front().id==0x104) {
            captured_state=frames;return;
        }
        if(reverse)std::reverse(frames.begin(),frames.end());
        for(const auto& frame:frames) {
            if(!drop || !drop(to_ecu,frame))queue.push_back({to_ecu,frame});
        }
    }
    void pump() {
        unsigned events=0;
        while(!queue.empty()) {
            require(++events<2000,"unbounded immediate protocol replies");
            step();
        }
    }
    void step() {
        require(!queue.empty(),"no queued delivery");
        const auto packet=queue.front();queue.pop_front();++now;
        enqueue(!packet.to_ecu,(packet.to_ecu ? *ecu_target : *ivi_target).receive(packet.frame,now));
        if(!packet.to_ecu)collect();
    }
    void advance(std::uint64_t duration) {
        now+=duration;
        enqueue(false,ecu_target->poll(now));enqueue(true,ivi_target->poll(now));collect();pump();
    }
    void settle(unsigned rounds=50) {
        for(unsigned i=0;i<rounds;++i) {
            pump();
            if(ecu_target->phase()==Phase::Open && ivi_target->phase()==Phase::Open)return;
            now+=20;
            enqueue(false,ecu_target->poll(now));enqueue(true,ivi_target->poll(now));collect();
        }
        pump();
    }
    void open() {
        enqueue(false,ecu.start(now));settle();
        require(ecu.dataOpen() && ivi.dataOpen(),"initial exchange did not open");
    }
};

void cleanAndReversed() {
    for(bool reverse:{false,true}) {
        Wire wire;wire.reverse=reverse;
        require(wire.ecu.publishData(0x100,{},0).empty(),"data sent before session");
        wire.ecu.setCurrentState(Payload{3,1,4,0,0,0,0,0},0);
        wire.open();
        require(wire.ivi.receivedState()==Payload({3,1,4,0,0,0,0,0}),"shutdown state not preserved");
        require(wire.ivi.stateApplications()==1,"state applied multiple times");
        require(wire.ecu.nextCounter()==1,"state did not consume first counter exactly once");
        const auto data=wire.ecu.publishData(0x100,Payload{150,200,0,0,0,0,65,0},++wire.now);
        require(data.size()==2 && counter(data[1])==1,"BMS not released after current receipt");
        const auto event=wire.ecu.publishData(0x101,{},++wire.now);
        require(event.size()==2 && counter(event[1])==2,"candidate global counter not shared");
        require(wire.ecu.setCurrentState(Payload{1,1,3,0,0,0,0,0},++wire.now).empty() && wire.ecu.dataOpen(),
                "ordinary new transition unexpectedly closed data gate");
    }
}

void lostFragments() {
    // REQUEST, each control kind's first fragment, and each state pair frame.
    for(unsigned missing=0;missing<9;++missing) {
        Wire wire;bool dropped=false;
        wire.drop=[&](bool,const Frame& frame) {
            const bool selected=missing<7 ? (frame.id>=0x300 && (frame.data[0]&15)==missing && frame.data[1]==0)
                                            : frame.id==(missing==7 ? 0x104u : 0x105u);
            if(!dropped && selected){dropped=true;return true;}return false;
        };
        wire.open();
        require(dropped,"requested loss case was not exercised");
        require(wire.ecu.nextCounter()==1,"retransmission reset or consumed state counter");
        require(wire.ivi.stateApplications()==1,"retry fabricated a second state application");
    }
}

void oldReceiptCannotOpenLatest() {
    Wire wire;wire.hold_state=true;
    wire.enqueue(false,wire.ecu.start(0));wire.pump();
    require(wire.ecu.phase()==Phase::WaitReceipt,"did not reach latest state barrier");
    const auto initial=wire.captured_state;
    const Payload warning{1,1,1,0,0,0,0,0};
    const auto first_warning=wire.ecu.setCurrentState(warning,++wire.now);
    wire.ecu.setCurrentState(Payload{},++wire.now);
    const auto latest=wire.ecu.setCurrentState(warning,++wire.now);
    require(counter(first_warning[1])==1 && counter(latest[1])==3,"latest generation reused a counter");
    wire.hold_state=false;
    wire.enqueue(false,initial);wire.pump();wire.advance(5);
    require(!wire.ecu.dataOpen(),"old normal receipt opened latest warning");
    wire.enqueue(false,first_warning);wire.pump();wire.advance(5);
    require(!wire.ecu.dataOpen(),"old same-payload warning receipt opened latest generation");
    wire.enqueue(false,latest);wire.pump();wire.advance(5);
    require(wire.ecu.dataOpen(),"latest warning receipt did not open");
    require(wire.ivi.receivedState()==warning,"latest risk snapshot wrong");
}

void confirmAndAckDuplicatesDoNotReset() {
    Wire wire;wire.open();
    Context ctx{1,{}, {}};ctx.nonce_b.fill(0x42);ctx.nonce_a.fill(0x41);
    const auto keys=deriveKeys(dummyKey(),ctx);
    const auto proof=controlTag(keys,ctx,Role::Confirm);
    wire.ecu.publishData(0x100,{},++wire.now);
    const auto before=wire.ecu.nextCounter();
    const auto generation=wire.ecu.generation();
    wire.now+=30;
    wire.enqueue(true,fragment(Kind::Confirm,1,{proof.begin(),proof.end()}));wire.pump();
    require(wire.ecu.nextCounter()==before && wire.ecu.dataOpen(),"duplicate confirm reset live counter/gate");
    require(wire.ecu.generation()==generation && wire.ivi.generation()==1,"duplicate commit changed session generation");
    require(wire.ivi.stateApplications()==1,"duplicate ACK fabricated state");
    wire.now=1000;
    const auto checks=wire.ecu.verifications();
    wire.enqueue(true,fragment(Kind::Confirm,1,{proof.begin(),proof.end()}));wire.pump();
    require(wire.ecu.verifications()==checks,"expired completed cache accepted old confirm");
}

void prolongedLossFailsAndNewAttemptRecovers() {
    Wire wire;
    wire.drop=[](bool,const Frame& frame){return frame.id>=0x300 && (frame.data[0]&15)==5;};
    wire.enqueue(false,wire.ecu.start(0));wire.pump();
    require(wire.ecu.phase()==Phase::WaitReady && !wire.ecu.dataOpen(),"READY loss did not keep gate shut");
    wire.now+=200;
    wire.ecu.poll(wire.now);
    require(wire.ecu.phase()==Phase::Failed && !wire.ecu.dataOpen(),"phase deadline did not fail closed");
    wire.drop={};wire.settle(100);
    require(wire.ecu.dataOpen() && wire.ivi.dataOpen(),"backoff/new nonce attempt failed to recover");
}

void preCommitKeepsOldSessionAndPostCommitCannotFallBack() {
    Wire wire;wire.open();wire.now+=100;
    wire.drop=[](bool,const Frame& frame){return frame.id==0x301 && (frame.data[0]&15)==3;};
    wire.enqueue(true,wire.ivi.start(wire.now));wire.pump();
    require(wire.ecu.phase()==Phase::WaitConfirm && wire.ecu.dataOpen(),"unverified confirm destroyed active session");
    require(wire.ecu.activeContext()->nonce_b[0]==0x42 && wire.ecu.generation()==1,"pending nonce replaced active session identity");
    require(wire.ecu.publishData(0x100,{},++wire.now).size()==2,"old authenticated session unavailable before commit");
    wire.drop={};wire.now+=20;wire.enqueue(false,wire.ecu.poll(wire.now));
    wire.drop=[](bool,const Frame& frame){return frame.id==0x301 && (frame.data[0]&15)==5;};
    wire.enqueue(true,wire.ivi.poll(wire.now));wire.pump();
    require(wire.ecu.phase()==Phase::WaitReady && !wire.ecu.dataOpen(),"valid confirm did not close old data path");
    require(wire.ecu.activeContext()->nonce_b[0]==0x43 && wire.ecu.generation()==2,"commit did not switch identity once");
    wire.now+=200;wire.ecu.poll(wire.now);
    require(wire.ecu.publishData(0x100,{},++wire.now).empty(),"failed committed exchange fell back to old key");
}

void changedStatesDoNotExtendDeadline() {
    Wire wire;wire.hold_state=true;
    wire.enqueue(false,wire.ecu.start(0));wire.pump();
    const auto entered=wire.now;
    for(unsigned i=1;i<6;++i) {
        wire.now=entered+i*30;
        wire.ecu.setCurrentState(i%2 ? Payload{1,1,1,0,0,0,0,0} : Payload{},wire.now);
    }
    wire.now=entered+201;wire.ecu.poll(wire.now);
    require(wire.ecu.phase()==Phase::Failed && !wire.ecu.dataOpen(),"state churn extended phase deadline");
}

void invalidProofAndMetadataCannotCommit() {
    Wire wire;
    wire.drop=[](bool,const Frame& frame){return frame.id==0x301 && (frame.data[0]&15)==3;};
    wire.enqueue(false,wire.ecu.start(0));wire.pump();
    require(wire.ecu.phase()==Phase::WaitConfirm,"test did not stop before confirm");
    Context ctx{1,{}, {}};ctx.nonce_b.fill(0x42);ctx.nonce_a.fill(0x41);
    const auto keys=deriveKeys(dummyKey(),ctx);const auto proof=controlTag(keys,ctx,Role::Confirm);
    auto frames=fragment(Kind::Confirm,1,{proof.begin(),proof.end()});
    frames[0].data[4]^=1;
    for(const auto& frame:frames)wire.ecu.receive(frame,++wire.now);
    require(wire.ecu.phase()==Phase::WaitConfirm,"bad confirm committed session");
    frames=fragment(Kind::Confirm,1,{proof.begin(),proof.end()});
    for(auto frame:frames){frame.extended=true;wire.ecu.receive(frame,++wire.now);}
    require(wire.ecu.phase()==Phase::WaitConfirm,"extended confirm committed session");
    for(const auto& frame:frames)wire.ecu.receive(frame,++wire.now);
    require(wire.ecu.phase()==Phase::WaitReady,"valid confirm not accepted after malformed input");
    require(!wire.ecu.dataOpen() && wire.ecu.nextCounter()==0,"commit boundary not atomic");
}

void nonceFailureAndClockRegression() {
    Exchange bad(Endpoint::Ivi,dummyKey(),limits(),[]{throw std::runtime_error("injected RNG failure");return Nonce{};});
    bool threw=false;try{bad.start(0);}catch(const std::runtime_error&){threw=true;}
    require(threw && bad.phase()==Phase::Failed && !bad.dataOpen(),"nonce failure used fallback");
    Wire wire;wire.open();wire.ecu.poll(wire.now-1);
    require(wire.ecu.phase()==Phase::Failed && !wire.ecu.dataOpen(),"clock regression kept data gate open");
}

void totalDeadlineSurvivesPhaseProgress() {
    auto bound=limits();bound.phase_ms=100;bound.total_ms=150;
    Exchange ecu(Endpoint::Ecu,dummyKey(),bound,source(0x40));
    Exchange ivi(Endpoint::Ivi,dummyKey(),bound,source(0x41));
    auto deliver=[](Exchange& receiver,const std::vector<Frame>& batch,std::uint64_t now) {
        std::vector<Frame> reply;
        for(const auto& frame:batch) {
            const auto tx=receiver.receive(frame,now);reply.insert(reply.end(),tx.begin(),tx.end());
        }
        return reply;
    };
    auto batch=ivi.start(0);
    batch=deliver(ecu,batch,10); // start ECU overall deadline at10
    batch=deliver(ivi,batch,40);
    batch=deliver(ecu,batch,70);
    batch=deliver(ivi,batch,100);
    batch=deliver(ecu,batch,130);
    batch=deliver(ivi,batch,140);
    require(batch.empty(),"state receipt sent before ordered application");
    batch=ivi.poll(145);
    require(!batch.empty() && ecu.phase()==Phase::WaitReceipt,"deadline test never reached receipt");
    deliver(ecu,batch,171); // phase elapsed41 but overall elapsed161
    require(ecu.phase()==Phase::Failed && !ecu.dataOpen(),"phase progression extended total exchange deadline");
}

void endpointRebootsAndOldPairRejection() {
    for(unsigned restarted=1;restarted<=3;++restarted) {
        Wire wire;wire.open();
        Context old{1,{}, {}};old.nonce_b.fill(0x42);old.nonce_a.fill(0x41);
        const auto old_keys=deriveKeys(dummyKey(),old);
        const Payload old_state{3,1,4,0,0,0,0,0};
        const auto old_mac=dataMac(old_keys.at(Role::Data),0x104,0,old_state);
        Payload auth{};std::copy(old_mac.begin(),old_mac.end(),auth.begin());
        auto next_ecu=std::make_unique<Exchange>(Endpoint::Ecu,dummyKey(),limits(),source(0x50));
        auto next_ivi=std::make_unique<Exchange>(Endpoint::Ivi,dummyKey(),limits(),source(0x60));
        if(restarted&1)wire.ecu_target=next_ecu.get();
        if(restarted&2)wire.ivi_target=next_ivi.get();
        wire.now+=100;
        if(restarted&1)wire.enqueue(false,wire.ecu_target->start(wire.now));
        else wire.enqueue(true,wire.ivi_target->start(wire.now));
        wire.settle(100);
        require(wire.ecu_target->dataOpen() && wire.ivi_target->dataOpen(),"endpoint reboot did not establish fresh session");
        const auto applications=wire.ivi_target->stateApplications();
        wire.enqueue(false,{Frame{0x104,old_state},Frame{0x105,auth}});wire.pump();
        require(wire.ivi_target->stateApplications()==applications,"old-key state published after reboot");
        require(wire.ivi_target->receivedState()!=old_state,"old shutdown overwritten current state");
        require(wire.ecu_target->nextCounter()==1,"reboot did not allocate new session state counter");
        require(wire.ecu_target->publishData(0x100,{},++wire.now).size()==2,"replay closed new sender gate");
    }
}

void authenticatedInvalidStateIsNotApplied() {
    Wire wire;wire.hold_state=true;
    wire.enqueue(false,wire.ecu.start(0));wire.pump();
    Context ctx{1,{}, {}};ctx.nonce_b.fill(0x42);ctx.nonce_a.fill(0x41);
    const auto keys=deriveKeys(dummyKey(),ctx);
    const Payload bad{2,1,4,0,0,0,0,0}; // valid tag but critical/reason4 is invalid
    const auto proof=dataMac(keys.at(Role::Data),0x104,0,bad);
    Payload auth{};std::copy(proof.begin(),proof.end(),auth.begin());
    wire.hold_state=false;
    wire.enqueue(false,{Frame{0x104,bad},Frame{0x105,auth}});wire.pump();
    require(wire.ivi.stateApplications()==0 && !wire.ecu.dataOpen(),"invalid authenticated state was applied/acknowledged");
    wire.enqueue(false,wire.captured_state);wire.pump();wire.advance(5);
    require(wire.ivi.stateApplications()==1 && wire.ecu.dataOpen(),"invalid state consumed valid state counter");
    for(const auto payload:{Payload{4,0,0,0,0,0,0,0},Payload{0,0,1,0,0,0,0,0},Payload{0,1,0,0,0,0,0,0},Payload{0,0,0,0,0,0,0,1}})
        require(!validCurrentState(payload),"invalid state semantics accepted");
}

void statePairExpiryAndBudgetBounds() {
    Wire wire;wire.hold_state=true;
    wire.enqueue(false,wire.ecu.start(0));wire.pump();
    wire.hold_state=false;
    const auto original=wire.captured_state;
    wire.enqueue(false,{original[0]});wire.pump();
    wire.now+=60;
    wire.enqueue(false,{original[1]});wire.pump();
    require(!wire.ecu.dataOpen() && wire.ivi.stateApplications()==0,"expired raw state paired with late auth");
    wire.enqueue(false,original);wire.pump();wire.advance(5);
    require(wire.ecu.dataOpen(),"retry after raw expiry failed");
    for(unsigned exhausted=0;exhausted<2;++exhausted) {
        auto bound=limits();
        if(exhausted==0)bound.max_batches=2;
        else bound.max_verifications=1;
        Exchange ecu(Endpoint::Ecu,dummyKey(),bound,source(0x40));
        Exchange ivi(Endpoint::Ivi,dummyKey(),bound,source(0x41));
        std::deque<std::pair<bool,Frame>> pending;
        for(const auto& frame:ecu.start(0))pending.push_back({false,frame});
        std::uint64_t now=0;
        while(!pending.empty()) {
            const auto packet=pending.front();pending.pop_front();
            for(const auto& reply:(packet.first ? ecu : ivi).receive(packet.second,++now))
                pending.push_back({!packet.first,reply});
        }
        require(!ecu.dataOpen(),"exhausted verification/transmission budget opened gate");
        require(ecu.transmissions()<=bound.max_batches && ivi.transmissions()<=bound.max_batches,"transmission budget exceeded");
        require(ecu.verifications()<=bound.max_verifications && ivi.verifications()<=bound.max_verifications,"verification budget exceeded");
    }
}

void rebootDuringEveryExchangePhase() {
    for(unsigned stop=0;stop<8;++stop) {
        for(unsigned restarted=1;restarted<=3;++restarted) {
            Wire wire;
            wire.enqueue(false,wire.ecu.start(0));
            const std::array<Phase,4> a{Phase::WaitChallenge,Phase::WaitConfirm,Phase::WaitReady,Phase::WaitReceipt};
            const std::array<Phase,4> b{Phase::WaitOffer,Phase::WaitAck,Phase::WaitState,Phase::Open};
            unsigned events=0;
            while((stop<4 ? wire.ecu.phase()!=a[stop] : wire.ivi.phase()!=b[stop-4])) {
                require(++events<100,"could not reach requested interrupted phase");
                if(wire.queue.empty()){
                    wire.now+=5;wire.enqueue(false,wire.ecu.poll(wire.now));wire.enqueue(true,wire.ivi.poll(wire.now));wire.collect();
                }else wire.step();
            }
            auto next_ecu=std::make_unique<Exchange>(Endpoint::Ecu,dummyKey(),limits(),source(0x50));
            auto next_ivi=std::make_unique<Exchange>(Endpoint::Ivi,dummyKey(),limits(),source(0x60));
            if(restarted&1)wire.ecu_target=next_ecu.get();
            if(restarted&2)wire.ivi_target=next_ivi.get();
            wire.now+=50;
            // Retain the old in-flight frames: a reboot is not a bus flush.
            if(restarted&1)wire.enqueue(false,wire.ecu_target->start(wire.now));
            else wire.enqueue(true,wire.ivi_target->start(wire.now));
            wire.settle(150);
            if(!wire.ecu_target->dataOpen() || !wire.ivi_target->dataOpen()) {
                std::cerr<<"interrupted phase="<<stop<<" reboot mask="<<restarted<<'\n';
                throw std::runtime_error("mid-exchange reboot failed to recover within test schedule");
            }
            require(wire.ivi_target->receivedState()==Payload{},"stale intermediate snapshot applied after reboot");
        }
    }
}

void fullBmsAndEventReceivePath(){
    Wire wire;wire.reverse=true;wire.open();
    require(!wire.ivi.lastAuthenticatedBmsAt(),"state receipt fabricated authenticated BMS freshness");
    const Payload bms{150,200,0x10,0x68,0xff,0xec,65,0};
    const Payload event{1,3,4,150,101,0,0,0};
    const auto normal=wire.ecu.publishData(0x100,bms,++wire.now);
    const auto risk=wire.ecu.publishData(0x101,event,++wire.now);
    wire.enqueue(false,risk);wire.enqueue(false,normal);wire.pump();
    const auto pair_at=wire.ivi.lastAuthenticatedBmsAt();
    require(pair_at && *pair_at<=wire.now,"complete BMS not authenticated before publication");
    require(wire.publications.size()==1,"data published before ordering deadline");
    wire.advance(5);
    require(wire.publications.size()==3 && wire.publications[1].id==0x100 && wire.publications[1].counter==1 &&
            wire.publications[2].id==0x101 && wire.publications[2].counter==2,"actual exchange receiver lost shared-counter order");
    require(wire.ivi.lastAuthenticatedBmsAt()==pair_at && wire.publications[1].applied_ms>*pair_at,
            "publication time replaced actual authenticated RX time");
}

void earlyAuthenticatedBmsCannotBypassStateBarrier(){
    Wire wire;wire.hold_state=true;
    wire.enqueue(false,wire.ecu.start(0));wire.pump();
    Context ctx{1,{}, {}};ctx.nonce_b.fill(0x42);ctx.nonce_a.fill(0x41);
    const auto keys=deriveKeys(dummyKey(),ctx);const Payload bms{150,200,0x10,0x68,0xff,0xec,65,0};
    const auto mac=dataMac(keys.at(Role::Data),0x100,1,bms);
    Payload auth{};std::copy(mac.begin(),mac.end(),auth.begin());auth[7]=1;
    wire.enqueue(false,{Frame{0x100,bms},Frame{0x102,auth}});wire.pump();
    require(wire.publications.empty() && !wire.ivi.lastAuthenticatedBmsAt(),"authenticated BMS bypassed current-state barrier");
    require(!wire.ivi.lastReceiveOutcome().decisions.empty() &&
            wire.ivi.lastReceiveOutcome().decisions.back().reason==ReceiveReason::BeforeState,"early data not classified");
    wire.hold_state=false;wire.enqueue(false,wire.captured_state);wire.settle();
    require(wire.ecu.dataOpen() && wire.publications.size()==1 && wire.publications[0].id==0x104,
            "early data leaked from a pre-state queue");
}

void commitDropsOldOrderedQueueAndRxAge(){
    auto bound=limits();bound.phase_ms=1000;bound.total_ms=4000;bound.cache_ms=2000;bound.receive.order_ms=150;
    Wire wire(bound);wire.open();
    const Payload bms{150,200,0x10,0x68,0xff,0xec,65,0};
    wire.enqueue(false,wire.ecu.publishData(0x100,bms,++wire.now));wire.pump();
    require(wire.ivi.lastAuthenticatedBmsAt().has_value() && wire.publications.size()==1,"old BMS was not pending");
    wire.enqueue(true,wire.ivi.start(++wire.now));wire.settle(150);
    require(wire.ecu.generation()==2 && wire.ivi.generation()==2 && wire.ecu.dataOpen(),"rekey did not complete");
    require(!wire.ivi.lastAuthenticatedBmsAt(),"new session inherited old authenticated RX age");
    wire.advance(200);
    require(std::none_of(wire.publications.begin(),wire.publications.end(),[](const auto& message){return message.id==0x100;}),
            "old generation's queued BMS applied after key switch");
    require(wire.publications.size()==2 && wire.publications[1].generation==2,"new current state not applied under new generation");
}
void protectedOverflowRequestsNewSessionWithoutLoweringRisk(){
    auto bound=limits();bound.receive.order_ms=20;bound.receive.protected_slots=1;
    Wire wire(bound);wire.open();
    wire.ecu.setCurrentState(Payload{3,1,4,0,0,0,0,0},++wire.now);
    const Payload event{1,3,4,150,101,0,0,0};
    wire.enqueue(false,wire.ecu.publishData(0x101,event,++wire.now));wire.pump();
    wire.enqueue(false,wire.ecu.publishData(0x101,event,++wire.now));wire.pump();
    require(wire.ivi.lastReceiveOutcome().failed && wire.ivi.phase()==Phase::Failed && !wire.ivi.dataOpen(),
            "protected overflow did not close authenticated receive session");
    require(wire.ivi.lastReceiveOutcome().generation==1 && wire.ivi.lastReceiveContext() && !wire.ivi.activeContext(),
            "fatal receive result lost its original session scope");
    require(wire.ivi.receivedState()==Payload{},"unreceived shutdown was invented on queue failure");
    wire.advance(50);wire.settle(100);
    require(wire.ivi.dataOpen() && wire.ecu.dataOpen() && wire.ivi.generation()==2,"protected overflow failed to re-establish session");
    require(wire.ivi.receivedState()==Payload({3,1,4,0,0,0,0,0}),"resync lowered actual shutdown risk");
}
}
int main() {
    try {
        cleanAndReversed();lostFragments();oldReceiptCannotOpenLatest();confirmAndAckDuplicatesDoNotReset();
        prolongedLossFailsAndNewAttemptRecovers();preCommitKeepsOldSessionAndPostCommitCannotFallBack();
        changedStatesDoNotExtendDeadline();invalidProofAndMetadataCannotCommit();nonceFailureAndClockRegression();
        totalDeadlineSurvivesPhaseProgress();endpointRebootsAndOldPairRejection();
        authenticatedInvalidStateIsNotApplied();statePairExpiryAndBudgetBounds();
        rebootDuringEveryExchangePhase();
        fullBmsAndEventReceivePath();earlyAuthenticatedBmsCannotBypassStateBarrier();commitDropsOldOrderedQueueAndRxAge();
        protectedOverflowRequestsNewSessionWithoutLoweringRisk();
        std::cout<<"PASS 18 exchange scenario groups including 9 first-frame loss and 27 endpoint reboot cases\n";return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
