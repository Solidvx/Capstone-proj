#include "physical_soh_tracker.h"
#include <gtest/gtest.h>
#include <filesystem>
#include <fstream>
#include <unistd.h>
namespace {
struct SohFixture {
    std::string path=(std::filesystem::temp_directory_path()/("soh-test-"+std::to_string(getpid()))).string();
    std::uint64_t seq=0,at=0;
    SohFixture(){std::filesystem::remove(path);}
    ~SohFixture(){std::filesystem::remove(path);}
    void rest(PhysicalSohTracker& s,double v,double t=20){for(unsigned n=0;n<=1800;++n)s.accept(++seq,at+=1000,v,0,t);}
    void discharge(PhysicalSohTracker& s){for(unsigned n=0;n<3600;++n)s.accept(++seq,at+=1000,3.8,-.6,20);}
};
}
TEST(PhysicalSoh,UpdatesFromIndependentVoltageEndpointsAndPersistsOnlyEstimate){
    SohFixture r;PhysicalSohTracker s(81,2.55,3000,r.path,"public-test");
    r.rest(s,4.008118);r.discharge(s);r.rest(s,3.820965);
    // OCV endpoints are 80% and 50%, independent of coulomb SOC.
    ASSERT_EQ(s.updates(),1u);EXPECT_NEAR(s.percent(),.8*81+.2*(.6/.3/2.55*100),.01);
    PhysicalSohTracker restored(81,2.55,3000,r.path,"public-test");
    EXPECT_DOUBLE_EQ(s.percent(),restored.percent());EXPECT_EQ(restored.updates(),1u);
    r.discharge(restored);r.rest(restored,3.783504);
    EXPECT_EQ(restored.updates(),1u); // no anchor survives a restart
}
TEST(PhysicalSoh,GapAndChargingInvalidateIntervalWithoutErasingPrior){
    for(bool charge:{false,true}){
        SohFixture r;PhysicalSohTracker s(81,2.55,3000,r.path,"public-test");
        r.rest(s,4.008118);r.discharge(s);
        if(charge)s.accept(++r.seq,r.at+=1000,3.8,.1,20);else s.unavailable();
        r.rest(s,3.820965);EXPECT_EQ(s.updates(),0u);EXPECT_EQ(s.percent(),81);
    }
}
TEST(PhysicalSoh,RestOnlyAndInsufficientSpanDoNotCreateUpdates){
    SohFixture r;PhysicalSohTracker s(81,2.55,3000,r.path,"public-test");
    r.rest(s,4.008118);r.rest(s,4.008118);EXPECT_EQ(s.updates(),0u);
    for(unsigned n=0;n<60;++n)s.accept(++r.seq,r.at+=1000,3.8,-.6,20);
    r.rest(s,3.820965);EXPECT_EQ(s.updates(),0u);
}
TEST(PhysicalSoh,TemperatureMismatchAndImplausibleCapacityAreRejected){
    for(bool temperature:{false,true}){
        SohFixture r;PhysicalSohTracker s(81,2.55,3000,r.path,"public-test");
        r.rest(s,4.008118);r.discharge(s);
        if(!temperature)r.discharge(s); // >100% raw candidate must not clamp to 100
        r.rest(s,3.820965,temperature?24:20);EXPECT_EQ(s.updates(),0u);EXPECT_EQ(s.percent(),81);
    }
}
TEST(PhysicalSoh,CorruptStateFailsExplicitly){
    SohFixture r;std::ofstream(r.path)<<"broken";
    EXPECT_THROW(PhysicalSohTracker(81,2.55,3000,r.path,"public-test"),std::invalid_argument);
}
TEST(PhysicalSoh,MissingSequenceAndLongIntervalCannotBridgeDischarge){
    for(bool missing:{false,true}){
        SohFixture r;PhysicalSohTracker s(81,2.55,3000,r.path,"public-test");
        r.rest(s,4.008118);r.discharge(s);
        if(missing)++r.seq;else r.at+=4000;
        r.rest(s,3.820965);EXPECT_EQ(s.updates(),0u);EXPECT_EQ(s.percent(),81);
    }
}
TEST(PhysicalSoh,FailedSaveDoesNotPublishUnpersistedUpdate){
    SohFixture r;PhysicalSohTracker s(81,2.55,3000,r.path+"/missing/state","public-test");
    r.rest(s,4.008118);r.discharge(s);r.rest(s,3.820965);
    EXPECT_EQ(s.updates(),0u);EXPECT_EQ(s.percent(),81);EXPECT_STREQ(s.status(),"held-save-error");
}
TEST(PhysicalSoh,DuplicateRestDoesNotConsumeTheSameDischargeTwice){
    SohFixture r;PhysicalSohTracker s(81,2.55,3000,r.path,"public-test");
    r.rest(s,4.008118);r.discharge(s);r.rest(s,3.820965);
    const auto value=s.percent();r.rest(s,3.820965);r.rest(s,3.820965);
    EXPECT_EQ(s.updates(),1u);EXPECT_EQ(s.percent(),value);
    EXPECT_THROW(PhysicalSohTracker(81,2.55,3000,r.path,"different-config"),std::invalid_argument);
}
