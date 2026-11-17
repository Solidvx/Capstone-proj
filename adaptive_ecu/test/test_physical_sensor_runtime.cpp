#include "physical_sensor_runtime.h"
#include "physical_measurement.h"
#include <gtest/gtest.h>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <fcntl.h>
#include <limits>
#include <thread>
#include <unistd.h>
#include <sys/stat.h>

namespace {
struct Temp {
    std::filesystem::path directory;
    Temp(){std::string name=(std::filesystem::temp_directory_path()/"physical-runtime-XXXXXX").string();
        auto* created=::mkdtemp(name.data());if(!created)throw std::runtime_error("temporary directory failed");directory=created;}
    ~Temp(){std::filesystem::remove_all(directory);}
};
std::string configText(){return
    "i2c_device=/dev/i2c-test\nina_address=64\nshunt_ohm=0.1\ncurrent_lsb_a=0.0001\n"
    "battery_current_sign=-1\ncurrent_zero_a=0\nterminal_offset_v=0\ntemperature_device=28-000000000000\n"
    "w1_root=/tmp/public-sensor-fixture\ncalibration_id=PUBLIC-UNCALIBRATED\nperiod_ms=2000\n"
    "read_timeout_ms=5000\nfreshness_ms=5000\nmax_interval_ms=3000\nnominal_capacity_ah=2.55\n"
    "initial_soc_percent=unknown\nmeasured_capacity_ah=unknown\ncapacity_test_id=unknown\n";}
PhysicalRuntimeConfig config(){Temp temp;const auto p=temp.directory/"config";std::ofstream(p)<<configText();return loadPhysicalRuntimeConfig(p.string());}
PhysicalSensorSample sample(const PhysicalRuntimeConfig& c,unsigned n,std::uint64_t at){
    PhysicalSensorSample s;s.fingerprint=c.fingerprint;s.sequence=n;s.completed_ms=at+800;s.ina_ms=at;s.temperature_ms=at+800;
    s.voltage_v=3.85;s.current_a=-.37;s.temperature_c=20.125;return s;
}
}
TEST(PhysicalRuntime,ExplicitConfigurationAndFingerprint){
    auto c=config();EXPECT_DOUBLE_EQ(c.ina.shunt_ohm,.1);EXPECT_EQ(c.ina.battery_current_sign,-1);
    EXPECT_FALSE(c.meter.initial_soc);EXPECT_FALSE(c.measured_capacity_ah);EXPECT_EQ(c.fingerprint,config().fingerprint);
    Temp temp;const auto p=temp.directory/"config";
    for(const auto& extra:{"extra=1\n","period_ms=1000\n"}){
        std::ofstream(p)<<configText()<<extra;EXPECT_THROW(loadPhysicalRuntimeConfig(p.string()),std::invalid_argument);
    }
    auto text=configText();text.replace(text.find("shunt_ohm=0.1"),13,"shunt_ohm=0");
    std::ofstream(p)<<text;EXPECT_THROW(loadPhysicalRuntimeConfig(p.string()),std::invalid_argument);
    std::ofstream(p)<<std::string(9000,'x');EXPECT_THROW(loadPhysicalRuntimeConfig(p.string()),std::invalid_argument);
}
TEST(PhysicalRuntime,PacketPreservesSignsAndRejectsNoncanonicalData){
    const auto c=config();const auto s=sample(c,1,1000);auto p=encodePhysicalSensorSample(s);
    auto parsed=decodePhysicalSensorSample(p);ASSERT_TRUE(parsed);EXPECT_DOUBLE_EQ(*parsed->current_a,-.37);
    EXPECT_DOUBLE_EQ(*parsed->voltage_v,3.85);EXPECT_DOUBLE_EQ(*parsed->temperature_c,20.125);
    p[38]=1;EXPECT_FALSE(decodePhysicalSensorSample(p));p[38]=0;p[36]=0;EXPECT_FALSE(decodePhysicalSensorSample(p));
    auto invalid=s;invalid.voltage_v=std::numeric_limits<double>::quiet_NaN();EXPECT_THROW(encodePhysicalSensorSample(invalid),std::invalid_argument);
    invalid=s;invalid.ina_ms=invalid.completed_ms+1;EXPECT_THROW(encodePhysicalSensorSample(invalid),std::invalid_argument);
}
TEST(PhysicalRuntime,NewConversionsGateDisplayAndIntegrateOnce){
    const auto c=config();PhysicalSampleFeed feed(c);
    for(unsigned i=1;i<=3;++i){const auto s=sample(c,i,i*2000);ASSERT_TRUE(feed.accept(s,s.completed_ms));
        EXPECT_FALSE(feed.accept(s,s.completed_ms));const auto v=feed.values(s.completed_ms);
        EXPECT_EQ(v.voltage_v.has_value(),i==3);EXPECT_FALSE(v.soc_percent);EXPECT_FALSE(v.soh_percent);}
    EXPECT_NEAR(feed.meterState().discharged_ah,.37*4/3600.,1e-12);
    EXPECT_FALSE(feed.meterState().observation_gap);
}
TEST(PhysicalRuntime,TemperatureFailureDoesNotStopElectricalIntegration){
    const auto c=config();PhysicalSampleFeed feed(c);
    for(unsigned i=1;i<=4;++i){auto s=sample(c,i,i*2000);if(i==4)s.temperature_c.reset();ASSERT_TRUE(feed.accept(s,s.completed_ms));}
    const auto v=feed.values(8800);EXPECT_TRUE(v.voltage_v);EXPECT_FALSE(v.temperature_c);
    EXPECT_EQ(v.temperature_quality,SensorQuality::ErrorWithValue);
    EXPECT_NEAR(feed.meterState().discharged_ah,.37*6/3600.,1e-12);EXPECT_FALSE(feed.meterState().observation_gap);
}
TEST(PhysicalRuntime,ElectricalFailureDoesNotFabricateZeroAndRecoveryRequiresThree){
    const auto c=config();PhysicalSampleFeed feed(c);
    for(unsigned i=1;i<=8;++i){auto s=sample(c,i,i*2000);
        if(i==4){s.voltage_v.reset();s.current_a.reset();}ASSERT_TRUE(feed.accept(s,s.completed_ms));
        const auto v=feed.values(s.completed_ms);if(i>=4&&i<=6)EXPECT_FALSE(v.voltage_v);
        if(i==4)EXPECT_TRUE(v.temperature_c);if(i==7)EXPECT_TRUE(v.voltage_v);
    }
    EXPECT_TRUE(feed.meterState().observation_gap);
    EXPECT_NEAR(feed.meterState().discharged_ah,.37*(4+6)/3600.,1e-12);
}
TEST(PhysicalRuntime,StaleAndForeignOrReorderedSamplesCannotRefreshValues){
    const auto c=config();PhysicalSampleFeed feed(c);
    for(unsigned i=1;i<=3;++i){const auto s=sample(c,i,i*2000);feed.accept(s,s.completed_ms);}
    EXPECT_FALSE(feed.values(12000).voltage_v);EXPECT_TRUE(feed.meterState().observation_gap);
    auto s=sample(c,4,13000);s.fingerprint[0]^=1;EXPECT_FALSE(feed.accept(s,s.completed_ms));
    EXPECT_FALSE(feed.values(s.completed_ms).voltage_v);
    s=sample(c,2,15000);EXPECT_FALSE(feed.accept(s,s.completed_ms));
    s=sample(c,4,16000);EXPECT_FALSE(feed.accept(s,s.completed_ms-1));
}
TEST(PhysicalRuntime,ExplicitSocAndIndependentCapacityStaySeparate){
    auto c=config();c.meter.initial_soc=.8;c.measured_capacity_ah=2.295;c.capacity_test_id="PUBLIC-CAPACITY-TEST";
    PhysicalSampleFeed feed(c);
    for(unsigned i=1;i<=3;++i){const auto s=sample(c,i,i*2000);feed.accept(s,s.completed_ms);}
    const auto v=feed.values(6800);ASSERT_TRUE(v.soc_percent);ASSERT_TRUE(v.soh_percent);
    EXPECT_NEAR(*v.soc_percent,80.-(.37*4/3600.)/2.55*100,1e-10);EXPECT_NEAR(*v.soh_percent,90.,1e-10);
}
TEST(PhysicalRuntime,AuthenticatedBodyKeepsUnknownDistinctFromZero){
    using namespace capstone::session_v2;PhysicalMeasurement m;
    m.instance[6]=0x40;m.instance[8]=0x80;m.configuration[0]=1;m.nominal_capacity_mah=2550;m.max_interval_ms=3000;
    auto b=encodePhysicalMeasurement(m);auto read=decodePhysicalMeasurement(b);ASSERT_TRUE(read);EXPECT_FALSE(read->soc_percent);
    m.sequence=3;m.voltage_v=3.85;m.current_a=-.3711;m.temperature_c=20.125;m.ina_quality=m.temperature_quality=2;
    m.ina_age_ms=800;m.temperature_age_ms=0;m.soc_percent=0;m.soc_basis=1;
    b=encodePhysicalMeasurement(m);read=decodePhysicalMeasurement(b);ASSERT_TRUE(read);ASSERT_TRUE(read->soc_percent);EXPECT_EQ(*read->soc_percent,0);
    EXPECT_NEAR(*read->current_a,-.3711,1e-12);EXPECT_FALSE(read->soh_percent);
    b[71]=1;EXPECT_FALSE(decodePhysicalMeasurement(b));m.soc_percent=1000;EXPECT_THROW(encodePhysicalMeasurement(m),std::invalid_argument);
}
#ifdef __linux__
TEST(PhysicalRuntime,OwnedProcessHandlesFragmentedOutputAndClosesInheritedDescriptors){
    Temp temp;const auto c=config();const auto packet=encodePhysicalSensorSample(sample(c,1,1000));
    const auto executable=temp.directory/"reader";const auto fd=::open("/dev/null",O_RDONLY);
    ASSERT_GE(fd,0);::fcntl(fd,F_SETFD,0);
    {
        std::ofstream out(executable);out<<"#!/usr/bin/python3\nimport os,time\n";
        out<<"try:\n os.fstat("<<fd<<")\n raise SystemExit(9)\nexcept OSError: pass\n";
        out<<"p=bytes([";for(auto b:packet)out<<unsigned(b)<<',';out<<"])\nos.write(1,p[:10])\ntime.sleep(.02)\nos.write(1,p[10:])\ntime.sleep(5)\n";
    }
    ::chmod(executable.c_str(),0700);
    PhysicalSensorProcess process(executable.string(),(temp.directory/"unused").string(),c.fingerprint);
    std::vector<PhysicalSensorSample> samples;
    for(unsigned i=0;i<100&&samples.empty();++i){samples=process.poll();std::this_thread::sleep_for(std::chrono::milliseconds(5));}
    EXPECT_EQ(samples.size(),1u);EXPECT_FALSE(process.failed());EXPECT_TRUE(process.stop());::close(fd);
}
TEST(PhysicalRuntime,OwnedProcessRejectsForeignPacketAndMissingExecutable){
    Temp temp;const auto c=config();auto s=sample(c,1,1000);s.fingerprint[0]^=1;const auto p=encodePhysicalSensorSample(s);
    const auto executable=temp.directory/"reader";
    {std::ofstream out(executable);out<<"#!/usr/bin/python3\nimport os,time\nos.write(1,bytes([";for(auto b:p)out<<unsigned(b)<<',';out<<"]))\ntime.sleep(5)\n";}
    ::chmod(executable.c_str(),0700);PhysicalSensorProcess process(executable.string(),"/tmp/public-config",c.fingerprint);
    for(unsigned i=0;i<100&&!process.failed();++i){EXPECT_TRUE(process.poll().empty());std::this_thread::sleep_for(std::chrono::milliseconds(5));}
    EXPECT_TRUE(process.failed());EXPECT_TRUE(process.stop());
    EXPECT_THROW(PhysicalSensorProcess("/missing/physical-reader","/tmp/public-config",c.fingerprint),std::runtime_error);
}
#endif
