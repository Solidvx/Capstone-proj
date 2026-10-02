#include "vehicle_data_service.h"
#include "test_support.h"
#include <chrono>

namespace {
using namespace std::chrono_literals;
const ivi::SecOcKey key{}; // Explicit dummy key, never for deployment.
const ivi::CanPayload bms{150, 190, 0x10, 0x68, 0xff, 0xec, 65, 0};
ivi::CanPayload auth(unsigned counter, const ivi::CanPayload& p = bms,
                     unsigned id = 0x100) {
    const auto m = ivi::SecOcVerifier(key).computeTruncatedMac(id, counter, p);
    return {m[0],m[1],m[2],m[3],static_cast<unsigned char>(counter>>24),
            static_cast<unsigned char>(counter>>16),static_cast<unsigned char>(counter>>8),
            static_cast<unsigned char>(counter)};
}
void run() {
    const auto t = ivi::VehicleDataService::Clock::time_point{};
    ivi::VehicleDataService s(key);
    int notifications = 0;
    s.registerObserver([&](const auto& value) {
        ++notifications;
        EXPECT_EQ(s.latest().vehicle.valid, value.vehicle.valid); // callback outside mutex
    });
    s.processFrame(0x100, bms, t);
    s.pollTimeouts(t + 99ms);
    EXPECT_EQ(notifications, 0);
    s.pollTimeouts(t + 100ms);
    EXPECT_EQ(s.latest().pending_timeout_count, 1U);
    EXPECT_EQ(s.latest().secoc_failure_count, 1U);
    EXPECT_EQ(notifications, 1);
    s.pollTimeouts(t + 200ms);
    EXPECT_EQ(notifications, 1);
    EXPECT_FALSE(s.latest().vehicle.valid);
    s.processFrame(0x100, bms, t + 200ms);
    EXPECT_EQ(s.processFrame(0x102, auth(10), t+201ms), ivi::ProcessResult::kPublished);
    s.refreshTime(t+500ms);
    EXPECT_FALSE(s.latest().vehicle.stale);
    // Fail-safe authentication must not refresh the BMS freshness deadline.
    const ivi::CanPayload fs{0,1,1,30,65,0,0,0};
    s.processFrame(0x101, fs, t+500ms);
    s.processFrame(0x103, auth(9,fs,0x101), t+500ms);
    s.refreshTime(t+501ms);
    EXPECT_TRUE(s.latest().vehicle.stale);
    EXPECT_NEAR(s.latest().vehicle.soc_percent, 75, 0.001);
    for (unsigned counter : {10U, 9U, 111U}) {
        s.processFrame(0x100,bms,t+600ms);
        EXPECT_EQ(s.processFrame(0x102,auth(counter),t+601ms),ivi::ProcessResult::kRejected);
        const auto message=s.latest().last_message;
        const auto reason=counter==10 ? "COUNTER_REUSE" : counter==9 ? "COUNTER_BACKWARD" : "COUNTER_WINDOW";
        EXPECT_TRUE(message.find(reason)!=std::string::npos);
    }
    auto bad=auth(11); bad[0]^=1;
    s.processFrame(0x102,bad,t+602ms);
    EXPECT_TRUE(s.latest().last_message.find("MAC_FAIL")!=std::string::npos);
    for(int i=0;i<6;++i) s.processFrame(0x102,bad,t+603ms);
    EXPECT_EQ(s.latest().consecutive_secoc_failure_count,10U);
    EXPECT_TRUE(s.latest().last_message.find("CRITICAL:")==0U);
    EXPECT_NEAR(s.latest().vehicle.soc_percent,75,0.001);
    EXPECT_EQ(s.processFrame(0x102,auth(110),t+604ms),ivi::ProcessResult::kPublished); // +100
    EXPECT_EQ(s.latest().consecutive_secoc_failure_count,0U);
    EXPECT_FALSE(s.latest().vehicle.stale);
    s.processFrame(0x100,bms,t+700ms);
    EXPECT_EQ(s.processFrame(0x102,auth(111),t+699ms),ivi::ProcessResult::kRejected);
    s.setSecOcKey(key);
    EXPECT_EQ(s.processFrame(0x102,auth(111),t+701ms),ivi::ProcessResult::kRejected); // cleared pair
    s.processFrame(0x100,bms,t+702ms);
    EXPECT_EQ(s.processFrame(0x102,auth(110),t+703ms),ivi::ProcessResult::kRejected); // history retained
    ivi::VehicleDataService wrap(key);
    wrap.processFrame(0x100,bms,t);
    wrap.processFrame(0x102,auth(0xffffffffU),t);
    wrap.processFrame(0x100,bms,t+1ms);
    EXPECT_EQ(wrap.processFrame(0x102,auth(0),t+2ms),ivi::ProcessResult::kPublished);
    ivi::VehicleDataService repeated(key);
    repeated.processFrame(0x100,bms,t);
    repeated.processFrame(0x102,auth(0),t);
    for (int i=1;i<=100;++i) {
        const auto at=t+std::chrono::milliseconds{i*200};
        auto changed=bms; changed[0]=40;
        repeated.processFrame(0x100,changed,at);
        auto tampered=auth(static_cast<unsigned>(i),changed);tampered[0]^=1;
        EXPECT_EQ(repeated.processFrame(0x102,tampered,at+1ms),ivi::ProcessResult::kRejected);
        repeated.processFrame(0x100,bms,at+2ms);
        EXPECT_EQ(repeated.processFrame(0x102,auth(static_cast<unsigned>(i-1)),at+3ms),ivi::ProcessResult::kRejected);
        EXPECT_NEAR(repeated.latest().vehicle.soc_percent,75,0.001);
        EXPECT_EQ(repeated.processFrame(0x102,auth(static_cast<unsigned>(i)),at+4ms),ivi::ProcessResult::kPublished);
    }
    EXPECT_EQ(repeated.latest().secoc_failure_count,200U);
}
}
int main() { return runTestProgram("SecOC silent timeout and diagnostic delivery",run); }
