#include "can_session_receiver.h"

#include <algorithm>
#include <iostream>
#include <stdexcept>

using namespace capstone::session_v2;
namespace {
void require(bool condition,const char* message){if(!condition)throw std::runtime_error(message);}
template<class Function>void rejects(Function function){
    bool rejected=false;try{function();}catch(const std::exception&){rejected=true;}
    require(rejected,"invalid receiver configuration accepted");
}
std::shared_ptr<SessionKeys> keys(unsigned nonce=0x41){
    Key key{};for(unsigned i=0;i<32;++i)key[i]=i;
    Context ctx{1,{}, {}};ctx.nonce_b.fill(0x42);ctx.nonce_a.fill(nonce);
    return std::make_shared<SessionKeys>(deriveKeys(key,ctx));
}
ReceiveLimits limits(){return {100,5,20,4,8,4,256};}
Payload bms(unsigned soc=150){return Payload{static_cast<std::uint8_t>(soc),200,0x10,0x68,0xff,0xec,65,0};}
Payload event(){return Payload{1,3,4,150,101,0,0,0};}
std::array<Frame,2> pair(const SessionKeys& key,std::uint16_t id,std::uint32_t counter,Payload raw){
    const auto mac=dataMac(key.at(Role::Data),id,counter,raw);
    Payload auth{};std::copy(mac.begin(),mac.end(),auth.begin());
    for(unsigned i=0;i<4;++i)auth[4+i]=static_cast<std::uint8_t>(counter>>(24-i*8));
    const auto auth_id=id==0x104 ? 0x105 : id+2;
    return {Frame{id,raw},Frame{static_cast<std::uint32_t>(auth_id),auth}};
}
ReceiveOutcome feed(OrderedReceiver& receiver,const std::array<Frame,2>& frames,std::uint64_t now){
    receiver.receive(frames[0],now);return receiver.receive(frames[1],now+1);
}
bool has(const ReceiveOutcome& outcome,ReceiveReason reason){
    return std::any_of(outcome.decisions.begin(),outcome.decisions.end(),[&](const auto& d){return d.reason==reason;});
}

void reversedGlobalOrderAndClocks(){
    auto key=keys();OrderedReceiver receiver(key,7,limits(),0);
    feed(receiver,pair(*key,0x100,11,bms()),0);
    feed(receiver,pair(*key,0x101,10,event()),2);
    auto state=pair(*key,0x104,12,Payload{3,1,4,0,0,0,0,0});
    receiver.receive(state[1],4);receiver.receive(state[0],5);
    auto result=receiver.poll(6);
    require(result.applied.size()==3,"reversed complete packets not batched");
    for(unsigned i=0;i<3;++i)require(result.applied[i].counter==10+i,"global counter order not preserved");
    const auto& message=result.applied[0];
    require(message.raw_received_ms==2 && message.auth_received_ms==3 && message.authenticated_ms==3 &&
            message.applied_ms==6 && message.generation==7,"receive and publication clocks were overwritten");
    require(receiver.lastAuthenticatedBmsAt()==1,"queue flush refreshed BMS receive age");
}
void lateLowerNumberAndBoundary(){
    auto key=keys();OrderedReceiver receiver(key,1,limits(),0);
    feed(receiver,pair(*key,0x100,11,bms()),0);
    auto low=pair(*key,0x101,10,event());
    auto due=receiver.receive(low[0],6); // expiry wins at exact batch deadline
    require(due.applied.size()==1 && due.applied[0].counter==11,"deadline was extended by late lower original");
    auto result=receiver.receive(low[1],7);
    require(has(result,ReceiveReason::Replay) && receiver.lastAppliedCounter()==11,"late number rolled counter back");
    require(result.decisions.back().mac_verified,"replay disposition lacks actual MAC evidence");
}
void everyMacBitMutation(){
    auto key=keys();
    for(unsigned bit=0;bit<32;++bit){
        OrderedReceiver receiver(key,1,limits(),0);
        auto frames=pair(*key,0x100,0,bms());frames[1].data[bit/8]^=1u<<(bit%8);
        feed(receiver,frames,0);auto result=receiver.poll(101);
        require(result.applied.empty() && !receiver.lastAppliedCounter() && !receiver.lastAuthenticatedBmsAt(),"mutated MAC advanced receive state");
        require(has(result,ReceiveReason::AuthExpired),"unmatched auth not expired");
    }
}
void exactCounterWindows(){
    auto key=keys();OrderedReceiver first(key,1,limits(),0);
    require(has(feed(first,pair(*key,0x100,100,bms()),0),ReceiveReason::Ahead),"initial counter100 accepted");
    feed(first,pair(*key,0x100,99,bms()),2);require(first.poll(8).applied.size()==1,"initial counter99 rejected");
    OrderedReceiver receiver(key,1,limits(),0);
    feed(receiver,pair(*key,0x100,0,bms()),0);receiver.poll(6);
    require(has(feed(receiver,pair(*key,0x100,101,bms()),7),ReceiveReason::Ahead),"delta101 accepted");
    feed(receiver,pair(*key,0x100,100,bms()),9);auto accepted=receiver.poll(15);
    require(accepted.applied.size()==1 && accepted.applied[0].counter==100,"delta100 rejected");
    require(has(feed(receiver,pair(*key,0x100,0,bms()),16),ReceiveReason::Replay),"wrapped counter accepted in same session");
}
void hundredOneBitMutationsDoNotPublishOrConsumeFreshness(){
    auto key=keys();OrderedReceiver receiver(key,1,limits(),0);
    const auto original=pair(*key,0x100,0,bms());
    unsigned applied=0,expired=0;
    for(unsigned attempt=0;attempt<100;++attempt){
        const auto at=std::uint64_t(attempt)*200;
        auto altered=original;const unsigned bit=attempt%32;
        altered[1].data[bit/8]^=static_cast<std::uint8_t>(1u<<(bit%8));
        applied+=feed(receiver,altered,at).applied.size();
        require(receiver.macChecksInWindow()>0,"tampered candidate skipped actual MAC checking");
        const auto due=receiver.poll(at+101);applied+=due.applied.size();
        expired+=has(due,ReceiveReason::AuthExpired)?1u:0u;
        require(!receiver.lastAppliedCounter() && !receiver.lastAuthenticatedBmsAt(),"failed authentication refreshed receive state");
    }
    require(applied==0 && expired==100,"hundred modified authentications were not all discarded");
    feed(receiver,original,20000);
    require(receiver.poll(20006).applied.size()==1 && receiver.lastAppliedCounter()==0,
            "failed authentication consumed the next valid original");
    std::cout<<"TC-SEC-002 session software: injected=100 applied=0 expired_auth=100 valid_after=1\n";
}
void duplicatesCannotExtendPairDeadline(){
    auto key=keys();OrderedReceiver receiver(key,1,limits(),0);
    const auto frames=pair(*key,0x100,0,bms());
    receiver.receive(frames[0],0);receiver.receive(frames[0],99);
    const auto result=receiver.receive(frames[1],100);
    require(has(result,ReceiveReason::OriginalExpired),"duplicate postponed original expiry");
    require(receiver.poll(200).applied.empty() && !receiver.lastAppliedCounter(),"late auth paired with expired original");
}
void reservationAndGeneralOverflow(){
    auto key=keys();auto bound=limits();bound.order_ms=20;bound.general_slots=2;bound.protected_slots=1;
    OrderedReceiver receiver(key,1,bound,0);
    feed(receiver,pair(*key,0x100,0,bms(140)),0);
    feed(receiver,pair(*key,0x100,1,bms(150)),2);
    const auto rejected=feed(receiver,pair(*key,0x100,2,bms(160)),4);
    require(has(rejected,ReceiveReason::GeneralFull) && !receiver.failed(),"normal queue overflow did not reject only new entry");
    require(receiver.lastAuthenticatedBmsAt()==5,"authenticated RX evidence not distinct from publication");
    feed(receiver,pair(*key,0x100,2,bms(160)),6);
    require(receiver.lastAuthenticatedBmsAt()==5,"repeat of rejected counter refreshed RX age");
    feed(receiver,pair(*key,0x101,3,event()),8);
    require(receiver.queuedGeneral()==2 && receiver.queuedProtected()==1,"BMS occupied protected capacity");
    auto result=receiver.poll(21);
    require(result.applied.size()==3 && result.applied[2].id==0x101 && result.applied[2].counter==3,"reserved event lost or reordered");
}
void protectedOverflowFailsPreservingPublishedHistory(){
    auto key=keys();auto bound=limits();bound.order_ms=20;bound.protected_slots=1;
    OrderedReceiver receiver(key,1,bound,0);
    feed(receiver,pair(*key,0x100,0,bms()),0);auto published=receiver.poll(21);
    require(published.applied.size()==1,"precondition BMS not published");
    feed(receiver,pair(*key,0x101,1,event()),22);
    auto result=feed(receiver,pair(*key,0x104,2,Payload{}),24);
    require(result.failed && has(result,ReceiveReason::ProtectedFull) && receiver.lastAppliedCounter()==0,"protected overflow did not fail preserving last good counter");
    require(receiver.poll(100).applied.empty() && receiver.queuedProtected()==0,"failed session later published queued risk");
}
void authenticatedConflictAndIdenticalDuplicate(){
    auto key=keys();
    for(unsigned variant=0;variant<3;++variant){
        OrderedReceiver receiver(key,1,limits(),0);
        feed(receiver,pair(*key,0x100,0,bms()),0);
        const auto raw=variant==0 ? bms(151) : variant==1 ? event() : bms(201);
        auto result=feed(receiver,pair(*key,variant==1 ? 0x101 : 0x100,0,raw),2);
        require(result.failed && has(result,ReceiveReason::Conflict),"authenticated same-number conflict not fatal");
        require(receiver.poll(10).applied.empty(),"conflicting session published queued data");
    }
    OrderedReceiver duplicate(key,1,limits(),0);
    feed(duplicate,pair(*key,0x100,0,bms()),0);
    require(has(feed(duplicate,pair(*key,0x100,0,bms()),2),ReceiveReason::Duplicate),"identical queued duplicate not recognized");
    require(duplicate.poll(6).applied.size()==1,"duplicate postponed or duplicated publication");
}
void badSemanticsDoNotConsumeCounter(){
    auto key=keys();OrderedReceiver receiver(key,1,limits(),0);
    require(has(feed(receiver,pair(*key,0x100,0,bms(201)),0),ReceiveReason::Semantic),"invalid BMS passed");
    auto invalid=event();invalid[2]=0;
    require(has(feed(receiver,pair(*key,0x101,0,invalid),2),ReceiveReason::Semantic),"reason0 transition passed");
    feed(receiver,pair(*key,0x100,0,bms()),4);
    const auto result=receiver.poll(10);
    require(result.applied.size()==1 && result.applied[0].counter==0,"semantic rejection consumed counter");
}
void budgetDoesNotFabricateFreshness(){
    auto key=keys();auto bound=limits();bound.max_mac_checks=1;
    OrderedReceiver receiver(key,1,bound,0);
    const auto good=pair(*key,0x100,0,bms());
    receiver.receive(Frame{0x100,bms(140)},0);receiver.receive(good[1],1);
    auto limited=receiver.receive(good[0],2);
    require(has(limited,ReceiveReason::MacBudget) && receiver.macChecksInWindow()==1,"MAC budget exceeded");
    require(!receiver.lastAuthenticatedBmsAt(),"unverified pair refreshed RX age");
    receiver.poll(100); // interfering original expires, old auth is still within100ms
    require(receiver.lastAuthenticatedBmsAt()==2,"delayed MAC verification pretended data arrived now");
    auto result=receiver.poll(105);
    require(result.applied.size()==1 && result.applied[0].authenticated_ms==100 &&
            result.applied[0].raw_received_ms==2 && result.applied[0].auth_received_ms==1,"verification/arrival clocks conflated");
}
void replayDoesNotConsumeNextIdenticalOriginal(){
    auto key=keys();OrderedReceiver receiver(key,1,limits(),0);
    const auto old=pair(*key,0x100,0,bms());feed(receiver,old,0);receiver.poll(6);
    receiver.receive(old[0],7);
    require(has(receiver.receive(old[1],8),ReceiveReason::Replay),"old auth not rejected");
    require(receiver.lastAuthenticatedBmsAt()==1,"replay refreshed authenticated RX age");
    auto next=pair(*key,0x100,1,bms());receiver.receive(next[1],9);
    const auto result=receiver.poll(14);
    require(result.applied.size()==1 && result.applied[0].counter==1 && result.applied[0].raw_received_ms==7,"replay consumed original needed by fresh auth");
}
void reversePairingAcrossMultipleCandidates(){
    auto key=keys();OrderedReceiver receiver(key,1,limits(),0);
    const auto a=pair(*key,0x100,10,bms(100)),b=pair(*key,0x100,11,bms(110));
    receiver.receive(b[1],0);receiver.receive(a[1],1);receiver.receive(a[0],2);receiver.receive(b[0],3);
    const auto result=receiver.poll(7);
    require(result.applied.size()==2 && result.applied[0].counter==10 && result.applied[0].payload==bms(100) &&
            result.applied[1].counter==11 && result.applied[1].payload==bms(110),"auth-first pairing selected wrong original");
    OrderedReceiver reordered(key,1,limits(),0);
    feed(reordered,b,0);feed(reordered,a,2);
    require(reordered.lastAuthenticatedBmsAt()==3,"new lower ordinal's later authentic arrival was ignored");
    feed(reordered,b,4);
    require(reordered.lastAuthenticatedBmsAt()==3,"duplicate larger ordinal refreshed RX age");
}
void metadataAndPendingBounds(){
    auto key=keys();OrderedReceiver receiver(key,1,limits(),0);
    auto normal=pair(*key,0x100,0,bms());
    for(unsigned i=0;i<6;++i){
        auto frame=normal[0];
        switch(i){case 0:frame.extended=true;break;case 1:frame.remote=true;break;case 2:frame.error=true;break;
            case 3:frame.dlc=7;break;case 4:frame.id=0x800;break;case 5:frame.id=0x200;break;}
        auto result=receiver.receive(frame,i);
        require(has(result,i==5 ? ReceiveReason::UnsupportedId : ReceiveReason::Metadata),"bad frame accepted");
    }
    for(unsigned i=0;i<4;++i)receiver.receive(Frame{0x100,bms(100+i)},10+i);
    require(has(receiver.receive(normal[0],14),ReceiveReason::PendingFull),"pending original cap exceeded");
    require(receiver.macChecksInWindow()==0 && !receiver.lastAppliedCounter(),"metadata changed cryptographic history");
}
void generationIsolationAndClockFailure(){
    auto old=keys(),next=keys(0x51);
    OrderedReceiver before(old,1,limits(),0);feed(before,pair(*old,0x100,0,bms()),0);
    OrderedReceiver after(next,2,limits(),10);
    feed(after,pair(*old,0x100,0,bms()),10);require(after.poll(16).applied.empty(),"old key accepted by new session");
    feed(after,pair(*next,0x100,0,bms(151)),17);auto result=after.poll(23);
    require(result.applied.size()==1 && result.applied[0].generation==2 && result.applied[0].counter==0,"fresh generation did not isolate old queue/counter");
    auto failed=after.poll(22);
    require(failed.failed && has(failed,ReceiveReason::ClockError) && after.poll(24).failed,"clock failure reopened old session");
}
void invalidLimitsAreRejected(){
    auto key=keys();
    auto bound=limits();bound.order_ms=0;rejects([&]{OrderedReceiver r(key,1,bound,0);});
    bound=limits();bound.protected_slots=0;rejects([&]{OrderedReceiver r(key,1,bound,0);});
    bound=limits();bound.candidates_per_stream=17;rejects([&]{OrderedReceiver r(key,1,bound,0);});
    rejects([&]{OrderedReceiver r(key,0,limits(),0);});rejects([&]{OrderedReceiver r(nullptr,1,limits(),0);});
}
void ambiguousTruncatedMacFailsInsteadOfChoosingArrivalOrder(){
    // Precomputed using only this file's public dummy key/context. Both valid
    // BMS bodies have MAC2400d661 for ID0x100/counter0. No runtime brute force.
    auto key=keys();
    const Payload a{0x96,0xc8,0,0,0x1c,0xaf,0x41,0};
    const Payload b{0x96,0xc8,0,0,0x34,0xfc,0x41,0};
    auto first=pair(*key,0x100,0,a),second=pair(*key,0x100,0,b);
    require(first[1].data==second[1].data,"public collision fixture is invalid");
    for(bool reverse:{false,true}){
        OrderedReceiver receiver(key,1,limits(),0);
        receiver.receive(reverse ? second[0] : first[0],0);
        receiver.receive(reverse ? first[0] : second[0],1);
        auto result=receiver.receive(first[1],2);
        require(result.failed && has(result,ReceiveReason::Conflict) && !receiver.lastAppliedCounter(),
                "ambiguous MAC selected an arbitrary original");
    }
}
void ownerBacklogPreservesArrivalAndExpiresOutOfOrderCandidates(){
    auto key=keys();const auto frames=pair(*key,0x100,0,bms());
    OrderedReceiver receiver(key,1,limits(),0);
    receiver.poll(8);
    receiver.receive(frames[0],10,1);receiver.receive(frames[1],11,2);
    auto result=receiver.poll(16);
    require(!result.failed && result.applied.size()==1 && receiver.lastAuthenticatedBmsAt()==2 &&
            result.applied[0].raw_received_ms==1 && result.applied[0].auth_received_ms==2 &&
            result.applied[0].authenticated_ms==11,"owner backlog replaced arrival or caused clock failure");
    OrderedReceiver expired(key,1,limits(),0);
    require(has(expired.receive(frames[0],100,0),ReceiveReason::OriginalExpired),"already expired captured original admitted");
    require(has(expired.receive(frames[1],101,1),ReceiveReason::AuthExpired),"already expired captured auth admitted");
    OrderedReceiver reordered(key,1,limits(),0);
    reordered.receive(Frame{0x100,bms(140)},90,90);
    reordered.receive(frames[0],95,0); // older captured entry behind a newer one
    require(has(reordered.receive(frames[1],101,100),ReceiveReason::OriginalExpired),"non-front stale original not expired");
    require(!reordered.lastAuthenticatedBmsAt(),"stale backlog refreshed authenticated RX");
    reordered.receive(frames[0],102,102);
    require(reordered.poll(107).applied.size()==1,"fresh retry after out-of-order expiry failed");
    require(has(reordered.receive(frames[0],108,109),ReceiveReason::Metadata),"future capture clock accepted");
}
}
int main(){
    try{
        reversedGlobalOrderAndClocks();lateLowerNumberAndBoundary();everyMacBitMutation();exactCounterWindows();
        hundredOneBitMutationsDoNotPublishOrConsumeFreshness();
        duplicatesCannotExtendPairDeadline();reservationAndGeneralOverflow();protectedOverflowFailsPreservingPublishedHistory();
        authenticatedConflictAndIdenticalDuplicate();badSemanticsDoNotConsumeCounter();budgetDoesNotFabricateFreshness();
        replayDoesNotConsumeNextIdenticalOriginal();reversePairingAcrossMultipleCandidates();metadataAndPendingBounds();
        generationIsolationAndClockFailure();invalidLimitsAreRejected();
        ambiguousTruncatedMacFailsInsteadOfChoosingArrivalOrder();
        ownerBacklogPreservesArrivalAndExpiresOutOfOrderCandidates();
        std::cout<<"PASS 18 ordered receiver scenario groups including 32 MAC bit mutations, 100 consecutive tampered authentications and a public tag collision\n";return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
