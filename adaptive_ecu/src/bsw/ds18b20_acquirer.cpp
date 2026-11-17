#include "ds18b20_acquirer.h"

#include <sstream>
#include <string>

namespace {
bool hexByte(const std::string& text,std::uint8_t& value) {
    if (text.size()!=2)return false;
    unsigned out=0;
    for (char c:text){
        out<<=4;
        if (c>='0'&&c<='9')out+=unsigned(c-'0');
        else if (c>='a'&&c<='f')out+=unsigned(c-'a')+10;
        else if (c>='A'&&c<='F')out+=unsigned(c-'A')+10;
        else return false;
    }
    value=static_cast<std::uint8_t>(out);return true;
}
bool bytes(std::istringstream& stream,std::array<std::uint8_t,9>& out) {
    std::string token;
    for(auto& b:out)if(!(stream>>token)||!hexByte(token,b))return false;
    return true;
}
std::uint8_t crc8(const std::array<std::uint8_t,9>& bytes) {
    std::uint8_t crc=0;
    for(unsigned i=0;i<8;++i){
        auto b=bytes[i];
        for(unsigned j=0;j<8;++j){const bool mix=(crc^b)&1;crc>>=1;if(mix)crc^=0x8c;b>>=1;}
    }
    return crc;
}
}
const char* ds18b20StatusName(Ds18b20Status status) {
    switch(status){
    case Ds18b20Status::Complete:return "OK";
    case Ds18b20Status::Malformed:return "MALFORMED";
    case Ds18b20Status::CrcError:return "CRC_ERROR";
    case Ds18b20Status::RetainedValue:return "RETAINED_VALUE";
    case Ds18b20Status::RangeError:return "RANGE_ERROR";
    case Ds18b20Status::AmbiguousPowerOn:return "AMBIGUOUS_85C";
    }
    return "UNKNOWN";
}
Ds18b20Result parseDs18b20(std::string_view text) {
    Ds18b20Result result;
    if(text.empty()||text.size()>1024||text.find('\0')!=std::string_view::npos)return result;
    std::istringstream all{std::string(text)};std::string first,second,extra;
    if(!std::getline(all,first)||!std::getline(all,second))return result;
    while(std::getline(all,extra))if(!extra.empty())return result;
    std::istringstream a(first),b(second);std::array<std::uint8_t,9> retained{};
    std::string colon,crc,yes;
    if(!bytes(a,result.scratchpad)||!(a>>colon>>crc>>yes)||colon!=":"||
       crc.size()!=6||crc.substr(0,4)!="crc="||a>>extra)return result;
    std::uint8_t reported=0;
    if(!hexByte(crc.substr(4),reported))return result;
    if(yes!="YES" || reported!=result.scratchpad[8] || crc8(result.scratchpad)!=reported){
        result.status=Ds18b20Status::CrcError;return result;
    }
    std::string temp;
    if(!bytes(b,retained)||!(b>>temp)||temp.size()<3||temp.substr(0,2)!="t="||b>>extra)return result;
    if(retained!=result.scratchpad){result.status=Ds18b20Status::RetainedValue;return result;}
    const auto& raw=result.scratchpad;
    if((raw[4]&0x9f)!=0x1f||raw[5]!=0xff||raw[6]!=0x0c||raw[7]!=0x10)return result;
    unsigned word=unsigned(raw[0])|(unsigned(raw[1])<<8);
    const unsigned unused=3-((raw[4]>>5)&3);word&=~((1u<<unused)-1);
    const int signed_word=word<0x8000 ? int(word) : int(word)-65536;
    const int milli=signed_word*1000/16;
    // Match the canonical integer Linux reports, rejecting suffixes/overflow.
    if(temp.substr(2)!=std::to_string(milli))return result;
    if(milli<-55000||milli>125000){result.status=Ds18b20Status::RangeError;return result;}
    if(milli==85000){result.status=Ds18b20Status::AmbiguousPowerOn;return result;}
    result.status=Ds18b20Status::Complete;result.temperature_c=double(milli)/1000;
    return result;
}
