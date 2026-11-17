#include "ds18b20_acquirer.h"
#include <gtest/gtest.h>
#include <iomanip>
#include <sstream>

namespace {
std::string text(int raw,unsigned resolution=0x7f,const std::string& verdict="YES"){
    std::array<unsigned,9> b{{unsigned(raw)&255,(unsigned(raw)>>8)&255,0x4b,0x46,resolution,0xff,0x0c,0x10,0}};
    unsigned crc=0;
    for(unsigned i=0;i<8;++i){auto v=b[i];for(int j=0;j<8;++j){const auto mix=(crc^v)&1;crc>>=1;if(mix)crc^=0x8c;v>>=1;}}
    b[8]=crc;std::ostringstream bytes;
    for(auto v:b)bytes<<std::hex<<std::setw(2)<<std::setfill('0')<<v<<' ';
    return bytes.str()+": crc="+bytes.str().substr(24,2)+' '+verdict+'\n'+bytes.str()+"t="+std::to_string(raw*1000/16)+'\n';
}
}
TEST(Ds18b20, SignedTemperaturesAndRealZeroRequireCrcAndMatchingRetainedBytes){
    for(int raw:{-880,-161,-1,0,1,400,2000}){
        const auto value=parseDs18b20(text(raw));ASSERT_EQ(value.status,Ds18b20Status::Complete)<<raw;
        ASSERT_TRUE(value.temperature_c);EXPECT_DOUBLE_EQ(*value.temperature_c,double(raw*1000/16)/1000);
    }
}
TEST(Ds18b20, ConversionResolutionIsRespected){
    for(unsigned resolution:{0x1f,0x3f,0x5f,0x7f}){
        auto input=text(400,resolution);EXPECT_EQ(parseDs18b20(input).status,Ds18b20Status::Complete);
    }
    auto value=text(401,0x1f);EXPECT_EQ(parseDs18b20(value).status,Ds18b20Status::Malformed);
}
TEST(Ds18b20, CrcNoOrChangedScratchpadNeverUsesRetainedOldTemperature){
    auto value=parseDs18b20(text(400,0x7f,"NO"));EXPECT_EQ(value.status,Ds18b20Status::CrcError);EXPECT_FALSE(value.temperature_c);
    auto corrupted=text(400);corrupted[0]='0';EXPECT_EQ(parseDs18b20(corrupted).status,Ds18b20Status::CrcError);
    auto mismatch=text(400);mismatch[mismatch.find('\n')+1]='0';EXPECT_EQ(parseDs18b20(mismatch).status,Ds18b20Status::RetainedValue);
}
TEST(Ds18b20, Startup85AndDisconnectedMinus127AreNotNormalData){
    const auto power_on=parseDs18b20(text(1360));EXPECT_EQ(power_on.status,Ds18b20Status::AmbiguousPowerOn);EXPECT_FALSE(power_on.temperature_c);
    const auto disconnected=parseDs18b20(text(-2032));EXPECT_EQ(disconnected.status,Ds18b20Status::RangeError);EXPECT_FALSE(disconnected.temperature_c);
}
TEST(Ds18b20, MalformedAndSpoofedCrcLabelAreRejected){
    for(const auto& value:{std::string{},std::string("t=25000\n"),std::string(1025,'x'),
        std::string("00 00 00 00 00 00 00 00 00 : crc=00 YES\n00 00 00 00 00 00 00 00 00 t=0\n")})
        EXPECT_NE(parseDs18b20(value).status,Ds18b20Status::Complete);
    auto bad=text(400);bad.replace(bad.find("t="),2,"x=");EXPECT_EQ(parseDs18b20(bad).status,Ds18b20Status::Malformed);
    bad=text(400);bad+="extra\n";EXPECT_EQ(parseDs18b20(bad).status,Ds18b20Status::Malformed);
    bad=text(400);bad[bad.find("crc=")+4]='0';EXPECT_EQ(parseDs18b20(bad).status,Ds18b20Status::CrcError);
    bad=text(400);bad.replace(bad.find("25000"),5,"25000suffix");EXPECT_EQ(parseDs18b20(bad).status,Ds18b20Status::Malformed);
}
