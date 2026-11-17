#include "physical_sensor_runtime.h"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <limits>
#include <map>
#include <openssl/sha.h>
#include <regex>
#include <sstream>
#include <stdexcept>

namespace {
double number(const std::string& text){
    std::size_t used=0;const auto value=std::stod(text,&used);
    if(used!=text.size()||!std::isfinite(value)||text.find_first_of(" \t\r\n")!=std::string::npos)
        throw std::invalid_argument("invalid physical numeric setting");
    return value;
}
unsigned integer(const std::string& text,unsigned low,unsigned high){
    if(text.empty()||text.find_first_not_of("0123456789")!=std::string::npos)
        throw std::invalid_argument("invalid physical integer setting");
    const auto value=std::stoull(text);
    if(value<low||value>high)throw std::invalid_argument("physical setting outside bounds");
    return static_cast<unsigned>(value);
}
void put(PhysicalSensorPacket& p,unsigned at,std::uint64_t value,unsigned bytes){
    for(unsigned i=0;i<bytes;++i)p[at+i]=static_cast<std::uint8_t>(value>>(8*(bytes-1-i)));
}
std::uint64_t get(const PhysicalSensorPacket& p,unsigned at,unsigned bytes){
    std::uint64_t value=0;for(unsigned i=0;i<bytes;++i)value=(value<<8)|p[at+i];return value;
}
std::int64_t signed32(std::uint64_t value){return value>=0x80000000ull ? static_cast<std::int64_t>(value)-0x100000000ll : static_cast<std::int64_t>(value);}
bool sensible(const PhysicalSensorSample& s){
    return s.sequence && s.ina_ms<=s.completed_ms && s.temperature_ms<=s.completed_ms &&
        s.voltage_v.has_value()==s.current_a.has_value() &&
        (!s.voltage_v||(s.ina_ms && std::isfinite(*s.voltage_v)&&*s.voltage_v>=0&&*s.voltage_v<=26&&
                       std::isfinite(*s.current_a)&&std::abs(*s.current_a)<=2147)) &&
        (!s.temperature_c||(s.temperature_ms&&std::isfinite(*s.temperature_c)&&*s.temperature_c>=-55&&*s.temperature_c<=125));
}
std::uint32_t age(std::optional<double> value,std::uint64_t at,std::uint64_t now){
    if(!value||now<at)return 0xffffffffu;
    return static_cast<std::uint32_t>(std::min<std::uint64_t>(now-at,0xfffffffeu));
}
}

PhysicalRuntimeConfig loadPhysicalRuntimeConfig(const std::string& path){
    std::ifstream input(path,std::ios::binary);std::string bytes,line;char c;
    if(!input)throw std::invalid_argument("physical configuration unavailable");
    while(input.get(c)){bytes+=c;if(bytes.size()>8192)throw std::invalid_argument("physical configuration oversized");}
    if(input.bad())throw std::invalid_argument("physical configuration read failed");
    std::map<std::string,std::string> settings;std::istringstream lines(bytes);
    while(std::getline(lines,line)){
        if(line.empty()||line.front()=='#')continue;
        const auto at=line.find('=');
        if(at==std::string::npos||at==0||at+1==line.size()||
           !settings.emplace(line.substr(0,at),line.substr(at+1)).second)
            throw std::invalid_argument("invalid/duplicate physical setting");
    }
    auto take=[&](const std::string& key){
        const auto it=settings.find(key);if(it==settings.end())throw std::invalid_argument("missing physical setting: "+key);
        auto value=it->second;settings.erase(it);return value;
    };
    PhysicalRuntimeConfig result;
    result.i2c_device=take("i2c_device");result.temperature_device=take("temperature_device");
    result.w1_root=take("w1_root");result.calibration_id=take("calibration_id");
    if(result.i2c_device.front()!='/'||result.w1_root.front()!='/'||
       !std::regex_match(result.temperature_device,std::regex("28-[0-9a-f]{12}"))||
       !std::regex_match(result.calibration_id,std::regex("[A-Za-z0-9_-]{1,64}")))
        throw std::invalid_argument("physical device/calibration identity rejected");
    result.ina_address=integer(take("ina_address"),0x40,0x4f);
    result.ina.shunt_ohm=number(take("shunt_ohm"));
    result.ina.requested_current_lsb_a=number(take("current_lsb_a"));
    const auto sign=take("battery_current_sign");
    if(sign!="1"&&sign!="-1")throw std::invalid_argument("physical current sign must be explicit");
    result.ina.battery_current_sign=sign=="1"?1:-1;
    result.ina.current_zero_a=number(take("current_zero_a"));
    result.ina.terminal_offset_v=number(take("terminal_offset_v"));
    result.period_ms=integer(take("period_ms"),1,10000);
    result.read_timeout_ms=integer(take("read_timeout_ms"),1,10000);
    result.freshness_ms=integer(take("freshness_ms"),result.period_ms,60000);
    result.meter.max_interval_ms=integer(take("max_interval_ms"),result.period_ms,60000);
    result.meter.nominal_capacity_ah=number(take("nominal_capacity_ah"));
    if(result.meter.nominal_capacity_ah>4294967.)throw std::invalid_argument("capacity cannot be represented");
    const auto prior=take("initial_soc_percent");
    if(prior!="unknown")result.meter.initial_soc=number(prior)/100.;
    const auto measured=take("measured_capacity_ah");result.capacity_test_id=take("capacity_test_id");
    if(measured!="unknown"){
        result.measured_capacity_ah=number(measured);
        if(*result.measured_capacity_ah<=0||!std::regex_match(result.capacity_test_id,std::regex("[A-Za-z0-9_-]{1,64}"))||result.capacity_test_id=="unknown")
            throw std::invalid_argument("independent capacity test identity required");
    }else if(result.capacity_test_id!="unknown")throw std::invalid_argument("capacity test requires measured capacity");
    if(!settings.empty())throw std::invalid_argument("unknown physical setting: "+settings.begin()->first);
    SHA256(reinterpret_cast<const unsigned char*>(bytes.data()),bytes.size(),result.fingerprint.data());
    std::ostringstream identity;identity<<std::hex;
    for(auto b:result.fingerprint){identity.width(2);identity.fill('0');identity<<unsigned(b);}
    result.meter.model_calibration_id=identity.str();
    PhysicalBatteryMeter validated_meter(result.meter);
    struct NoIo final:Ads1115Transport{
        bool write(const std::uint8_t*,std::size_t)override{return false;}
        bool readRegister(std::uint8_t,std::uint8_t*,std::size_t)override{return false;}
    } transport;
    Ina219Acquirer validated_ina(transport,result.ina);
    return result;
}

PhysicalSensorPacket encodePhysicalSensorSample(const PhysicalSensorSample& s){
    if(!sensible(s))throw std::invalid_argument("invalid physical IPC sample");
    PhysicalSensorPacket p{};p[0]='P';p[1]='C';p[2]='B';p[3]=1;
    put(p,4,s.sequence,8);put(p,12,s.completed_ms,8);put(p,20,s.ina_ms,8);put(p,28,s.temperature_ms,8);
    p[36]=s.voltage_v.has_value();p[37]=s.temperature_c.has_value();
    auto scalar=[&](unsigned at,double value,double scale){
        const auto raw=static_cast<std::int64_t>(std::llround(value*scale));
        if(raw<std::numeric_limits<std::int32_t>::min()||raw>std::numeric_limits<std::int32_t>::max())
            throw std::invalid_argument("physical IPC scalar outside bounds");
        put(p,at,static_cast<std::uint32_t>(raw),4);
    };
    if(s.voltage_v){scalar(40,*s.voltage_v,1e6);scalar(44,*s.current_a,1e6);}
    if(s.temperature_c)scalar(48,*s.temperature_c,1000);
    std::copy(s.fingerprint.begin(),s.fingerprint.end(),p.begin()+52);return p;
}
std::optional<PhysicalSensorSample> decodePhysicalSensorSample(const PhysicalSensorPacket& p){
    if(p[0]!='P'||p[1]!='C'||p[2]!='B'||p[3]!=1||p[36]>1||p[37]>1||p[38]||p[39]||
       (!p[36]&&(get(p,40,4)||get(p,44,4)))||(!p[37]&&get(p,48,4)))return std::nullopt;
    PhysicalSensorSample s;s.sequence=get(p,4,8);s.completed_ms=get(p,12,8);s.ina_ms=get(p,20,8);s.temperature_ms=get(p,28,8);
    if(p[36]){s.voltage_v=double(signed32(get(p,40,4)))/1e6;s.current_a=double(signed32(get(p,44,4)))/1e6;}
    if(p[37])s.temperature_c=double(signed32(get(p,48,4)))/1000;
    std::copy_n(p.begin()+52,32,s.fingerprint.begin());return sensible(s)?std::optional<PhysicalSensorSample>(s):std::nullopt;
}

PhysicalSampleFeed::PhysicalSampleFeed(PhysicalRuntimeConfig config):config_(std::move(config)),meter_(config_.meter){}
void PhysicalSampleFeed::unavailable(){
    ina_current_=temperature_current_=false;ina_quality_.error();temperature_quality_.error();meter_.unavailable();
}
bool PhysicalSampleFeed::accept(const PhysicalSensorSample& s,std::uint64_t now){
    if(s.sequence==sequence_)return false;
    if(!sensible(s)||s.sequence<sequence_||s.completed_ms>now||s.fingerprint!=config_.fingerprint){unavailable();return false;}
    if(sequence_&&s.sequence!=sequence_+1){ina_quality_.error();temperature_quality_.error();meter_.unavailable();}
    sequence_=s.sequence;
    if(s.voltage_v&&now-s.ina_ms<=config_.freshness_ms&&(!voltage_||s.ina_ms>ina_ms_)){
        voltage_=s.voltage_v;current_=s.current_a;ina_ms_=s.ina_ms;ina_current_=true;ina_quality_.accept(true);
        meter_.accept(s.sequence,s.ina_ms,*voltage_,*current_);
    }else{ina_current_=false;ina_quality_.error();meter_.unavailable();}
    if(s.temperature_c&&now-s.temperature_ms<=config_.freshness_ms&&(!temperature_||s.temperature_ms>temperature_ms_)){
        temperature_=s.temperature_c;temperature_ms_=s.temperature_ms;temperature_current_=true;temperature_quality_.accept(true);
    }else{temperature_current_=false;temperature_quality_.error();}
    return true;
}
PhysicalLiveValues PhysicalSampleFeed::values(std::uint64_t now){
    PhysicalLiveValues v;v.sequence=sequence_;
    v.ina_age_ms=age(voltage_,ina_ms_,now);v.temperature_age_ms=age(temperature_,temperature_ms_,now);
    if(ina_current_&&v.ina_age_ms>config_.freshness_ms){ina_current_=false;ina_quality_.error();meter_.unavailable();}
    if(temperature_current_&&v.temperature_age_ms>config_.freshness_ms){temperature_current_=false;temperature_quality_.error();}
    v.ina_quality=ina_quality_.state();v.temperature_quality=temperature_quality_.state();
    if(ina_current_&&v.ina_quality==SensorQuality::Valid){
        v.voltage_v=voltage_;v.current_a=current_;
        if(meter_.state().estimated_soc)v.soc_percent=*meter_.state().estimated_soc*100;
    }
    if(temperature_current_&&v.temperature_quality==SensorQuality::Valid)v.temperature_c=temperature_;
    if(config_.measured_capacity_ah)v.soh_percent=std::clamp(*config_.measured_capacity_ah/config_.meter.nominal_capacity_ah,0.,1.)*100;
    return v;
}
