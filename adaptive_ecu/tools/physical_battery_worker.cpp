// Private sensor subprocess. It receives no CAN descriptor or authentication key.
#include "physical_sensor_runtime.h"
#include "bounded_sensor_read.h"
#include "ds18b20_acquirer.h"
#include "linux_i2c_transport.h"

#include <chrono>
#include <cmath>
#include <csignal>
#include <cstring>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <sys/prctl.h>
#include <thread>
#include <unistd.h>

namespace {
volatile std::sig_atomic_t running=1;
void stop(int){running=0;}
std::uint64_t nowMs(){return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
// The child returns a full, canonical local packet, so no text/float parser is
// needed between the bounded device call and its single-thread owner.
std::string packetText(const PhysicalSensorSample& sample){
    const auto p=encodePhysicalSensorSample(sample);
    return std::string(reinterpret_cast<const char*>(p.data()),p.size());
}
std::optional<PhysicalSensorSample> returned(const BoundedSensorRead& read){
    if(read.status!=BoundedSensorRead::Status::Complete||read.text.size()!=84)return std::nullopt;
    PhysicalSensorPacket p{};std::memcpy(p.data(),read.text.data(),p.size());return decodePhysicalSensorSample(p);
}
}
int main(int argc,char** argv){
    try{
        if(argc!=5||std::string(argv[1])!="--config"||std::string(argv[3])!="--parent-pid")
            throw std::invalid_argument("owned physical reader invocation required");
        const std::string parent_text=argv[4];
        if(parent_text.empty()||parent_text.find_first_not_of("0123456789")!=std::string::npos)
            throw std::invalid_argument("invalid reader parent");
        const auto parent=std::stoull(parent_text);
        if(parent<=1||parent>static_cast<unsigned>(std::numeric_limits<int>::max()))throw std::invalid_argument("invalid reader parent");
        std::signal(SIGTERM,stop);std::signal(SIGINT,stop);std::signal(SIGPIPE,SIG_IGN);
        if(::prctl(PR_SET_PDEATHSIG,SIGTERM)||::getppid()!=static_cast<pid_t>(parent))return 2;
        const auto config=loadPhysicalRuntimeConfig(argv[2]);
        std::uint64_t sequence=0;
        while(running){
            if(sequence==std::numeric_limits<std::uint64_t>::max())return 2;
            const auto start=std::chrono::steady_clock::now();
            PhysicalSensorSample sample;sample.sequence=++sequence;sample.fingerprint=config.fingerprint;
            auto ina=readSensorBounded([&]{
                PhysicalSensorSample reply=sample;
                LinuxI2cTransport transport(config.i2c_device,config.ina_address);
                Ina219Acquirer reader(transport,config.ina);
                if(transport.ready()&&reader.start()){
                    Ina219Result result{Ina219Status::Waiting,{}};
                    do{result=reader.poll();if(result.status==Ina219Status::Waiting)std::this_thread::sleep_for(std::chrono::milliseconds(1));}
                    while(result.status==Ina219Status::Waiting);
                    if(result.measurement){reply.voltage_v=result.measurement->terminal_v;reply.current_a=result.measurement->battery_current_a;}
                }
                reply.ina_ms=reply.completed_ms=nowMs();return packetText(reply);
            },config.read_timeout_ms,[]{return running!=0;});
            if(ina.status==BoundedSensorRead::Status::Unreclaimed)return 2;
            sample.ina_ms=nowMs();
            if(auto read=returned(ina)){sample.ina_ms=read->ina_ms;sample.voltage_v=read->voltage_v;sample.current_a=read->current_a;}
            auto temperature=readSensorBounded([&]{
                PhysicalSensorSample reply=sample;std::ifstream input(config.w1_root+'/'+config.temperature_device+"/w1_slave");
                std::string text;char ch;
                if(input){while(input.get(ch)){text+=ch;if(text.size()>1024)break;}
                    if(!input.bad())reply.temperature_c=parseDs18b20(text).temperature_c;
                }
                reply.temperature_ms=reply.completed_ms=nowMs();return packetText(reply);
            },config.read_timeout_ms,[]{return running!=0;});
            if(temperature.status==BoundedSensorRead::Status::Unreclaimed)return 2;
            sample.temperature_ms=nowMs();
            if(auto read=returned(temperature)){sample.temperature_ms=read->temperature_ms;sample.temperature_c=read->temperature_c;}
            sample.completed_ms=nowMs();
            if(!running)break;
            const auto packet=encodePhysicalSensorSample(sample);
            // PIPE_BUF-sized atomic write; a stalled owner/backpressure ends
            // acquisition instead of accumulating or publishing stale samples.
            ssize_t sent;
            do{sent=::write(STDOUT_FILENO,packet.data(),packet.size());}while(sent<0&&errno==EINTR&&running);
            if(sent!=static_cast<ssize_t>(packet.size()))return 2;
            while(running&&std::chrono::steady_clock::now()<start+std::chrono::milliseconds(config.period_ms))
                std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
        return 0;
    }catch(const std::exception& error){std::cerr<<"physical reader stopped: "<<error.what()<<'\n';return 2;}
}
