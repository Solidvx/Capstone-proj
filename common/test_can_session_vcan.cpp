#include "can_restart_notice.h"
#include "physical_measurement.h"
#include <cmath>

#include <linux/can.h>
#include <linux/can/raw.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>

using namespace capstone::session_v2;
namespace {
void require(bool value,const char* text){if(!value)throw std::runtime_error(text);}
std::uint64_t milliseconds(){return std::chrono::duration_cast<std::chrono::milliseconds>(
    std::chrono::steady_clock::now().time_since_epoch()).count();}
class Socket {
public:
    explicit Socket(const std::string& name,bool ecu){
        fd_=::socket(PF_CAN,SOCK_RAW|SOCK_CLOEXEC|SOCK_NONBLOCK,CAN_RAW);
        require(fd_>=0,"vcan socket failed");
        try{
            const std::vector<canid_t> ids=ecu ? std::vector<canid_t>{0x301,0x303} :
                std::vector<canid_t>{0x100,0x101,0x102,0x103,0x104,0x105,0x300,0x302};
            std::vector<can_filter> filters;
            for(const auto id:ids)filters.push_back({id,CAN_SFF_MASK|CAN_EFF_FLAG|CAN_RTR_FLAG});
            require(::setsockopt(fd_,SOL_CAN_RAW,CAN_RAW_FILTER,filters.data(),filters.size()*sizeof(can_filter))==0,"vcan filter setup failed");
            ifreq request{};std::strncpy(request.ifr_name,name.c_str(),IFNAMSIZ-1);
            require(::ioctl(fd_,SIOCGIFINDEX,&request)==0,"vcan interface unavailable");
            sockaddr_can address{};address.can_family=AF_CAN;address.can_ifindex=request.ifr_ifindex;
            require(::bind(fd_,reinterpret_cast<sockaddr*>(&address),sizeof address)==0,"vcan bind failed");
        }catch(...){::close(fd_);fd_=-1;throw;}
    }
    ~Socket(){if(fd_>=0)::close(fd_);}
    void send(const std::vector<Frame>& frames){
        for(const auto& frame:frames){
            can_frame raw{};raw.can_id=frame.id;raw.can_dlc=frame.dlc;
            std::copy(frame.data.begin(),frame.data.end(),raw.data);
            require(::write(fd_,&raw,sizeof raw)==sizeof raw,"vcan frame send failed");++sent;
        }
    }
    std::optional<Frame> receive(){
        can_frame raw{};const auto n=::read(fd_,&raw,sizeof raw);
        if(n<0&&(errno==EAGAIN||errno==EWOULDBLOCK))return std::nullopt;
        require(n==sizeof raw,"vcan read failed/truncated");
        Frame result{};result.id=raw.can_id&CAN_SFF_MASK;result.dlc=raw.can_dlc;
        result.extended=raw.can_id&CAN_EFF_FLAG;result.remote=raw.can_id&CAN_RTR_FLAG;result.error=raw.can_id&CAN_ERR_FLAG;
        std::copy(std::begin(raw.data),std::end(raw.data),result.data.begin());++received;return result;
    }
    unsigned sent=0,received=0;
private:int fd_=-1;
};
void uuid(std::vector<std::uint8_t>& bytes,unsigned at,std::uint8_t seed){
    std::fill_n(bytes.begin()+at,16,seed);bytes[at+6]=0x40|(seed&15);bytes[at+8]=0x80|(seed&63);
}
int receivePhysicalEcu(const std::string& iface,const std::string& selected){
    Socket socket(iface,false);Key dummy{};for(unsigned i=0;i<32;++i)dummy[i]=i;
    ExchangeLimits bounds{100,1000,5000,500,2000,200,64,1024,{200,5,100,8,16,8,1024},{1000,100,4,128}};
    Exchange ivi(Endpoint::Ivi,dummy,bounds);const auto start=milliseconds();
    std::optional<Nonce> instance;bool passed=false,inject=false;
    const bool receive_fault=selected=="--ivi-physical-receive-error";
    auto observe=[&]{
        for(const auto& m:ivi.lastReceiveOutcome().applied){
            require(m.id!=0x100,"physical mode fabricated a legacy pack BMS");
            require(m.id!=0x101,"physical mode fabricated a legacy battery warning");
        }
        const auto& result=ivi.lastDiagnosticResult();
        if(result.code!=DiagnosticResultCode::Message||!result.message)return;
        const auto& message=*result.message;
        if(message.kind==DiagnosticKind::NodeStatus){
            require(message.body[35]==0xff,"physical mode claimed unconfigured battery protection");
            Nonce id{};std::copy_n(message.body.begin(),16,id.begin());instance=id;
            if(receive_fault&&message.body[32]==5){passed=true;return;}
        }
        if(message.kind!=DiagnosticKind::PhysicalMeasurement)return;
        const auto m=decodePhysicalMeasurement(message.body);require(m.has_value(),"invalid physical body");
        if(!instance||m->instance!=*instance||m->sequence<3)return;
        const bool no_electrical=selected=="--ivi-physical-electrical-error";
        const bool no_temperature=selected=="--ivi-physical-temperature-error";
        if(!no_electrical&&(!m->voltage_v||!m->current_a))return;
        if(!no_temperature&&!m->temperature_c)return;
        require(no_electrical?!m->voltage_v:std::abs(*m->voltage_v-3.737)<1e-6,"physical voltage mismatch");
        require(no_electrical?!m->current_a:std::abs(*m->current_a+.37)<1e-6,"physical current mismatch");
        require(no_temperature?!m->temperature_c:std::abs(*m->temperature_c-19.75)<1e-6,"physical temperature mismatch");
        if(selected=="--ivi-physical-known"){
            require(m->soc_percent&&*m->soc_percent>79&&*m->soc_percent<=80,"explicit SOC prior not integrated");
            require(m->soh_percent&&std::abs(*m->soh_percent-90)<1e-6,"independent capacity SOH mismatch");
        }else require(!m->soc_percent&&!m->soh_percent,"unknown physical SOC/SOH fabricated");
        require(m->nominal_capacity_mah==2550,"single-cell nominal capacity lost");
        if(receive_fault)inject=true;else passed=true;
    };
    while(!passed){
        require(milliseconds()-start<(receive_fault?25000u:8000u),"physical ECU authentication/data deadline");
        if(inject)socket.send({Frame{0x123,{}}});
        while(auto frame=socket.receive()){const auto at=milliseconds();socket.send(ivi.receive(*frame,at,at));observe();}
        socket.send(ivi.poll(milliseconds()));observe();std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    std::cout<<"PASS actual physical ECU/owned reader/authenticated CAN: "<<selected<<"; synthetic syscall inputs only\n";return 0;
}
int receiveRealEcu(const std::string& iface){
    Socket socket(iface,false);
    Key dummy{};for(unsigned i=0;i<32;++i)dummy[i]=i;
    const ExchangeLimits limits{100,1000,5000,500,2000,200,64,1024,{200,5,100,8,16,8,1024},{1000,100,4,128}};
    Exchange ivi(Endpoint::Ivi,dummy,limits);
    unsigned bms=0;
    auto observe=[&]{
        for(const auto& message:ivi.lastReceiveOutcome().applied)if(message.id==0x100){
            require(message.payload[1]==200 && message.payload[7]==0,"real ECU modified existing BMS layout");++bms;
        }
    };
    const auto start=milliseconds();socket.send(ivi.start(start));
    while(bms<10){
        require(milliseconds()-start<8000,"real ECU did not complete authenticated session/BMS publication");
        unsigned burst=0;
        while(auto frame=socket.receive()){
            require(++burst<=512,"real ECU test unexpected RX burst");const auto at=milliseconds();
            socket.send(ivi.receive(*frame,at,at));observe();
        }
        socket.send(ivi.poll(milliseconds()));observe();
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    require(ivi.generation()==1&&ivi.receivedState()==Payload{}&&ivi.lastAuthenticatedBmsAt(),
            "real ECU BMS bypassed initial state/session gate");
    std::cout<<"PASS real adaptive_ecu main/PubSub/session-v2/vcan -> authenticated IVI receiver;published_bms="<<bms
        <<";generation="<<ivi.generation()<<";no legacy fallback\n";return 0;
}
}
int main(int argc,char** argv){
    const char* name=std::getenv("CAPSTONE_SESSION_TEST_INTERFACE");
    if(!name){std::cout<<"SKIP: set CAPSTONE_SESSION_TEST_INTERFACE to an existing virtual CAN\n";return 77;}
    try{
        const std::string iface(name);
        require(iface.rfind("vcan",0)==0&&iface.find('/')==std::string::npos&&iface.size()<IFNAMSIZ&&
            std::filesystem::is_directory("/sys/devices/virtual/net/"+iface),"session smoke only accepts existing virtual vcan interfaces");
        if(argc==2&&std::string(argv[1])=="--ivi-only")return receiveRealEcu(iface);
        if(argc==2&&std::string(argv[1]).rfind("--ivi-physical",0)==0)return receivePhysicalEcu(iface,argv[1]);
        require(argc==1,"unexpected vcan test argument");
        Socket ecu_socket(iface,true),ivi_socket(iface,false);
        Key dummy{};for(unsigned i=0;i<32;++i)dummy[i]=i;
        // Explicit smoke-test settings, not product timing guarantees/defaults.
        ExchangeLimits bound{100,1000,5000,500,2000,200,64,1024,{200,5,100,8,16,8,1024},{1000,100,4,128}};
        Exchange ecu(Endpoint::Ecu,dummy,bound),ivi(Endpoint::Ivi,dummy,bound);
        const Payload shutdown{3,1,4,0,0,0,0,0};
        ecu.setCurrentState(shutdown,milliseconds());
        RestartNotice notice({100,3});
        unsigned bms=0,plans=0;
        auto consume=[&](bool to_ecu){
            auto& socket=to_ecu ? ecu_socket : ivi_socket;
            auto& exchange=to_ecu ? ecu : ivi;
            unsigned processed=0;
            while(auto frame=socket.receive()){
                require(++processed<=512,"vcan receive burst exceeded smoke limit");
                const auto at=milliseconds();socket.send(exchange.receive(*frame,at,at));
                if(to_ecu)notice.accept(exchange.lastDiagnosticResult(),at);
                else{
                    for(const auto& message:exchange.lastReceiveOutcome().applied)if(message.id==0x100)++bms;
                    if(auto body=restartReceiptBody(exchange.lastDiagnosticResult())){
                        ++plans;auto receipt=ivi.makeDiagnostic(DiagnosticKind::RestartReceipt,*body);
                        require(receipt.has_value(),"vcan receipt sender missing");ivi_socket.send(receipt->frames);
                    }
                }
            }
        };
        auto tick=[&]{
            consume(true);consume(false);
            const auto now=milliseconds();ecu_socket.send(ecu.poll(now));ivi_socket.send(ivi.poll(now));
            for(const auto& message:ivi.lastReceiveOutcome().applied)if(message.id==0x100)++bms;
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        };
        const auto start=milliseconds();ecu_socket.send(ecu.start(start));
        while(!ecu.dataOpen()||!ivi.dataOpen()){
            if(milliseconds()-start>=5000){
                std::cerr<<"vcan handshake state ecu="<<static_cast<unsigned>(ecu.phase())<<" ivi="<<static_cast<unsigned>(ivi.phase())
                    <<";ecu_tx="<<ecu_socket.sent<<";ecu_rx="<<ecu_socket.received<<";ivi_tx="<<ivi_socket.sent
                    <<";ivi_rx="<<ivi_socket.received<<";ecu_generation="<<ecu.generation()<<";ivi_generation="<<ivi.generation()<<'\n';
                throw std::runtime_error("vcan initial handshake deadline");
            }
            tick();
        }
        require(ivi.receivedState()==shutdown&&!ivi.lastAuthenticatedBmsAt(),"state sync fabricated normal battery/BMS");
        const Payload raw{150,200,0x10,0x68,0xff,0xec,65,0};
        const auto pair=ecu.publishData(0x100,raw,milliseconds());ecu_socket.send(pair);
        while(!bms){require(milliseconds()-start<6000,"vcan authenticated BMS not published");tick();}
        const auto last=ivi.lastAuthenticatedBmsAt();ecu_socket.send(pair);
        const auto replay_started=milliseconds();while(milliseconds()-replay_started<30)tick();
        require(bms==1&&ivi.lastAuthenticatedBmsAt()==last,"vcan replay published/refreshed normal BMS");
        std::vector<std::uint8_t> plan(56);uuid(plan,0,0x11);uuid(plan,16,0x22);uuid(plan,32,0x33);
        plan[48]=1;plan[49]=2;plan[50]=1;plan[54]=3;plan[55]=0xe8; //1000ms smoke ACK wait
        require(notice.begin(ecu,plan,milliseconds()),"vcan restart plan did not begin");
        PlannedRestart::Decision decision=PlannedRestart::Decision::None;
        while(decision==PlannedRestart::Decision::None){
            auto result=notice.poll(ecu,milliseconds());decision=result.decision;ecu_socket.send(result.frames);
            require(milliseconds()-start<8000,"vcan notice deadline");if(decision==PlannedRestart::Decision::None)tick();
        }
        require(decision==PlannedRestart::Decision::Acknowledged&&plans>=1&&ecu.nextCounter()==2,
            "vcan ACK not bound to restart request or diagnostic consumed BMS ordinal");
        require(ivi.receivedState()==shutdown,"restart notification lowered actual shutdown");
        std::cout<<"PASS vcan authenticated session/current shutdown/BMS/replay/restart notice ACK;ecu_tx="<<ecu_socket.sent
            <<";ivi_tx="<<ivi_socket.sent<<";published_bms="<<bms<<";no process restart performed\n";return 0;
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
