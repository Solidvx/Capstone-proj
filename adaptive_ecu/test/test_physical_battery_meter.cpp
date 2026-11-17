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

TEST(PhysicalSoh, ConfirmedCapacityIntervalEstimatesNinetyPercentWithoutUsingSoc){
    PhysicalBatteryMeter meter(config());auto start=meter.state();start.discharged_ah=.1;
    auto end=start;end.discharged_ah=.1+2.295;
    // Deliberately unknown SOC: the capacity result must be independent of it.
    start.estimated_soc.reset();end.estimated_soc.reset();
    const auto result=estimatePhysicalSoh(start,end,true);
    ASSERT_EQ(result.status,PhysicalSohStatus::Estimated);ASSERT_TRUE(result.display_percent);
    EXPECT_NEAR(*result.usable_capacity_ah,2.295,1e-12);EXPECT_NEAR(*result.capacity_ratio,.9,1e-12);
    EXPECT_NEAR(*result.display_percent,90,1e-12);
}
TEST(PhysicalSoh, PartialOrMissingCapacityDoesNotInventOneHundredPercent){
    PhysicalBatteryMeter meter(config());auto start=meter.state();auto end=start;end.discharged_ah=.001;
    const auto result=estimatePhysicalSoh(start,end,false);
    EXPECT_EQ(result.status,PhysicalSohStatus::AwaitingCapacityTest);EXPECT_FALSE(result.display_percent);
    EXPECT_FALSE(result.usable_capacity_ah);EXPECT_FALSE(result.capacity_ratio);
    EXPECT_EQ(estimatePhysicalSoh(start,start,true).status,PhysicalSohStatus::InvalidCapacity);
}
TEST(PhysicalSoh, GapChargeReversalAndDifferentModelCannotQualifyCapacity){
    PhysicalBatteryMeter meter(config());auto start=meter.state();auto end=start;end.discharged_ah=2.295;
    end.observation_gap=true;EXPECT_EQ(estimatePhysicalSoh(start,end,true).status,PhysicalSohStatus::ObservationGap);
    end.observation_gap=false;end.charged_ah=.01;EXPECT_EQ(estimatePhysicalSoh(start,end,true).status,PhysicalSohStatus::InvalidCapacity);
    end.charged_ah=0;end.config.nominal_capacity_ah=50;EXPECT_EQ(estimatePhysicalSoh(start,end,true).status,PhysicalSohStatus::IncompatibleModel);
    end.config=start.config;end.config.model_calibration_id="OTHER";
    EXPECT_EQ(estimatePhysicalSoh(start,end,true).status,PhysicalSohStatus::IncompatibleModel);
}
TEST(PhysicalSoh, RealCapacityAboveNominalRetainsRawRatioAndBoundsUiPercentage){
    PhysicalBatteryMeter meter(config());auto start=meter.state();auto end=start;end.discharged_ah=2.6;
    const auto result=estimatePhysicalSoh(start,end,true);ASSERT_TRUE(result.capacity_ratio);
    EXPECT_GT(*result.capacity_ratio,1);EXPECT_DOUBLE_EQ(*result.display_percent,100);
    EXPECT_DOUBLE_EQ(*result.usable_capacity_ah,2.6);
}
TEST(PhysicalSoh, NonfiniteOrRolledBackAccumulationHasNoEstimate){
    PhysicalBatteryMeter meter(config());auto start=meter.state();auto end=start;
    for(double invalid:{-1.,std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN()}){
        end.discharged_ah=invalid;EXPECT_EQ(estimatePhysicalSoh(start,end,true).status,PhysicalSohStatus::InvalidCapacity);
    }
    end=start;start.discharged_ah=1;end.discharged_ah=.5;
    EXPECT_EQ(estimatePhysicalSoh(start,end,true).status,PhysicalSohStatus::InvalidCapacity);
}
TEST(PhysicalEstimation, OneHourCurrentTraceChangesSocAndProducesIndependentCapacitySoh){
    PhysicalBatteryMeter soc_meter({"PUBLIC-SOC",2.55,.8,1000});
    soc_meter.accept(1,1000,3.7,-.255);
    for(std::uint64_t i=2;i<=3601;++i)soc_meter.accept(i,i*1000,3.7,-.255);
    ASSERT_TRUE(soc_meter.state().estimated_soc);
    EXPECT_NEAR(*soc_meter.state().estimated_soc,.7,1e-10);
    PhysicalBatteryMeter capacity_meter({"PUBLIC-CAPACITY",2.55,std::nullopt,1000});
    const auto start=capacity_meter.state();
    capacity_meter.accept(1,1000,3.7,-2.295);
    for(std::uint64_t i=2;i<=3601;++i)capacity_meter.accept(i,i*1000,3.7,-2.295);
    EXPECT_FALSE(capacity_meter.state().estimated_soc);
    const auto estimate=estimatePhysicalSoh(start,capacity_meter.state(),true);
    ASSERT_TRUE(estimate.display_percent);EXPECT_NEAR(*estimate.display_percent,90,1e-9);
}
