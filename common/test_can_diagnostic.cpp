#include "can_diagnostic.h"
#include "ids_diagnostic_ipc.h"
#include "diagnostic_tx_queue.h"
#include "ids_diagnostic_bridge.h"
#include "ids_peer_diagnostic.h"
#include "can_session_receiver.h"
#include "can_session_exchange.h"
#include "can_restart_notice.h"
#include "protection_publisher.h"
#include "physical_measurement.h"

#include <algorithm>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <deque>
#include <sstream>
#include <stdexcept>

using namespace capstone::session_v2;
namespace {
using Bytes=std::vector<std::uint8_t>;
void require(bool condition,const char* message){if(!condition)throw std::runtime_error(message);}
template<class Call>void rejects(Call call){
    bool rejected=false;try{call();}catch(const std::invalid_argument&){rejected=true;}
    require(rejected,"invalid diagnostic policy accepted");
}
template<class BytesType>std::string hex(const BytesType& bytes){
    std::ostringstream out;out<<std::hex<<std::setfill('0');
    for(auto byte:bytes)out<<std::setw(2)<<static_cast<unsigned>(byte);return out.str();
}
Bytes unhex(const std::string& value){
    require(value.size()%2==0,"odd input hex");Bytes result;
    for(unsigned i=0;i<value.size();i+=2)result.push_back(static_cast<std::uint8_t>(std::stoul(value.substr(i,2),nullptr,16)));
    return result;
}
Context context(){Context ctx{0x1234,{}, {}};ctx.nonce_b.fill(0x42);ctx.nonce_a.fill(0x41);return ctx;}
std::shared_ptr<SessionKeys> keys(){Key key{};for(unsigned i=0;i<32;++i)key[i]=i;return std::make_shared<SessionKeys>(deriveKeys(key,context()));}
struct Input{std::string name;std::uint16_t sender;std::uint32_t sequence;DiagnosticKind kind;Bytes body;};
std::vector<Input> inputs(){
    std::ifstream file(DIAGNOSTIC_INPUT_PATH);require(static_cast<bool>(file),"diagnostic input fixture missing");
    std::vector<Input> result;std::string name,body;unsigned sender,sequence,kind;
    while(file>>name>>sender>>sequence>>kind>>body)
        result.push_back({name,static_cast<std::uint16_t>(sender),sequence,static_cast<DiagnosticKind>(kind),unhex(body)});
    require(result.size()==8,"diagnostic fixture count");return result;
}
Bytes envelope(const DiagnosticPacket& packet,unsigned length){
    Bytes result;for(const auto& frame:packet.frames)result.insert(result.end(),frame.data.begin()+4,frame.data.end());
    result.resize(length);return result;
}
std::map<std::string,std::string> vectors(){
    const auto key=keys();const auto ctx=context();
    std::map<std::string,std::string> out{{"context",hex(contextId(ctx))},
        {"key.diag-ecu",hex(key->at(Role::DiagEcu))},{"key.diag-ivi",hex(key->at(Role::DiagIvi))}};
    for(const auto& input:inputs()){
        const auto packet=encodeDiagnostic(*key,ctx,input.sender,input.sequence,input.kind,input.body);
        const auto data=envelope(packet,38+input.body.size());
        out["envelope."+input.name]=hex(data);
        out["tag."+input.name]=hex(Bytes(data.end()-16,data.end()));
        for(unsigned i=0;i<packet.frames.size();++i)out["frame."+input.name+"."+std::to_string(i)]=
            std::to_string(input.sender)+":"+hex(packet.frames[i].data);
    }
    return out;
}
DiagnosticLimits limits(){return {1000,100,4,64};}
DiagnosticResult deliver(DiagnosticReceiver& receiver,std::vector<Frame> frames,std::uint64_t& now,bool reverse=false){
    if(reverse)std::reverse(frames.begin(),frames.end());DiagnosticResult result;
    for(const auto& frame:frames)result=receiver.receive(frame,++now);return result;
}
void allKindsRoundTripAndDuplicate(){
    const auto key=keys();
    for(const auto& input:inputs())for(bool reverse:{false,true}){
        DiagnosticReceiver receiver(key,context(),input.sender,limits(),0);std::uint64_t now=0;
        const auto packet=encodeDiagnostic(*key,context(),input.sender,input.sequence,input.kind,input.body);
        const auto result=deliver(receiver,packet.frames,now,reverse);
        require(result.code==DiagnosticResultCode::Message&&result.message&&result.message->body==input.body&&
                result.message->kind==input.kind&&result.message->sequence==input.sequence&&
                result.message->sender_id==input.sender&&result.message->session_id==contextId(context()),"diagnostic round trip differs");
        const auto duplicate=deliver(receiver,packet.frames,now,reverse);
        require(duplicate.code==DiagnosticResultCode::Duplicate&&duplicate.message->duplicate,"authenticated retry not marked duplicate");
    }
}
void tagBitsAndReflection(){
    const auto input=inputs()[6];const auto key=keys();
    const auto packet=encodeDiagnostic(*key,context(),input.sender,input.sequence,input.kind,input.body);
    for(unsigned bit=0;bit<128;++bit){
        DiagnosticReceiver receiver(key,context(),input.sender,limits(),0);std::uint64_t now=0;
        auto frames=packet.frames;const auto offset=22+input.body.size()+bit/8;
        frames[offset/4].data[4+offset%4]^=1u<<(bit%8);
        const auto result=deliver(receiver,frames,now);
        require(result.code==DiagnosticResultCode::AuthFailed&&!result.message,"diagnostic MAC mutation accepted");
        require(deliver(receiver,packet.frames,now).code==DiagnosticResultCode::Message,"failed MAC consumed replay number");
    }
    auto frames=packet.frames;for(auto& frame:frames)frame.id=0x302;
    DiagnosticReceiver reflected(key,context(),0x302,limits(),0);std::uint64_t now=0;
    require(deliver(reflected,frames,now).code==DiagnosticResultCode::AuthFailed,"opposite direction role reflected");
    auto ctx=context();ctx.nonce_a[0]^=1;
    DiagnosticReceiver old(key,ctx,input.sender,limits(),0);now=0;
    require(deliver(old,packet.frames,now).code==DiagnosticResultCode::ForeignSession,"old context accepted");
}
void reassemblyLimitsAndExpiry(){
    const auto input=inputs()[3];const auto key=keys();
    const auto packet=encodeDiagnostic(*key,context(),input.sender,0,input.kind,input.body);
    DiagnosticReceiver missing(key,context(),input.sender,limits(),0);std::uint64_t now=0;
    auto frames=packet.frames;frames.erase(frames.begin());
    require(deliver(missing,frames,now).code==DiagnosticResultCode::Pending,"incomplete diagnostic delivered");
    const auto expired=missing.poll(1100);
    require(expired.expired_assemblies==1&&missing.pending()==0,"diagnostic assembly did not expire");now=1100;
    require(deliver(missing,packet.frames,now).code==DiagnosticResultCode::Message,"retry after expiry failed");
    auto bound=limits();bound.assemblies=1;
    DiagnosticReceiver full(key,context(),input.sender,bound,0);
    full.receive(packet.frames[0],0);
    auto other=packet.frames[0];other.data[3]=1;
    require(full.receive(other,1).code==DiagnosticResultCode::Limit&&full.pending()==1,"new transfer evicted occupied assembly");
    full.receive(packet.frames[0],999);
    require(full.poll(1000).expired_assemblies==1,"duplicate extended assembly deadline");
    DiagnosticReceiver conflict(key,context(),input.sender,limits(),0);
    conflict.receive(packet.frames[0],0);other=packet.frames[0];other.data[4]^=1;
    require(conflict.receive(other,1).code==DiagnosticResultCode::Invalid&&!conflict.failed(),"unverified conflict failed whole diagnostic channel");
}
void badMetadataPaddingAndTimestamp(){
    const auto input=inputs()[0];const auto key=keys();
    const auto packet=encodeDiagnostic(*key,context(),input.sender,0,input.kind,input.body);
    for(unsigned variant=0;variant<7;++variant){
        DiagnosticReceiver receiver(key,context(),input.sender,limits(),0);auto frame=packet.frames[0];
        switch(variant){case 0:frame.extended=true;break;case 1:frame.remote=true;break;case 2:frame.error=true;break;
            case 3:frame.dlc=7;break;case 4:frame.data[0]=0xd2;break;case 5:frame.data[1]=36;break;case 6:frame.id=0x303;break;}
        const auto result=receiver.receive(frame,0);
        require(!result.message&&receiver.pending()==0,"bad metadata allocated/delivered diagnostic");
    }
    auto padded=packet.frames;padded.back().data[7]=1;
    DiagnosticReceiver pad(key,context(),input.sender,limits(),0);std::uint64_t now=0;
    require(deliver(pad,padded,now).code==DiagnosticResultCode::Invalid,"nonzero diagnostic padding accepted");
    DiagnosticReceiver queued(key,context(),input.sender,limits(),0);
    queued.poll(100);
    DiagnosticResult done;
    for(unsigned i=0;i<packet.frames.size();++i)done=queued.receive(packet.frames[i],101+i,1+i);
    require(done.message&&done.message->received_ms==packet.frames.size()&&done.message->verified_ms==100+packet.frames.size(),
            "diagnostic owner backlog replaced capture time");
    require(queued.poll(0).code==DiagnosticResultCode::ClockError&&queued.failed(),"backward clock silently reopened diagnostics");
}
void replayWindowConflictAndDataIsolation(){
    const auto input=inputs()[5];const auto key=keys();std::uint64_t now=0;
    DiagnosticReceiver receiver(key,context(),0x302,limits(),0);
    for(const auto sequence:{0u,65u,64u}){
        const auto packet=encodeDiagnostic(*key,context(),0x302,sequence,input.kind,input.body);
        require(deliver(receiver,packet.frames,now).code==DiagnosticResultCode::Message,"valid reordered diagnostic rejected");
    }
    const auto old=encodeDiagnostic(*key,context(),0x302,0,input.kind,input.body);
    require(deliver(receiver,old.frames,now).code==DiagnosticResultCode::Replay,"old diagnostic escaped64-message window");
    auto changed=input.body;changed[23]^=1;
    const auto conflict=encodeDiagnostic(*key,context(),0x302,65,input.kind,changed);
    require(deliver(receiver,conflict.frames,now).code==DiagnosticResultCode::Conflict&&receiver.failed(),"authenticated sequence conflict not fatal to diagnostics");
    // A diagnostic failure has no access to the BMS receiver's state/key gate.
    OrderedReceiver data(key,1,ReceiveLimits{100,5,100,4,8,4,128},now);
    const Payload raw{150,200,0x10,0x68,0xff,0xec,65,0};const auto mac=dataMac(key->at(Role::Data),0x100,0,raw);
    Payload auth{};std::copy(mac.begin(),mac.end(),auth.begin());
    data.receive(Frame{0x100,raw},++now);data.receive(Frame{0x102,auth},++now);
    require(data.poll(now+5).applied.size()==1&&!data.failed(),"diagnostic failure contaminated BMS authentication");
}
void schemaAndSenderSequence(){
    const auto key=keys();const auto samples=inputs();
    for(const auto& sample:samples){
        auto wrong=sample.body;wrong[6]=0;
        require(!validDiagnosticBody(sample.sender,sample.kind,wrong),"non-UUID instance accepted");
        wrong=sample.body;wrong.push_back(0);
        require(!validDiagnosticBody(sample.sender,sample.kind,wrong),"extra schema byte accepted");
    }
    auto metrics=samples[5].body;metrics[24]=0; // unknown metric must remain0xffffffff
    require(!validDiagnosticBody(0x302,DiagnosticKind::Metrics,metrics),"missing metric made into measured zero");
    auto incident=samples[3].body;incident[33]=2;
    require(!validDiagnosticBody(0x302,DiagnosticKind::IncidentStatus,incident),"ended incident lacks5s quiet evidence");
    auto rejection=samples[4].body;rejection[33]=0;
    require(!validDiagnosticBody(0x303,DiagnosticKind::Rejection,rejection),"replay disposition falsely lacks MAC verification");
    auto node=samples[0].body;node[34]=4;
    require(!validDiagnosticBody(0x302,DiagnosticKind::NodeStatus,node),"errored input reported ready");
    node[53]=0;require(validDiagnosticBody(0x302,DiagnosticKind::NodeStatus,node),"honest errored input status rejected");
    auto fatal=samples[4].body;fatal[32]=12;
    require(!validDiagnosticBody(0x303,DiagnosticKind::Rejection,fatal),"fatal protected overflow misreported as single rejection");
    fatal[34]=5;require(validDiagnosticBody(0x303,DiagnosticKind::Rejection,fatal),"fatal receive status rejected");
    std::fill(fatal.begin()+48,fatal.begin()+64,0);
    require(!validDiagnosticBody(0x303,DiagnosticKind::Rejection,fatal),"verified pair without session context accepted");
    DiagnosticSender sender(key,context(),0x302);
    bool rejected=false;try{sender.encode(DiagnosticKind::Metrics,metrics);}catch(const std::invalid_argument&){rejected=true;}
    require(rejected&&sender.encode(samples[0].kind,samples[0].body).sequence==0&&
            sender.encode(samples[1].kind,samples[1].body).sequence==1,"invalid schema consumed/reset sender sequence");
}
void macBudgetDoesNotConsumeSequence(){
    const auto sample=inputs()[0];const auto key=keys();auto bound=limits();bound.max_verifications=1;bound.verification_window_ms=10000;
    DiagnosticReceiver receiver(key,context(),sample.sender,bound,0);std::uint64_t now=0;
    const auto packet=encodeDiagnostic(*key,context(),sample.sender,0,sample.kind,sample.body);
    auto wrong=packet.frames;const auto offset=22+sample.body.size();wrong[offset/4].data[4+offset%4]^=1;
    require(deliver(receiver,wrong,now).code==DiagnosticResultCode::AuthFailed,"budget test did not exercise MAC failure");
    require(deliver(receiver,packet.frames,now).code==DiagnosticResultCode::Limit,"verification budget exceeded");
    now=10000;receiver.poll(now);
    require(deliver(receiver,packet.frames,now).code==DiagnosticResultCode::Message,"budget rejection consumed sequence");
}
void authenticatedExchangeOwnsDiagnosticLifetimes(){
    Key key{};for(unsigned i=0;i<32;++i)key[i]=i;
    auto source=[](unsigned seed){return [seed]()mutable{Nonce n{};n.fill(++seed);return n;};};
    const ExchangeLimits bound{20,200,800,60,500,50,64,512,{60,5,100,4,8,4,256},{1000,100,4,64}};
    Exchange ecu(Endpoint::Ecu,key,bound,source(0x40)),ivi(Endpoint::Ivi,key,bound,source(0x41));
    const auto sample=inputs();
    require(!ecu.makeDiagnostic(sample[0].kind,sample[0].body),"diagnostic sent before authenticated session");
    std::uint64_t now=0;std::deque<std::pair<bool,Frame>> queue;
    auto enqueue=[&](bool to_ecu,const auto& frames){for(const auto& frame:frames)queue.push_back({to_ecu,frame});};
    auto pump=[&]{unsigned calls=0;while(!queue.empty()){
        require(++calls<2000,"unbounded diagnostic exchange replies");const auto packet=queue.front();queue.pop_front();
        enqueue(!packet.first,(packet.first?ecu:ivi).receive(packet.second,++now));
    }};
    auto settle=[&]{for(unsigned i=0;i<100;++i){pump();if(ecu.dataOpen()&&ivi.dataOpen())return;
        now+=20;enqueue(false,ecu.poll(now));enqueue(true,ivi.poll(now));}throw std::runtime_error("diagnostic exchange did not open");};
    enqueue(false,ecu.start(now));settle();
    auto node=ecu.makeDiagnostic(sample[0].kind,sample[0].body);
    auto plan=ecu.makeDiagnostic(sample[1].kind,sample[1].body);
    require(node&&plan&&node->sequence==0&&plan->sequence==1&&ecu.nextCounter()==1,"diagnostic ordinal contaminated BMS sequence");
    enqueue(false,node->frames);pump();
    require(ivi.lastDiagnosticResult().code==DiagnosticResultCode::Message&&ivi.lastDiagnosticResult().message->body==sample[0].body,
            "exchange did not deliver authenticated diagnostics");
    enqueue(false,node->frames);pump();require(ivi.lastDiagnosticResult().code==DiagnosticResultCode::Duplicate,"diagnostic retry reset endpoint");
    auto receipt=ivi.makeDiagnostic(sample[2].kind,sample[2].body);
    require(receipt.has_value(),"IVI diagnostic sender unavailable");enqueue(true,receipt->frames);pump();
    require(ecu.lastDiagnosticResult().code==DiagnosticResultCode::Message,"ECU did not verify IVI receipt");
    now+=100;enqueue(true,ivi.start(now));settle();
    auto fresh=ecu.makeDiagnostic(sample[0].kind,sample[0].body);
    require(fresh&&fresh->sequence==0&&fresh->session_id!=node->session_id&&ecu.generation()==2,"new session did not rotate diagnostic identity/counter");
    enqueue(false,fresh->frames);pump();require(ivi.lastDiagnosticResult().code==DiagnosticResultCode::Message,"new context diagnostic rejected as duplicate");
    IdsDiagnosticBridge bridge(4,2,1000);
    auto observation=sample[7].body;
    require(sample[7].kind==DiagnosticKind::Observation,"observation fixture index");
    require(bridge.submit(ecu,{DiagnosticKind::Observation,observation},now),"bridge submit");
    require(!bridge.submit(ecu,{DiagnosticKind::Observation,observation},now),"bridge duplicate accepted");
    unsigned sent=0;
    while(bridge.pending()){
        const auto before=sent;
        bridge.pump(ecu,++now,[&](const Frame& frame){++sent;enqueue(false,std::vector<Frame>{frame});return true;});
        require(sent-before<=2,"bridge exceeded frame budget");pump();
    }
    require(ivi.lastDiagnosticResult().code==DiagnosticResultCode::Message &&
            ivi.lastDiagnosticResult().message->kind==DiagnosticKind::Observation &&
            ivi.lastDiagnosticResult().message->body==observation,"bridge observation not authenticated at IVI");
    enqueue(false,node->frames);pump();
    require(ivi.lastDiagnosticResult().code==DiagnosticResultCode::ForeignSession&&ivi.dataOpen()&&ecu.dataOpen(),
            "old diagnostic accepted or disrupted BMS gate");

    rejects([&]{ProtectionPublisher invalid(0,100);});
    rejects([&]{ProtectionPublisher invalid(1000,0);});
    ProtectionPublisher publication(1000,100);
    Bytes protection(56,0);
    std::copy_n(sample[0].body.begin(),32,protection.begin());
    Exchange dormant(Endpoint::Ecu,key,bound,source(0x60));
    require(!publication.offer(dormant,protection,now),"protection sent without authenticated context");
    require(publication.offer(ecu,protection,now),"protection initial offer failed");
    require(!publication.offer(ecu,protection,now),"protection queue grew beyond one message");
    auto drain=[&]{
        unsigned count=0;
        while(publication.pending()){
            unsigned attempted=0;
            publication.pump(ecu,++now,[&](const Frame& frame){++attempted;++count;enqueue(false,std::vector<Frame>{frame});return true;});
            require(attempted<=1,"protection exceeded one frame per pump");pump();
        }
        return count;
    };
    require(drain()==24,"protection was not exactly24 fragments");
    require(ivi.lastDiagnosticResult().code==DiagnosticResultCode::Message&&
            ivi.lastDiagnosticResult().message->kind==DiagnosticKind::ProtectionStatus&&
            ivi.lastDiagnosticResult().message->body==protection,"published protection did not authenticate");
    const auto sequence=ivi.lastDiagnosticResult().message->sequence;
    require(!publication.offer(ecu,protection,now),"same protection body ignored heartbeat budget");
    now+=1000;require(publication.offer(ecu,protection,now),"protection heartbeat missing");
    publication.pump(ecu,++now,[&](const Frame&){return false;});
    require(!publication.pending()&&publication.dropped()==1,"failed protection frame retried or hidden");
    require(!publication.offer(ecu,protection,now),"failed packet retried immediately");
    now+=1000;require(publication.offer(ecu,protection,now),"next heartbeat unavailable");
    require(drain()==24,"post-failure heartbeat incomplete");
    require(ivi.lastDiagnosticResult().message->sequence==sequence+2,"protection counter rolled back after failure");
    protection[51]=1;require(publication.offer(ecu,protection,now),"changed protection not scheduled");
    publication.pump(ecu,++now,[](const Frame&){return true;});
    require(!publication.offer(ecu,std::nullopt,now)&&!publication.pending(),"unknown event retained stale queued identity");
    require(publication.offer(ecu,protection,now),"valid identity did not resume");
    now+=100;unsigned attempted=0;
    publication.pump(ecu,now,[&](const Frame&){++attempted;return true;});
    require(!attempted&&!publication.pending(),"expired protection frame transmitted");
    protection[51]=0;require(publication.offer(ecu,protection,now),"protection change unavailable");
    enqueue(true,ivi.start(now));settle();
    publication.pump(ecu,++now,[](const Frame&){return true;});
    require(!publication.pending(),"old-session protection survived authentication change");
    require(publication.offer(ecu,protection,now),"new session did not republish protection");
    require(drain()==24&&ivi.lastDiagnosticResult().code==DiagnosticResultCode::Message,
            "new session protection did not authenticate");
    publication.pump(ecu,now,[](const Frame&){return true;});
    publication.pump(ecu,now-1,[](const Frame&){return true;});
    require(publication.failures()==1&&!publication.offer(ecu,protection,now),"clock regression did not isolate publisher");
    require(ecu.dataOpen()&&ivi.dataOpen(),"protection publication failure stopped battery data gate");
}
void restartPlanReceiptAndBoundedWait(){
    const auto input=inputs()[1];
    for(unsigned mode=0;mode<5;++mode){
        Key key{};for(unsigned i=0;i<32;++i)key[i]=i;
        auto source=[](unsigned seed){return [seed]()mutable{Nonce n{};n.fill(++seed);return n;};};
        const ExchangeLimits bound{20,200,800,60,500,50,64,512,{60,5,100,4,8,4,256},{1000,100,4,64}};
        Exchange ecu(Endpoint::Ecu,key,bound,source(0x40)),ivi(Endpoint::Ivi,key,bound,source(0x41));
        RestartNotice notice({30,3});
        std::uint64_t now=0;bool acknowledge=false;unsigned plans=0;bool receipt_seen=false;
        std::deque<std::pair<bool,Frame>> queue;
        auto enqueue=[&](bool to_ecu,const auto& frames){for(const auto& frame:frames)queue.push_back({to_ecu,frame});};
        auto pump=[&]{unsigned calls=0;while(!queue.empty()){
            require(++calls<2000,"restart notice immediate reply loop");auto packet=queue.front();queue.pop_front();
            enqueue(!packet.first,(packet.first?ecu:ivi).receive(packet.second,++now));
            if(packet.first){
                if(ecu.lastDiagnosticResult().message){receipt_seen=true;notice.accept(ecu.lastDiagnosticResult(),now);}
            }else if(acknowledge){
                auto body=restartReceiptBody(ivi.lastDiagnosticResult());
                if(body){
                    ++plans;
                    if(mode==1 || (mode==2 && plans==1))continue; // no response / first response lost
                    if(mode==3)(*body)[0]^=1; // correctly authenticated, wrong ECU instance
                    if(mode==4)(*body)[39]^=1; // correctly authenticated, wrong plan sequence
                    auto receipt=ivi.makeDiagnostic(DiagnosticKind::RestartReceipt,*body);
                    require(receipt.has_value(),"IVI receipt session unavailable");enqueue(true,receipt->frames);
                }
            }
        }};
        enqueue(false,ecu.start(now));
        for(unsigned i=0;i<50 && !ecu.dataOpen();++i){pump();now+=20;enqueue(false,ecu.poll(now));enqueue(true,ivi.poll(now));}pump();
        require(ecu.dataOpen(),"notice test session failed to open");acknowledge=true;
        const auto start=now;
        require(notice.begin(ecu,input.body,now)&&!notice.begin(ecu,input.body,now),"duplicate plan restarted wait");
        PlannedRestart::Decision done=PlannedRestart::Decision::None;
        for(unsigned i=0;i<100;++i){
            auto result=notice.poll(ecu,now);
            if(result.decision!=PlannedRestart::Decision::None){done=result.decision;break;}
            enqueue(false,result.frames);pump();now+=10;
        }
        const bool should_ack=mode==0 || mode==2;
        require(done==(should_ack ? PlannedRestart::Decision::Acknowledged : PlannedRestart::Decision::Deadline),
                "restart wait accepted wrong ACK or stopped without ACK");
        require(should_ack ? now<start+200 : now>=start+200,"restart deadline changed under repeats");
        require(notice.transmissions()<=3&&plans<=3&&notice.poll(ecu,now+1000).decision==PlannedRestart::Decision::None,
                "restart decision or transmissions repeated after completion");
        if(mode==2)require(plans>=2&&receipt_seen,"lost receipt retry case not exercised");
    }
    // No authenticated CAN session / no peer at all still reaches the deadline.
    Key key{};const ExchangeLimits bound{20,200,800,60,500,50,64,512,{60,5,100,4,8,4,256},{1000,100,4,64}};
    Exchange offline(Endpoint::Ecu,key,bound);
    RestartNotice notice({30,3});require(notice.begin(offline,input.body,0),"offline plan not accepted locally");
    require(notice.notificationUnavailable()&&notice.poll(offline,199).frames.empty()&&
            notice.poll(offline,200).decision==PlannedRestart::Decision::Deadline,"CAN absence blocked automatic restart deadline");
}
}
void peerPipeForwarding(){
    const auto all=inputs();const auto found=std::find_if(all.begin(),all.end(),[](const Input& input){return input.name=="rejection";});
    require(found!=all.end(),"peer input missing");
    DiagnosticMessage message{DiagnosticKind::Rejection,1,0x303,contextId(context()),found->body,10,11,false};
    const auto encoded=peerRejectionPacket(message,2,12000000,5);
    // Independently packed Python diagnostic fixture: fixed endianness/layout.
    const std::string expected="4350523100000000000000020000000000b71b0000000000009896800000000000a7d8c0000000019ad351a7c4798ff677bdacabe31d1a8b00000000000000054444444444444444844444444444444455555555555545559555555555555555070101000208080000000100000001029ad351a7c4798ff677bdacabe31d1a8b96c81068ffec410038c2c36700000007";
    require(hex(encoded)==expected,"peer native/Python packet layout mismatch");
    int ends[2];require(::pipe(ends)==0,"peer pipe creation");
    for(const auto fd:ends)require(::fcntl(fd,F_SETFL,::fcntl(fd,F_GETFL)|O_NONBLOCK)==0,"peer nonblocking");
    bool rejected=false;try{PeerDiagnosticWriter wrong(ends[0]);}catch(const std::invalid_argument&){rejected=true;}
    require(rejected,"peer wrong pipe direction accepted");
    {
        PeerDiagnosticWriter writer(ends[1]);auto duplicate=message;duplicate.duplicate=true;
        require(!writer.forward(duplicate,2,12000000)&&writer.dropped()==1,"invalid peer diagnostic was forwarded");
        std::array<char,1024> noise{};while(::write(ends[1],noise.data(),noise.size())>0){}
        require(!writer.forward(message,2,12000000)&&writer.dropped()==2,"peer backpressure hidden/retried");
        while(::read(ends[0],noise.data(),noise.size())>0){}
        require(writer.forward(message,2,12000000),"peer did not resume after backpressure");
        std::array<std::uint8_t,144> received{};
        require(::read(ends[0],received.data(),received.size())==144&&received[63]==2,"peer explicit drop total lost");
    }
    ::close(ends[0]);
}
void protectionContract(){
    std::ifstream file(PROTECTION_FIXTURE_PATH);require(static_cast<bool>(file),"protection fixture missing");
    std::map<std::string,std::string> expected,actual;std::string line;
    while(std::getline(file,line)){
        const auto tab=line.find('\t');require(tab!=std::string::npos,"bad protection fixture row");
        require(expected.emplace(line.substr(0,tab),line.substr(tab+1)).second,"duplicate protection row");
    }
    unsigned index=0;
    for(const std::string name:{"fresh","resume","warning","critical","hot","closed"}){
        const auto body=unhex(expected.at("body."+name));
        const auto packet=encodeDiagnostic(*keys(),context(),0x302,64+index++,DiagnosticKind::ProtectionStatus,body);
        require(packet.frames.size()==24,"protection fragment count changed");
        actual["body."+name]=hex(body);actual["envelope."+name]=hex(envelope(packet,94));
        for(unsigned i=0;i<packet.frames.size();++i)
            actual["frame."+name+"."+std::to_string(i)]="770:"+hex(packet.frames[i].data);
        for(bool reverse:{false,true}){
            DiagnosticReceiver receiver(keys(),context(),0x302,limits(),0);std::uint64_t now=0;
            const auto result=deliver(receiver,packet.frames,now,reverse);
            require(result.code==DiagnosticResultCode::Message&&result.message->kind==DiagnosticKind::ProtectionStatus&&
                    result.message->body==body,"protection round trip failed");
            require(deliver(receiver,packet.frames,now).code==DiagnosticResultCode::Duplicate,"protection duplicate became new");
        }
        for(unsigned bit=0;bit<128;++bit){
            auto changed=packet.frames;const unsigned offset=78+bit/8;
            changed[offset/4].data[4+offset%4]^=static_cast<std::uint8_t>(1u<<(bit%8));
            DiagnosticReceiver receiver(keys(),context(),0x302,limits(),0);std::uint64_t now=0;
            require(deliver(receiver,changed,now).code==DiagnosticResultCode::AuthFailed,"protection tag mutation accepted");
        }
        auto other=context();other.nonce_a[0]^=1;
        DiagnosticReceiver receiver(keys(),other,0x302,limits(),0);std::uint64_t now=0;
        require(deliver(receiver,packet.frames,now).code==DiagnosticResultCode::ForeignSession,"foreign protection became current");
        require(!validDiagnosticBody(0x303,DiagnosticKind::ProtectionStatus,body),"IVI protection direction accepted");
        auto short_body=body;short_body.pop_back();
        require(!validDiagnosticBody(0x302,DiagnosticKind::ProtectionStatus,short_body),"short protection body accepted");
        for(unsigned at:{0u,16u}){
            auto invalid=body;std::fill_n(invalid.begin()+at,16,0);
            require(!validDiagnosticBody(0x302,DiagnosticKind::ProtectionStatus,invalid),"zero protection identity accepted");
        }
        auto invalid=body;invalid[51]=2;
        require(!validDiagnosticBody(0x302,DiagnosticKind::ProtectionStatus,invalid),"protection reserved flag accepted");
    }
    require(actual==expected&&actual.size()==156,"protection C++ differs from independent Python vectors");
    const auto active=unhex(expected.at("body.warning"));
    const std::array<unsigned,4> reasons{(1u<<0)|(1u<<5)|(1u<<6),(1u<<0)|(1u<<1)|(1u<<3)|(1u<<7),
                                        (1u<<0)|(1u<<2),(1u<<0)|(1u<<4)};
    for(unsigned phase=0;phase<4;++phase)for(unsigned state=0;state<5;++state)for(unsigned reason=0;reason<9;++reason){
        auto changed=active;changed[48]=state;changed[49]=reason;changed[50]=phase;
        const bool allowed=(phase==1||phase==2)&&state<4&&(reasons[state]&(1u<<reason))&&
                           (phase==1?state!=0:state==0);
        require(validDiagnosticBody(0x302,DiagnosticKind::ProtectionStatus,changed)==allowed,"protection state/phase/reason drift");
    }
    auto no_event=unhex(expected.at("body.fresh"));no_event[49]=5;
    require(!validDiagnosticBody(0x302,DiagnosticKind::ProtectionStatus,no_event),"no event claimed prior recovery");
    auto zero_revision=active;std::fill_n(zero_revision.begin()+52,4,0);
    require(!validDiagnosticBody(0x302,DiagnosticKind::ProtectionStatus,zero_revision),"active protection revision zero accepted");
    zero_revision=active;std::fill_n(zero_revision.begin()+32,16,0);
    require(!validDiagnosticBody(0x302,DiagnosticKind::ProtectionStatus,zero_revision),"active protection missing event accepted");
}
int main(int argc,char** argv){
    try{
        const auto actual=vectors();
        if(argc==2&&std::string(argv[1])=="--emit-dummy-vectors"){
            for(const auto& [name,value]:actual)std::cout<<name<<'\t'<<value<<'\n';return 0;
        }
        require(argc==1,"unexpected diagnostic test argument");
        std::ifstream file(DIAGNOSTIC_FIXTURE_PATH);require(static_cast<bool>(file),"diagnostic expected fixture missing");
        std::map<std::string,std::string> expected;std::string line;
        while(std::getline(file,line)){
            const auto tab=line.find('\t');require(tab!=std::string::npos,"bad expected row");
            require(expected.emplace(line.substr(0,tab),line.substr(tab+1)).second,"duplicate expected field");
        }
        require(actual==expected,"diagnostic C++ differs from independent Python fixture");
        for(const auto& input:inputs()){
            Bytes packet{'C','I','D','2',static_cast<std::uint8_t>(input.kind),static_cast<std::uint8_t>(input.body.size()),0,0,0,0,0,0,0,42};
            packet.insert(packet.end(),input.body.begin(),input.body.end());
            const auto parsed=parseIdsDiagnosticSubmission(packet);
            const bool allowed=input.kind==DiagnosticKind::IncidentStatus || input.kind==DiagnosticKind::Observation;
            require(static_cast<bool>(parsed)==allowed,"IPC accepted unauthorized diagnostic kind");
            if(parsed)require(parsed->body==input.body && parsed->kind==input.kind,"IPC changed body");
            packet.push_back(0);require(!parseIdsDiagnosticSubmission(packet),"IPC accepted trailing bytes");
            packet.pop_back();packet.pop_back();require(!parseIdsDiagnosticSubmission(packet),"IPC accepted truncation");
            packet[0]='X';require(!parseIdsDiagnosticSubmission(packet),"IPC accepted bad magic");
        }
        {
            const auto input=inputs()[0];
            auto packet=encodeDiagnostic(*keys(),context(),input.sender,0,input.kind,input.body);
            const auto identity=packet.session_id;
            DiagnosticTxQueue queue(1,2,100);
            require(queue.offer(packet,0),"TX enqueue");
            require(!queue.offer(packet,0),"TX capacity ignored");
            unsigned sent=0;
            queue.pump(identity,1,[&](const Frame&){++sent;return true;});
            require(sent==2 && queue.pending()==1,"TX budget ignored");
            queue.pump(identity,2,[&](const Frame&){++sent;return false;});
            require(sent==3 && queue.pending()==0,"failed packet retried");
            require(queue.offer(packet,3),"TX reenqueue");
            queue.pump(identity,103,[&](const Frame&){++sent;return true;});
            require(sent==3 && queue.pending()==0,"expired packet sent");
            require(queue.offer(packet,104),"TX session enqueue");
            auto changed=identity;changed[0]^=1;
            queue.pump(changed,105,[&](const Frame&){++sent;return true;});
            require(sent==3 && queue.pending()==0,"old session packet sent");
        }
        {
            std::ifstream file(PHYSICAL_FIXTURE_PATH);require(bool(file),"physical public vector file missing");
            std::string name,body_hex,frames_hex;std::uint32_t sequence;unsigned count=0;
            while(file>>name>>sequence>>body_hex>>frames_hex){
                const auto body=unhex(body_hex);require(decodePhysicalMeasurement(body).has_value(),"physical body rejected");
                auto reference=*decodePhysicalMeasurement(body);reference.soh_basis=2;reference.soh_percent=81;
                const auto referenceBody=encodePhysicalMeasurement(reference);
                require(decodePhysicalMeasurement(referenceBody)->soh_basis==2,"SOH reference basis lost");
                auto badReference=referenceBody;badReference[67]=3;
                require(!decodePhysicalMeasurement(badReference),"unknown SOH basis accepted");
                badReference=referenceBody;badReference[65]&=~16;
                require(!decodePhysicalMeasurement(badReference),"SOH reference without value accepted");

                const auto packet=encodeDiagnostic(*keys(),context(),0x302,sequence,DiagnosticKind::PhysicalMeasurement,body);
                std::string actual;for(const auto& frame:packet.frames)actual+=hex(frame.data);
                require(actual==frames_hex&&packet.frames.size()==30,"C++/Python physical frame mismatch");
                DiagnosticReceiver receiver(keys(),context(),0x302,{1000,100,4,128},0);
                DiagnosticResult result;
                for(unsigned i=0;i<packet.frames.size();++i)result=receiver.receive(packet.frames[i],i+1);
                require(result.code==DiagnosticResultCode::Message&&result.message->body==body,"physical authenticated receive failed");
                require(!validDiagnosticBody(0x303,DiagnosticKind::PhysicalMeasurement,body),"physical reverse direction accepted");++count;
            }
            require(count==6,"physical vector count");
        }
        allKindsRoundTripAndDuplicate();tagBitsAndReflection();reassemblyLimitsAndExpiry();badMetadataPaddingAndTimestamp();
        replayWindowConflictAndDataIsolation();schemaAndSenderSequence();macBudgetDoesNotConsumeSequence();
        authenticatedExchangeOwnsDiagnosticLifetimes();
        restartPlanReceiptAndBoundedWait();
        peerPipeForwarding();protectionContract();
        std::cout<<"PASS diagnostic vectors="<<actual.size()<<";128 tag bit mutations,6 restart ACK cases and peer pipe layout/backpressure\n";return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
