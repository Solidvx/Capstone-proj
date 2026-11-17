// Independent diagnostic only: never opens CAN, a SecOC key or a BMS model.
#include "bounded_sensor_read.h"
#include "ds18b20_acquirer.h"
#include "ina219_acquirer.h"
#include "linux_i2c_transport.h"

#include <chrono>
#include <csignal>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <thread>

namespace {
using Clock=std::chrono::steady_clock;
volatile std::sig_atomic_t running=1;
void stop(int){running=0;}
std::uint64_t nowMs(){return std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now().time_since_epoch()).count();}
std::string readStatus(BoundedSensorRead::Status status){
    using S=BoundedSensorRead::Status;
    if(status==S::Timeout)return "TIMEOUT";
    if(status==S::Interrupted)return "INTERRUPTED";
    if(status==S::Unreclaimed)return "UNRECLAIMED";
    return "CHILD_ERROR";
}
std::string body(const BoundedSensorRead& result){
    return result.status==BoundedSensorRead::Status::Complete ? result.text :
        "{\"status\":\""+readStatus(result.status)+"\",\"measurement\":null}";
}
double number(const std::string& value){
    std::size_t used=0;const auto result=std::stod(value,&used);
    if(used!=value.size()||value.empty()||value.find_first_of(" \t\r\n")!=std::string::npos)
        throw std::invalid_argument("invalid numeric option");
    return result;
}
unsigned integer(const std::string& value,unsigned max){
    if(!std::regex_match(value,std::regex("[0-9]+")))throw std::invalid_argument("invalid integer option");
    const auto result=std::stoul(value);
    if(result>max)throw std::invalid_argument("integer option out of range");
    return static_cast<unsigned>(result);
}
std::string publicIdentity(const char* path){
    std::ifstream input(path);std::string value;input>>value;
    if(!input||!std::regex_match(value,std::regex("[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")))
        throw std::runtime_error("public Linux capture/clock identity unavailable");
    return value;
}
}
int main(int argc,char** argv){
    std::string device,w1root="/sys/bus/w1/devices",sensor,calibration_id;
    unsigned address=0,count=0,period=0,timeout=0;
    Ina219Config config{};bool shunt=false,lsb=false,sign=false,zero=false,offset=false;
    try{
        for(int i=1;i<argc;++i){
            const std::string name=argv[i];
            if(name=="--help"){
                std::cout<<"physical_battery_capture --i2c-device PATH --ina-address DECIMAL --shunt-ohm N\n"
                    " --current-lsb-a N --battery-current-sign -1|1 --current-zero-a N --terminal-offset-v N\n"
                    " --temperature-device 28-xxxxxxxxxxxx --calibration-id LABEL\n"
                    " --count N --period-ms N --read-timeout-ms N [--w1-root PATH]\n"
                    "Explicit raw acquisition only. Stop other INA219/w1 readers. JSONL to stdout.\n"
                    "No CAN/SOC/SOH. Exit 1: measurement errors; 2: setup/unreclaimed worker; 130: interrupted.\n";
                return 0;
            }
            if(i+1>=argc)throw std::invalid_argument("missing option value");
            const std::string value=argv[++i];
            if(name=="--i2c-device")device=value;
            else if(name=="--ina-address")address=integer(value,0x4f);
            else if(name=="--shunt-ohm"){config.shunt_ohm=number(value);shunt=true;}
            else if(name=="--current-lsb-a"){config.requested_current_lsb_a=number(value);lsb=true;}
            else if(name=="--battery-current-sign"){if(value!="-1"&&value!="1")throw std::invalid_argument("sign must be -1 or 1");config.battery_current_sign=value=="-1"?-1:1;sign=true;}
            else if(name=="--current-zero-a"){config.current_zero_a=number(value);zero=true;}
            else if(name=="--terminal-offset-v"){config.terminal_offset_v=number(value);offset=true;}
            else if(name=="--temperature-device")sensor=value;
            else if(name=="--calibration-id")calibration_id=value;
            else if(name=="--count")count=integer(value,100000);
            else if(name=="--period-ms")period=integer(value,10000);
            else if(name=="--read-timeout-ms")timeout=integer(value,10000);
            else if(name=="--w1-root")w1root=value;
            else throw std::invalid_argument("unknown option");
        }
        if(device.empty()||w1root.empty()||address<0x40||!count||!period||!timeout||!shunt||!lsb||!sign||!zero||!offset||
           !std::regex_match(sensor,std::regex("28-[0-9a-f]{12}"))||
           !std::regex_match(calibration_id,std::regex("[A-Za-z0-9_-]{1,64}")))
            throw std::invalid_argument("explicit devices, calibration and bounded timing required");
        // Validate calibration before any device I/O; the unopened transport
        // below is only constructed inside its bounded child.
        struct NoIo final:Ads1115Transport{
            bool write(const std::uint8_t*,std::size_t)override{return false;}
            bool readRegister(std::uint8_t,std::uint8_t*,std::size_t)override{return false;}
        } no_io;
        Ina219Acquirer validated(no_io,config);
        const auto capture_id=publicIdentity("/proc/sys/kernel/random/uuid");
        const auto clock_id=publicIdentity("/proc/sys/kernel/random/boot_id");
        std::signal(SIGINT,stop);std::signal(SIGTERM,stop);
        bool failed=false;
        for(unsigned i=0;i<count && running;++i){
            const auto start=Clock::now();
            const auto sample_started_ms=nowMs();
            auto ina=readSensorBounded([&]{
                const auto begin=nowMs();LinuxI2cTransport bus(device,static_cast<std::uint8_t>(address));
                if(!bus.ready())return std::string("{\"status\":\"OPEN_ERROR\",\"measurement\":null}");
                Ina219Acquirer reader(bus,config);
                if(!reader.start())return std::string("{\"status\":\"START_ERROR\",\"measurement\":null}");
                Ina219Result result{Ina219Status::Waiting,{}};
                do{result=reader.poll();if(result.status==Ina219Status::Waiting)std::this_thread::sleep_for(std::chrono::milliseconds(1));}
                while(result.status==Ina219Status::Waiting);
                std::ostringstream out;out<<std::setprecision(17)<<"{\"status\":\""<<ina219StatusName(result.status)
                    <<"\",\"started_ms\":"<<begin<<",\"completed_ms\":"<<nowMs()<<",\"measurement\":";
                if(result.measurement){const auto& m=*result.measurement;
                    out<<"{\"bus_raw\":"<<m.bus_raw<<",\"shunt_raw\":"<<m.shunt_raw<<",\"current_raw\":"<<m.current_raw
                        <<",\"bus_v\":"<<m.bus_v<<",\"shunt_v\":"<<m.shunt_v<<",\"terminal_v\":"<<m.terminal_v
                        <<",\"ina_current_a\":"<<m.ina_current_a<<",\"battery_current_a\":"<<m.battery_current_a<<'}';
                }else out<<"null";
                out<<'}';return out.str();
            },timeout,[]{return running!=0;});
            if(ina.status==BoundedSensorRead::Status::Unreclaimed){std::cerr<<"INA219 reader unreclaimed; capture stopped\n";return 2;}
            auto temp=readSensorBounded([&]{
                const auto begin=nowMs();std::ifstream input(w1root+'/'+sensor+"/w1_slave");
                if(!input)return std::string("{\"status\":\"OPEN_ERROR\",\"measurement\":null}");
                std::string text;char c;
                while(input.get(c)){text+=c;if(text.size()>1024)break;}
                if(input.bad())return std::string("{\"status\":\"IO_ERROR\",\"measurement\":null}");
                auto result=parseDs18b20(text);std::ostringstream out;
                out<<std::setprecision(17)<<"{\"status\":\""<<ds18b20StatusName(result.status)
                    <<"\",\"started_ms\":"<<begin<<",\"completed_ms\":"<<nowMs()<<",\"measurement\":";
                if(result.temperature_c)out<<"{\"temperature_c\":"<<*result.temperature_c<<'}';else out<<"null";
                out<<",\"scratchpad\":\""<<std::hex<<std::setfill('0');
                for(auto b:result.scratchpad)out<<std::setw(2)<<unsigned(b);
                out<<"\"}";return out.str();
            },timeout,[]{return running!=0;});
            if(temp.status==BoundedSensorRead::Status::Unreclaimed){std::cerr<<"DS18B20 reader unreclaimed; capture stopped\n";return 2;}
            const auto a=body(ina),b=body(temp);
            const bool ok=a.find("\"status\":\"OK\"")!=std::string::npos&&b.find("\"status\":\"OK\"")!=std::string::npos;
            failed|=!ok;
            std::cout<<std::setprecision(17)<<"{\"schema\":\"physical-sensor-v2\",\"sample\":"<<i
                <<",\"capture_id\":\""<<capture_id<<"\",\"clock_id\":\""<<clock_id
                <<"\",\"sample_started_ms\":"<<sample_started_ms<<",\"sample_completed_ms\":"<<nowMs()
                <<",\"clock\":\"host-monotonic-ms\",\"physical_accuracy_verified\":false,\"calibration_id\":\""<<calibration_id
                <<"\",\"shunt_ohm\":"<<config.shunt_ohm<<",\"requested_current_lsb_a\":"<<config.requested_current_lsb_a
                <<",\"calibration_register\":"<<validated.calibration()<<",\"effective_current_lsb_a\":"<<validated.effectiveCurrentLsbA()
                <<",\"battery_current_sign\":"<<config.battery_current_sign<<",\"current_zero_a\":"<<config.current_zero_a
                <<",\"terminal_offset_v\":"<<config.terminal_offset_v<<",\"ina219\":"<<a<<",\"ds18b20\":"<<b<<'}'<<std::endl;
            while(running && Clock::now()<start+std::chrono::milliseconds(period))std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }
        return !running ? 130 : failed ? 1 : 0;
    }catch(const std::exception& error){std::cerr<<"capture setup failed: "<<error.what()<<'\n';return 2;}
}
