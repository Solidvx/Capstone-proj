#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <optional>
#include <stdexcept>
#include <vector>

namespace capstone::session_v2 {
struct PhysicalMeasurement {
    std::array<std::uint8_t,16> instance{},configuration{};
    std::uint64_t sequence=0;
    std::optional<double> voltage_v,current_a,temperature_c,soc_percent,soh_percent;
    std::uint32_t ina_age_ms=0xffffffffu,temperature_age_ms=0xffffffffu;
    std::uint8_t soc_basis=0,soh_basis=0,ina_quality=1,temperature_quality=1;
    bool observation_gap=false;
    std::uint32_t nominal_capacity_mah=0,max_interval_ms=0;
};
namespace physical_detail {
inline std::uint64_t get(const std::vector<std::uint8_t>& b,unsigned at,unsigned n){
    std::uint64_t value=0;for(unsigned i=0;i<n;++i)value=(value<<8)|b[at+i];return value;
}
inline std::int64_t signed32(std::uint64_t n){return n>=0x80000000ull?static_cast<std::int64_t>(n)-0x100000000ll:static_cast<std::int64_t>(n);}
inline void put(std::vector<std::uint8_t>& b,unsigned at,std::uint64_t value,unsigned n){
    for(unsigned i=0;i<n;++i)b[at+i]=static_cast<std::uint8_t>(value>>(8*(n-1-i)));
}
}
inline std::optional<PhysicalMeasurement> decodePhysicalMeasurement(const std::vector<std::uint8_t>& b){
    using physical_detail::get;
    if(b.size()!=80||(b[6]&0xf0)!=0x40||(b[8]&0xc0)!=0x80||
       std::all_of(b.begin()+16,b.begin()+32,[](auto v){return v==0;})||
       b[64]!=1||b[65]>31||b[66]>2||b[67]>1||b[68]<1||b[68]>6||b[69]<1||b[69]>6||b[70]>1||b[71]||
       !get(b,72,4)||!get(b,76,4)||get(b,76,4)>60000)return std::nullopt;
    const auto flags=b[65];
    if((flags&3)!=0&&(flags&3)!=3)return std::nullopt;
    if(bool(flags&3)!=(b[68]==2)||bool(flags&4)!=(b[69]==2)||
       ((flags&8)&&(!(flags&3)||!b[66]))||bool(flags&16)!=(b[67]==1)||
       ((flags&3)&&get(b,56,4)==0xffffffffu)||((flags&4)&&get(b,60,4)==0xffffffffu))return std::nullopt;
    if(!get(b,32,8)&&((flags&15)||(b[68]!=1&&b[68]!=3)||(b[69]!=1&&b[69]!=3)||get(b,56,4)!=0xffffffffu||get(b,60,4)!=0xffffffffu))return std::nullopt;
    PhysicalMeasurement m;std::copy_n(b.begin(),16,m.instance.begin());std::copy_n(b.begin()+16,16,m.configuration.begin());
    m.sequence=get(b,32,8);m.ina_age_ms=get(b,56,4);m.temperature_age_ms=get(b,60,4);
    m.soc_basis=b[66];m.soh_basis=b[67];m.ina_quality=b[68];m.temperature_quality=b[69];m.observation_gap=b[70];
    m.nominal_capacity_mah=get(b,72,4);m.max_interval_ms=get(b,76,4);
    for(unsigned i=0;i<5;++i){
        const auto at=i<3?40+4*i:52+2*(i-3);const auto raw=get(b,at,i<3?4:2);
        if(!(flags&(1<<i))){if(raw)return std::nullopt;continue;}
        const double value=i<3?double(physical_detail::signed32(raw))/(i==2?1000.:1e6):double(raw)/100.;
        if((i==0&&(value<0||value>26))||(i==1&&std::abs(value)>2147)||
           (i==2&&(value< -55||value>125))||(i>=3&&value>100))return std::nullopt;
        switch(i){case 0:m.voltage_v=value;break;case 1:m.current_a=value;break;case 2:m.temperature_c=value;break;
            case 3:m.soc_percent=value;break;case 4:m.soh_percent=value;break;}
    }
    return m;
}
inline std::vector<std::uint8_t> encodePhysicalMeasurement(const PhysicalMeasurement& m){
    using physical_detail::put;
    std::vector<std::uint8_t> b(80,0);std::copy(m.instance.begin(),m.instance.end(),b.begin());
    std::copy(m.configuration.begin(),m.configuration.end(),b.begin()+16);put(b,32,m.sequence,8);
    const std::array<std::optional<double>,5> values{m.voltage_v,m.current_a,m.temperature_c,m.soc_percent,m.soh_percent};
    for(unsigned i=0;i<5;++i)if(values[i]){
        if(!std::isfinite(*values[i]))throw std::invalid_argument("nonfinite physical measurement");
        const auto v=*values[i];
        if((i==0&&(v<0||v>26))||(i==1&&std::abs(v)>2147)||(i==2&&(v< -55||v>125))||(i>=3&&(v<0||v>100)))
            throw std::invalid_argument("physical measurement outside bounds");
        const double scaled=*values[i]*(i<2?1e6:i==2?1000.:100.);
        if(scaled< -2147483648.||scaled>2147483647.)throw std::invalid_argument("physical measurement overflow");
        const auto raw=static_cast<std::int64_t>(std::llround(scaled));
        b[65]|=1<<i;put(b,i<3?40+4*i:52+2*(i-3),static_cast<std::uint32_t>(raw),i<3?4:2);
    }
    put(b,56,m.ina_age_ms,4);put(b,60,m.temperature_age_ms,4);b[64]=1;
    b[66]=m.soc_basis;b[67]=m.soh_basis;b[68]=m.ina_quality;b[69]=m.temperature_quality;b[70]=m.observation_gap;
    put(b,72,m.nominal_capacity_mah,4);put(b,76,m.max_interval_ms,4);
    if(!decodePhysicalMeasurement(b))throw std::invalid_argument("invalid physical measurement body");return b;
}
}
