#include "physical_battery_meter.h"
#include <gtest/gtest.h>
#include <limits>

namespace {PhysicalMeterConfig config(){return {"PUBLIC-MODEL-CALIBRATION",2.55,.5,1000};}}
TEST(PhysicalMeter, ActualIrregularSampleTimesIntegrateBeforeWireRounding){
    PhysicalBatteryMeter meter(config());
    EXPECT_EQ(meter.accept(1,1000,3.7,-.37),PhysicalMeterResult::Anchored);
    EXPECT_EQ(meter.accept(2,1300,3.7,-.37),PhysicalMeterResult::Integrated);
    EXPECT_EQ(meter.accept(3,2000,3.7,-.37),PhysicalMeterResult::Integrated);
    EXPECT_NEAR(meter.state().discharged_ah,.37/3600,1e-15);
    EXPECT_NEAR(meter.state().signed_energy_wh,-3.7*.37/3600,1e-15);
    ASSERT_TRUE(meter.state().estimated_soc);EXPECT_NEAR(*meter.state().estimated_soc,.5-.37/3600/2.55,1e-15);
}
TEST(PhysicalMeter, UnknownInitialSocStaysUnknownAndNoSohIsInvented){
    auto c=config();c.initial_soc.reset();PhysicalBatteryMeter meter(c);
    meter.accept(1,1000,3.7,-.37);meter.accept(2,2000,3.7,-.37);
    EXPECT_GT(meter.state().discharged_ah,0);EXPECT_FALSE(meter.state().estimated_soc);
}
TEST(PhysicalMeter, DuplicateGapAndUnavailableDoNotDoubleCountOrInventMissingCharge){
    PhysicalBatteryMeter meter(config());meter.accept(1,1000,3.7,-.37);meter.accept(2,2000,3.7,-.37);
    const auto charge=meter.state().discharged_ah;
    EXPECT_EQ(meter.accept(2,3000,3.7,-.37),PhysicalMeterResult::Duplicate);
    EXPECT_EQ(meter.accept(3,10000,3.7,-.37),PhysicalMeterResult::Gap);
    EXPECT_DOUBLE_EQ(meter.state().discharged_ah,charge);EXPECT_TRUE(meter.state().observation_gap);
    meter.unavailable();EXPECT_EQ(meter.accept(4,11000,3.7,-.37),PhysicalMeterResult::Anchored);
    EXPECT_DOUBLE_EQ(meter.state().discharged_ah,charge);
}
TEST(PhysicalMeter, DirectionChangeTracksChargingAndDischargingSeparately){
    PhysicalBatteryMeter meter(config());meter.accept(1,1000,4,-1);meter.accept(2,2000,4,1);
    EXPECT_NEAR(meter.state().charged_ah,.25/3600,1e-15);
    EXPECT_NEAR(meter.state().discharged_ah,.25/3600,1e-15);
    EXPECT_DOUBLE_EQ(*meter.state().estimated_soc,.5);
}
TEST(PhysicalMeter, InvalidTimeAndValuesBreakIntegration){
    for(unsigned fault=0;fault<4;++fault){
        PhysicalBatteryMeter meter(config());meter.accept(1,1000,3.7,-.37);
        const auto result=fault==0?meter.accept(2,999,3.7,-.37):
            fault==1?meter.accept(2,2000,std::numeric_limits<double>::quiet_NaN(),-.37):
            fault==2?meter.accept(2,2000,3.7,std::numeric_limits<double>::infinity()):meter.accept(0,2000,3.7,-.37);
        EXPECT_EQ(result,PhysicalMeterResult::Rejected);EXPECT_DOUBLE_EQ(meter.state().discharged_ah,0);
        EXPECT_TRUE(meter.state().observation_gap);
    }
}
TEST(PhysicalMeter, RestoringOnlyTheSameModelDoesNotIntegrateDowntime){
    PhysicalBatteryMeter a(config());a.accept(1,1000,3.7,-.37);a.accept(2,2000,3.7,-.37);
    const auto saved=a.state();PhysicalBatteryMeter b(config());ASSERT_TRUE(b.restore(saved));
    EXPECT_TRUE(b.state().observation_gap);b.accept(1,50000,3.7,-.37);EXPECT_DOUBLE_EQ(b.state().discharged_ah,saved.discharged_ah);
    auto different=config();different.nominal_capacity_ah=50;PhysicalBatteryMeter wrong(different);EXPECT_FALSE(wrong.restore(saved));
    different=config();different.model_calibration_id="OTHER";PhysicalBatteryMeter other(different);EXPECT_FALSE(other.restore(saved));
    auto bad=saved;bad.charged_ah=-1;EXPECT_FALSE(b.restore(bad));
    bad=saved;bad.estimated_soc.reset();EXPECT_FALSE(b.restore(bad));
}
TEST(PhysicalMeter, InvalidModelAndPriorAreRejected){
    for(double value:{0.,-1.,std::numeric_limits<double>::quiet_NaN()}){auto c=config();c.nominal_capacity_ah=value;EXPECT_THROW(PhysicalBatteryMeter{c},std::invalid_argument);}
    for(double value:{-.1,1.1,std::numeric_limits<double>::infinity()}){auto c=config();c.initial_soc=value;EXPECT_THROW(PhysicalBatteryMeter{c},std::invalid_argument);}
    auto c=config();c.max_interval_ms=0;EXPECT_THROW(PhysicalBatteryMeter{c},std::invalid_argument);
}
