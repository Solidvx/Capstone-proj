#include "ina219_acquirer.h"
#include <gtest/gtest.h>
#include <array>
#include <limits>
#include <vector>

namespace {
struct Bus:Ads1115Transport {
    std::array<std::uint16_t,6> registers{};
    int fail_read=-1,fail_write=-1;
    bool write(const std::uint8_t* data,std::size_t count)override{
        if(count!=3||data[0]>=registers.size()||data[0]==fail_write)return false;
        registers[data[0]]=(std::uint16_t(data[1])<<8)|data[2];return true;
    }
    bool readRegister(std::uint8_t pointer,std::uint8_t* bytes,std::size_t count)override{
        if(count!=2||pointer>=registers.size()||pointer==fail_read)return false;
        bytes[0]=registers[pointer]>>8;bytes[1]=registers[pointer]&255;return true;
    }
    void sample(int shunt,int current,unsigned bus=925){
        registers[1]=static_cast<std::uint16_t>(shunt);
        registers[4]=static_cast<std::uint16_t>(current);registers[2]=(bus<<3)|2;
    }
};
Ina219Config config(){return {.1,.0001,-1,0,0};}
}

TEST(Ina219, ExplicitCalibrationAndSingleShotHaveExpectedBytes){
    Bus bus;Ina219Acquirer reader(bus,config());
    EXPECT_EQ(reader.calibration(),4096);EXPECT_NEAR(reader.effectiveCurrentLsbA(),.0001,1e-12);
    EXPECT_EQ(reader.poll().status,Ina219Status::NotStarted);
    ASSERT_TRUE(reader.start());EXPECT_EQ(bus.registers[0],0x199b);EXPECT_EQ(bus.registers[5],4096);
    EXPECT_EQ(reader.poll().status,Ina219Status::Waiting);
    bus.sample(3700,3700);const auto value=reader.poll();
    ASSERT_EQ(value.status,Ina219Status::Complete);ASSERT_TRUE(value.measurement);
    EXPECT_DOUBLE_EQ(value.measurement->bus_v,3.7);
    EXPECT_NEAR(value.measurement->terminal_v,3.737,1e-12);
    EXPECT_NEAR(value.measurement->battery_current_a,-.37,1e-12);
    EXPECT_EQ(reader.poll().status,Ina219Status::NotStarted);
}
TEST(Ina219, ReverseCurrentAndRealZeroAreMeasurements){
    for(int raw:{-3700,0,3700}){
        Bus bus;Ina219Acquirer reader(bus,config());ASSERT_TRUE(reader.start());bus.sample(raw,raw);
        const auto result=reader.poll();ASSERT_TRUE(result.measurement);
        EXPECT_NEAR(result.measurement->battery_current_a,-raw*.0001,1e-12);
    }
}
TEST(Ina219, CorrectionAndDirectionAreExplicit){
    Bus bus;auto c=config();c.battery_current_sign=1;c.current_zero_a=.001;c.terminal_offset_v=.01;
    Ina219Acquirer reader(bus,c);ASSERT_TRUE(reader.start());bus.sample(3700,3700);
    const auto value=reader.poll();ASSERT_TRUE(value.measurement);
    EXPECT_NEAR(value.measurement->battery_current_a,.369,1e-12);
    EXPECT_NEAR(value.measurement->terminal_v,3.747,1e-12);
}
TEST(Ina219, OddCalibrationUsesActualWritableRegisterScale){
    Bus bus;auto c=config();c.requested_current_lsb_a=.04096/(4095*.1);
    Ina219Acquirer reader(bus,c);EXPECT_EQ(reader.calibration(),4094);
    EXPECT_NEAR(reader.effectiveCurrentLsbA(),.04096/(4094*.1),1e-12);
}
TEST(Ina219, InvalidConfigurationCannotReachIo){
    Bus bus;
    for(double value:{0.,-1.,std::numeric_limits<double>::quiet_NaN(),std::numeric_limits<double>::infinity()}){
        auto c=config();c.shunt_ohm=value;EXPECT_THROW(Ina219Acquirer(bus,c),std::invalid_argument);
        c=config();c.requested_current_lsb_a=value;EXPECT_THROW(Ina219Acquirer(bus,c),std::invalid_argument);
    }
    for(double value:{1e-300,1e300}){auto c=config();c.requested_current_lsb_a=value;EXPECT_THROW(Ina219Acquirer(bus,c),std::invalid_argument);}
    auto c=config();c.battery_current_sign=0;EXPECT_THROW(Ina219Acquirer(bus,c),std::invalid_argument);
    c=config();c.current_zero_a=std::numeric_limits<double>::quiet_NaN();EXPECT_THROW(Ina219Acquirer(bus,c),std::invalid_argument);
    c=config();c.terminal_offset_v=std::numeric_limits<double>::infinity();EXPECT_THROW(Ina219Acquirer(bus,c),std::invalid_argument);
}
TEST(Ina219, AnyIoFailureProducesNoCurrentNotZeroAmps){
    for(int address:{0,5}){Bus bus;bus.fail_write=address;Ina219Acquirer reader(bus,config());EXPECT_FALSE(reader.start());EXPECT_FALSE(reader.poll().measurement);}
    for(int address:{0,1,2,4,5}){
        Bus bus;Ina219Acquirer reader(bus,config());ASSERT_TRUE(reader.start());bus.sample(3700,3700);bus.fail_read=address;
        const auto result=reader.poll();EXPECT_EQ(result.status,Ina219Status::IoError);EXPECT_FALSE(result.measurement);
    }
}
TEST(Ina219, ResetOverflowAndCrossRegisterMismatchAreRejected){
    for(int fault=0;fault<7;++fault){
        Bus bus;Ina219Acquirer reader(bus,config());ASSERT_TRUE(reader.start());bus.sample(3700,3700);
        if(fault==0)bus.registers[5]=0;
        if(fault==1)bus.registers[0]=0x399f;
        if(fault==2)bus.registers[2]|=1;
        if(fault==3)bus.registers[2]|=4;
        if(fault==4)bus.registers[1]=32001;
        if(fault==5)bus.registers[4]=0;
        if(fault==6)bus.registers[2]=(4001<<3)|2;
        const auto result=reader.poll();EXPECT_NE(result.status,Ina219Status::Complete);EXPECT_FALSE(result.measurement);
    }
}
TEST(Ina219, AcquisitionCanRecoverAfterFaultWithoutUsingOldValue){
    Bus bus;Ina219Acquirer reader(bus,config());ASSERT_TRUE(reader.start());bus.sample(3700,3700);bus.registers[5]=0;
    EXPECT_FALSE(reader.poll().measurement);ASSERT_TRUE(reader.start());bus.sample(0,0);
    const auto result=reader.poll();ASSERT_TRUE(result.measurement);EXPECT_DOUBLE_EQ(result.measurement->battery_current_a,0);
}
