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

namespace {
PhysicalMeterConfig automaticConfig(){auto c=config();c.initial_soc.reset();c.automatic_soc=true;return c;}
void resting(PhysicalBatteryMeter& meter,double voltage,std::uint64_t first=1,unsigned count=61){
    for(std::uint64_t n=first;n<first+count;++n)meter.accept(n,n*1000,voltage,0);
}
}
TEST(PhysicalAutoSoc, StableRestInitializesFromReferenceWithoutInventingSoh){
    PhysicalBatteryMeter meter(automaticConfig());
    resting(meter,3.820965,1,60);EXPECT_FALSE(meter.state().estimated_soc);
    meter.accept(61,61000,3.820965,0);
    ASSERT_TRUE(meter.state().estimated_soc);EXPECT_NEAR(*meter.state().estimated_soc,.5,1e-12);
    EXPECT_EQ(meter.socBasis(),2u);EXPECT_STREQ(meter.socUpdate(),"initialized");
    ASSERT_TRUE(meter.socCovariance());EXPECT_GT(*meter.socCovariance(),0);
    EXPECT_EQ(estimatePhysicalSoh(meter.state(),meter.state(),false).status,PhysicalSohStatus::AwaitingCapacityTest);
    // A partial SOC-only restore cannot masquerade as complete EKF recovery.
    PhysicalBatteryMeter restarted(automaticConfig());EXPECT_FALSE(restarted.restore(meter.state()));
    EXPECT_FALSE(restarted.state().estimated_soc);
}
TEST(PhysicalAutoSoc, LoadedOrDriftingVoltageCannotInitialize){
    PhysicalBatteryMeter meter(automaticConfig());
    for(unsigned n=1;n<=80;++n)meter.accept(n,n*1000,3.820965,-.37);
    EXPECT_FALSE(meter.state().estimated_soc);
    for(unsigned n=81;n<=160;++n)meter.accept(n,n*1000,n%2?3.80:3.84,0);
    EXPECT_FALSE(meter.state().estimated_soc);
    resting(meter,3.820965,161);ASSERT_TRUE(meter.state().estimated_soc);
    EXPECT_NEAR(*meter.state().estimated_soc,.5,1e-12);
}
TEST(PhysicalAutoSoc, PredictionUsesMeasuredChargeAndVoltageCorrectionNeedsAnotherRestWindow){
    PhysicalBatteryMeter meter(automaticConfig());resting(meter,3.820965);
    const auto initial_covariance=*meter.socCovariance();
    // Loaded terminal voltage is deliberately inconsistent: it must not be
    // mistaken for OCV or pull SOC toward zero during discharge.
    for(std::uint64_t n=62;n<=3661;++n)meter.accept(n,n*1000,3.1,-.255);
    const double predicted=.5-.255*3599.5/3600/2.55;
    EXPECT_NEAR(*meter.state().estimated_soc,predicted,1e-10);
    EXPECT_GT(*meter.socCovariance(),initial_covariance);EXPECT_STREQ(meter.socUpdate(),"predicted");
    resting(meter,3.884009,3662,60);const auto before=*meter.state().estimated_soc;
    meter.accept(3722,3722000,3.884009,0);
    EXPECT_GT(*meter.state().estimated_soc,before);EXPECT_LE(*meter.state().estimated_soc,1);
    EXPECT_LT(*meter.socCovariance(),initial_covariance);EXPECT_STREQ(meter.socUpdate(),"corrected");
}
TEST(PhysicalAutoSoc, GapAndDuplicateCannotFakeACompletedRestWindow){
    PhysicalBatteryMeter meter(automaticConfig());resting(meter,3.820965,1,30);
    EXPECT_EQ(meter.accept(30,100000,3.820965,0),PhysicalMeterResult::Duplicate);
    EXPECT_FALSE(meter.state().estimated_soc);
    EXPECT_EQ(meter.accept(31,100000,3.820965,0),PhysicalMeterResult::Gap);
    EXPECT_FALSE(meter.state().estimated_soc);
    meter.unavailable();
    for(std::uint64_t n=32;n<92;++n)meter.accept(n,100000+(n-31)*1000,3.820965,0);
    EXPECT_FALSE(meter.state().estimated_soc);
    meter.accept(92,161000,3.820965,0);EXPECT_TRUE(meter.state().estimated_soc);
}
TEST(PhysicalAutoSoc, NoCellAndOutOfModelVoltagesStayUnknownAndEndpointsAreBounded){
    for(double voltage:{0.,2.5,2.66,4.5}){
        PhysicalBatteryMeter meter(automaticConfig());resting(meter,voltage);
        EXPECT_FALSE(meter.state().estimated_soc);
        EXPECT_STREQ(meter.socUpdate(),"voltage-out-of-range");
    }
    for(double voltage:{3.,4.2}){
        PhysicalBatteryMeter meter(automaticConfig());resting(meter,voltage);
        ASSERT_TRUE(meter.state().estimated_soc);EXPECT_DOUBLE_EQ(*meter.state().estimated_soc,voltage==3.?0.:1.);
    }
    auto conflict=automaticConfig();conflict.initial_soc=.5;
    EXPECT_THROW(PhysicalBatteryMeter{conflict},std::invalid_argument);
    PhysicalBatteryMeter removed(automaticConfig());resting(removed,3.820965);
    ASSERT_TRUE(removed.state().estimated_soc);
    removed.accept(62,62000,0,0);EXPECT_FALSE(removed.state().estimated_soc);
    EXPECT_STREQ(removed.socUpdate(),"voltage-out-of-range");
    resting(removed,3.820965,63,60);EXPECT_FALSE(removed.state().estimated_soc);
    EXPECT_STREQ(removed.socUpdate(),"waiting-rest");
    removed.accept(123,123000,3.820965,0);EXPECT_TRUE(removed.state().estimated_soc);
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
