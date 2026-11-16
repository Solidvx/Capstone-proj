#include "can_publisher.h"
#include "can_cdd.h"
#include "can_tx_trace.h"
#include <cerrno>
#include <csignal>
#include <fcntl.h>
#include <unistd.h>

#include <gtest/gtest.h>

namespace {
struct TxPipe {
    int reader=-1,writer=-1;
    TxPipe(){int fd[2];if(::pipe(fd)!=0)throw std::runtime_error("pipe failed");
        reader=fd[0];writer=fd[1];
        for(int value:fd)if(::fcntl(value,F_SETFL,::fcntl(value,F_GETFL)|O_NONBLOCK)!=0)
            throw std::runtime_error("nonblocking pipe failed");}
    ~TxPipe(){if(reader>=0)::close(reader);if(writer>=0)::close(writer);}
    int giveWriter(){const int result=writer;writer=-1;return result;}
    std::string drain(){std::string result;char bytes[1024];
        for(;;){const auto n=::read(reader,bytes,sizeof bytes);if(n<=0)break;result.append(bytes,static_cast<std::size_t>(n));}
        return result;}
};
const std::array<std::uint8_t,16> kTraceInstance{{1,2,3,4,5,6,0x47,8,0x89,10,11,12,13,14,15,16}};
}

TEST(CanTxTrace, FixedPipeRecordCounterTimeAndClosedDriverPrecheck) {
    TxPipe pipe;const int transferred=pipe.writer;
    {
        SocketCanCdd driver;driver.enableTxTrace(pipe.giveWriter(),kTraceInstance);
        CanFrame frame{0x102,8,{{0,0,0,0,0xff,0xff,0xff,0xff}}};
        errno=ENOTTY;
        EXPECT_FALSE(driver.send(frame));EXPECT_EQ(errno,ENOTTY);
        const auto record=pipe.drain();
        EXPECT_LT(record.size(),512u);
        EXPECT_NE(record.find("\"counter\":4294967295"),std::string::npos);
        EXPECT_NE(record.find("\"syscall_attempted\":false"),std::string::npos);
        EXPECT_NE(record.find("\"kernel_accepted\":false"),std::string::npos);
        EXPECT_NE(record.find("\"error_number\":"+std::to_string(EBADF)),std::string::npos);
        EXPECT_NE(record.find("\"sequence\":1"),std::string::npos);
        EXPECT_NE(record.find("\"started_ns\":"),std::string::npos);
        EXPECT_NE(record.find("\"ended_ns\":"),std::string::npos);
        EXPECT_THROW(driver.enableTxTrace(transferred,kTraceInstance),std::logic_error);
    }
    const auto end=pipe.drain();
    EXPECT_NE(end.find("\"result\":\"ECU_CAN_TX_END\""),std::string::npos);
    EXPECT_NE(end.find("\"attempts\":1"),std::string::npos);
    EXPECT_EQ(::fcntl(transferred,F_GETFD),-1);EXPECT_EQ(errno,EBADF);
}

TEST(CanTxTrace, BackpressureDropsEvidenceWithoutRetryAndNextRecordPreservesGap) {
    TxPipe pipe;const int fd=pipe.writer;
    CanTxTrace trace(pipe.giveWriter(),kTraceInstance);
    std::array<char,512> padding{};
    while(::write(fd,padding.data(),padding.size())==static_cast<ssize_t>(padding.size())){}
    ASSERT_TRUE(errno==EAGAIN || errno==EWOULDBLOCK);
    CanFrame frame{0x100,8,{}};
    errno=ENOTTY;trace.complete(trace.begin(),frame,true,16,0,true);
    EXPECT_EQ(errno,ENOTTY);EXPECT_EQ(trace.dropped(),1u);
    pipe.drain();
    trace.complete(trace.begin(),frame,true,-1,ENOBUFS,false);
    const auto record=pipe.drain();
    EXPECT_NE(record.find("\"sequence\":2"),std::string::npos);
    EXPECT_NE(record.find("\"records_dropped\":1"),std::string::npos);
    EXPECT_NE(record.find("\"error_number\":"+std::to_string(ENOBUFS)),std::string::npos);
    EXPECT_NE(record.find("\"counter\":null"),std::string::npos);
}

TEST(CanTxTrace, DisconnectedReaderAndInvalidDescriptorDoNotMasqueradeAsDelivery) {
    TxPipe pipe;
    EXPECT_THROW(CanTxTrace::validateFd(pipe.reader),std::invalid_argument);
    ASSERT_EQ(::fcntl(pipe.writer,F_SETFL,::fcntl(pipe.writer,F_GETFL)&~O_NONBLOCK),0);
    EXPECT_THROW(CanTxTrace::validateFd(pipe.writer),std::invalid_argument);
    ASSERT_EQ(::fcntl(pipe.writer,F_SETFL,::fcntl(pipe.writer,F_GETFL)|O_NONBLOCK),0);
    const auto prior=std::signal(SIGPIPE,SIG_IGN);
    {
        CanTxTrace trace(pipe.giveWriter(),kTraceInstance);
        ::close(pipe.reader);pipe.reader=-1;
        trace.complete(trace.begin(),CanFrame{},false,-1,EINVAL,false);
        EXPECT_EQ(trace.dropped(),1u);
    }
    std::signal(SIGPIPE,prior);
}
#ifdef __linux__
#include "ecu_sender_gate.h"
#include <vector>

namespace {
struct SenderControlPipe {
    int fd[2]{-1,-1};
    SenderControlPipe(){if(::pipe2(fd,O_NONBLOCK|O_CLOEXEC)!=0)throw std::runtime_error("pipe failed");}
    ~SenderControlPipe(){for(auto value:fd)if(value>=0)::close(value);}
    int reader(){const auto value=fd[0];fd[0]=-1;return value;}
    void command(char value){ASSERT_EQ(::write(fd[1],&value,1),1);}
    void eof(){::close(fd[1]);fd[1]=-1;}
};
}

TEST(TestSenderGate, PauseResumeRetainsNonblockingNormalCalculationBoundary) {
    SenderControlPipe pipe;std::vector<bool> states;
    TestSenderGate gate(pipe.reader(),[&](bool paused,const char*,std::uint64_t){states.push_back(paused);});
    EXPECT_FALSE(gate.paused(1));pipe.command('P');EXPECT_TRUE(gate.paused(10));
    EXPECT_TRUE(gate.paused(11));pipe.command('R');EXPECT_FALSE(gate.paused(20));
    EXPECT_EQ(states,(std::vector<bool>{true,false}));
}

TEST(TestSenderGate, RepeatedPauseCannotExtendGuardAndDeadlineClosesChannel) {
    SenderControlPipe pipe;std::vector<std::string> reasons;
    TestSenderGate gate(pipe.reader(),[&](bool,const char* reason,std::uint64_t){reasons.emplace_back(reason);});
    pipe.command('P');EXPECT_TRUE(gate.paused(100));pipe.command('P');EXPECT_TRUE(gate.paused(2099));
    EXPECT_FALSE(gate.paused(2100));EXPECT_FALSE(gate.paused(2200));
    EXPECT_EQ(reasons,(std::vector<std::string>{"pause","deadline"}));
}

TEST(TestSenderGate, ControllerEofOrInvalidCommandResumesInsteadOfLeavingSenderStopped) {
    for(bool invalid:{false,true}){
        SenderControlPipe pipe;std::string last;
        TestSenderGate gate(pipe.reader(),[&](bool,const char* reason,std::uint64_t){last=reason;});
        pipe.command('P');EXPECT_TRUE(gate.paused(100));
        if(invalid)pipe.command('!');else pipe.eof();
        EXPECT_FALSE(gate.paused(101));EXPECT_EQ(last,invalid?"invalid-command":"controller-eof");
        EXPECT_FALSE(gate.paused(102));
    }
}

TEST(TestSenderGate, RejectsWriterBlockingPipeAndNonPipe) {
    SenderControlPipe pipe;
    const auto report=[](bool,const char*,std::uint64_t){};
    EXPECT_THROW(TestSenderGate(pipe.fd[1],report),std::invalid_argument);
    ASSERT_EQ(::fcntl(pipe.fd[0],F_SETFL,0),0);
    EXPECT_THROW(TestSenderGate(pipe.fd[0],report),std::invalid_argument);
    EXPECT_THROW(TestSenderGate(STDIN_FILENO,report),std::invalid_argument);
}
#endif

#include "bms_middleware.h"
#include "failsafe_sm.h"
#include "mock_can_driver.h"
#include "can_session_config.h"

#include <thread>
#include <vector>
#include <filesystem>
#include <fstream>
#include <chrono>


TEST(CanPublisher, EncodesBmsStatusPerIcd) {
    const auto frame = encodeBmsStatusFrame({75.0f, 95.0f, 42.0f, -2.0f, 25});

    EXPECT_EQ(frame.id, 0x100U);
    EXPECT_EQ(frame.dlc, 8);
    EXPECT_EQ(frame.data[0], 0x96);
    EXPECT_EQ(frame.data[1], 0xBE);
    EXPECT_EQ(frame.data[2], 0x10);
    EXPECT_EQ(frame.data[3], 0x68);
    EXPECT_EQ(frame.data[4], 0xFF);
    EXPECT_EQ(frame.data[5], 0xEC);
    EXPECT_EQ(frame.data[6], 0x41);
    EXPECT_EQ(frame.data[7], 0x00);
}

TEST(CanPublisher, EncodesFailSafeEventPerIcd) {
    const auto frame = encodeFailSafeFrame({0, 1, 0x01, 19.0f, 30});

    EXPECT_EQ(frame.id, 0x101U);
    EXPECT_EQ(frame.dlc, 8);
    EXPECT_EQ(frame.data[0], 0x00);
    EXPECT_EQ(frame.data[1], 0x01);
    EXPECT_EQ(frame.data[2], 0x01);
    EXPECT_EQ(frame.data[3], 0x26);
    EXPECT_EQ(frame.data[4], 0x46);
    EXPECT_EQ(frame.data[5], 0x00);
    EXPECT_EQ(frame.data[6], 0x00);
    EXPECT_EQ(frame.data[7], 0x00);
}


namespace {
constexpr std::array<uint8_t, 32> kDummyKey{1};

class FailingDriver : public MockCanDriver {
public:
    int calls = 0;
    int fail_on = 0;
    bool send(const CanFrame& frame) override {
        ++calls;
        return calls != fail_on && MockCanDriver::send(frame);
    }
};
}

TEST(BmsMiddleware, ProductRoutePublishesStatusAndTransitionsToCanAndOtherSubscribers) {
    MockCanDriver driver;
    ASSERT_TRUE(driver.open("mock"));
    SecOcModule sender, verifier;
    sender.setKey(kDummyKey);
    verifier.setKey(kDummyKey);
    BmsMiddleware middleware(driver, sender, true);
    int status_received = 0, event_received = 0;
    middleware.subscribeBms(Subscriber<BmsStatusData>([&](const BmsStatusData& data) {
        ++status_received;
        EXPECT_FLOAT_EQ(data.soh_percent, 90.0f);
    }));
    middleware.subscribeFailSafe(Subscriber<FailSafeEvent>([&](const FailSafeEvent& event) {
        ++event_received;
        EXPECT_EQ(event.new_state, 1U);
    }));
    FailSafeStateMachine fsm;
    fsm.setEventCallback([&](const FailSafeEvent& event) { middleware.publishFailSafe(event); });
    EXPECT_TRUE(fsm.evaluate(19.0f, 25));
    EXPECT_FALSE(fsm.evaluate(19.0f, 25)); // no duplicate transition publication
    middleware.publishBms({19.0f, 90.0f, 36.0f, -2.0f, 25});
    auto frames = driver.sentFrames();
    ASSERT_EQ(frames.size(), 4U);
    EXPECT_EQ(frames[0].id, 0x101U);
    EXPECT_EQ(frames[1].id, 0x103U);
    EXPECT_EQ(frames[2].id, 0x100U);
    EXPECT_EQ(frames[3].id, 0x102U);
    EXPECT_EQ(frames[2].data, encodeBmsStatusFrame({19, 90, 36, -2, 25}).data);
    EXPECT_TRUE(verifier.verify(0x101, frames[0].data, frames[1]));
    EXPECT_TRUE(verifier.verify(0x100, frames[2].data, frames[3]));
    EXPECT_EQ(status_received, 1);
    EXPECT_EQ(event_received, 1);
    EXPECT_EQ(sender.nextCounter(0x102), 1U);
    EXPECT_EQ(sender.nextCounter(0x103), 1U);
}

TEST(BmsMiddleware, TcBms005CriticalAndTcBms006ShutdownPublishAuthenticatedTransitions) {
    for(bool critical:{true,false}){
        SCOPED_TRACE(critical?"TC-BMS-005":"TC-BMS-006");
        MockCanDriver driver;ASSERT_TRUE(driver.open("mock"));
        SecOcModule sender,verifier;sender.setKey(kDummyKey);verifier.setKey(kDummyKey);
        BmsMiddleware middleware(driver,sender,true);
        FailSafeStateMachine fsm;
        fsm.setEventCallback([&](const FailSafeEvent& event){middleware.publishFailSafe(event);});
        // ICD permits SHUTDOWN from WARNING/CRITICAL, not NORMAL directly.
        ASSERT_TRUE(fsm.evaluate(critical?19.0f:50.0f,critical?25:56));
        const auto previous_frames=driver.sentFrames().size();
        ASSERT_TRUE(fsm.evaluate(critical?4.5f:50.0f,critical?25:61));
        const auto frames=driver.sentFrames();ASSERT_EQ(frames.size(),previous_frames+2);
        const auto& raw=frames[previous_frames];const auto& auth=frames[previous_frames+1];
        EXPECT_EQ(raw.id,0x101U);EXPECT_EQ(auth.id,0x103U);
        EXPECT_EQ(raw.dlc,8U);EXPECT_EQ(auth.dlc,8U);
        EXPECT_EQ(raw.data[0],1);EXPECT_EQ(raw.data[1],critical?2:3);
        EXPECT_EQ(raw.data[2],critical?2:4);EXPECT_EQ(raw.data[3],critical?9:100);
        EXPECT_EQ(raw.data[4],critical?65:101);
        for(std::size_t i=0;i<frames.size();i+=2)
            EXPECT_TRUE(verifier.verify(0x101,frames[i].data,frames[i+1]));
        EXPECT_FALSE(fsm.evaluate(critical?4.5f:50.0f,critical?25:61));
        EXPECT_EQ(driver.sentFrames().size(),frames.size());
    }
}

TEST(BmsMiddleware, ExplicitUnprotectedModeDoesNotSignOrSendAuth) {
    MockCanDriver driver;
    ASSERT_TRUE(driver.open("mock"));
    SecOcModule no_key;
    BmsMiddleware middleware(driver, no_key, false);
    middleware.publishBms({});
    middleware.publishFailSafe({0, 1, 1, 19, 25});
    auto frames = driver.sentFrames();
    ASSERT_EQ(frames.size(), 2U);
    EXPECT_EQ(frames[0].id, 0x100U);
    EXPECT_EQ(frames[1].id, 0x101U);
    EXPECT_EQ(no_key.nextCounter(0x102), 0U);
}

TEST(BmsMiddleware, OriginalFailureReportsAndDoesNotSignOrSendOrphanAuth) {
    FailingDriver driver;
    ASSERT_TRUE(driver.open("mock"));
    driver.fail_on = 1;
    SecOcModule secoc;
    secoc.setKey(kDummyKey);
    std::vector<CanPublishResult> results;
    BmsMiddleware middleware(driver, secoc, true, [&](uint32_t id, CanPublishResult r) {
        EXPECT_EQ(id, 0x100U);
        results.push_back(r);
    });
    middleware.publishBms({});
    EXPECT_EQ(driver.calls, 1);
    EXPECT_TRUE(driver.sentFrames().empty());
    EXPECT_EQ(secoc.nextCounter(0x102), 0U);
    ASSERT_EQ(results.size(), 1U);
    EXPECT_EQ(results[0], CanPublishResult::OriginalSendFailed);
    middleware.publishBms({});
    EXPECT_EQ(results.back(), CanPublishResult::Sent);
    EXPECT_EQ(driver.sentFrames().size(), 2U);
}

TEST(BmsMiddleware, AuthenticationFailureConsumesCounterWithoutSilentRetry) {
    FailingDriver driver;
    ASSERT_TRUE(driver.open("mock"));
    driver.fail_on = 2;
    SecOcModule secoc;
    secoc.setKey(kDummyKey);
    CanPublishResult result = CanPublishResult::Sent;
    BmsMiddleware middleware(driver, secoc, true, [&](uint32_t id, CanPublishResult r) {
        EXPECT_EQ(id, 0x101U); result = r;
    });
    middleware.publishFailSafe({0, 1, 1, 19, 25});
    EXPECT_EQ(result, CanPublishResult::AuthenticationSendFailed);
    EXPECT_EQ(driver.calls, 2);
    EXPECT_EQ(driver.sentFrames().size(), 1U);
    EXPECT_EQ(secoc.nextCounter(0x103), 1U);
    middleware.publishFailSafe({1, 0, 5, 30, 25});
    EXPECT_EQ(result, CanPublishResult::Sent);
    EXPECT_EQ(secoc.nextCounter(0x103), 2U);
}

TEST(BmsMiddleware, ConcurrentPublishersKeepPairsAndStreamCountersSerialized) {
    MockCanDriver driver;
    ASSERT_TRUE(driver.open("mock"));
    SecOcModule secoc, verifier;
    secoc.setKey(kDummyKey); verifier.setKey(kDummyKey);
    BmsMiddleware middleware(driver, secoc, true);
    std::thread statuses([&] { for (int i=0; i<100; ++i) middleware.publishBms({}); });
    std::thread events([&] { for (int i=0; i<100; ++i) middleware.publishFailSafe({0,1,1,19,25}); });
    statuses.join(); events.join();
    const auto frames = driver.sentFrames();
    ASSERT_EQ(frames.size(), 400U);
    for (std::size_t i=0; i<frames.size(); i+=2) {
        EXPECT_EQ(frames[i+1].id, frames[i].id+2);
        EXPECT_TRUE(verifier.verify(frames[i].id, frames[i].data, frames[i+1]));
    }
    EXPECT_EQ(secoc.nextCounter(0x102), 100U);
    EXPECT_EQ(secoc.nextCounter(0x103), 100U);
}

TEST(BmsMiddleware, SessionGateUsesTypedPublicationWithoutLegacyBypass) {
    std::vector<CanFrame> attempts;
    std::vector<CanPublishResult> deliveries;
    bool opened=false;
    BmsMiddleware middleware([&](const CanFrame& original){
        attempts.push_back(original);
        return opened ? CanPublishResult::Sent : CanPublishResult::AwaitingSession;
    },[&](std::uint32_t,CanPublishResult result){deliveries.push_back(result);});
    unsigned independent_subscriber=0;
    middleware.subscribeBms(Subscriber<BmsStatusData>([&](const auto&){++independent_subscriber;}));
    middleware.publishBms({75,90,42,-2,25});
    ASSERT_EQ(attempts.size(),1u);ASSERT_EQ(deliveries.size(),1u);
    EXPECT_EQ(deliveries[0],CanPublishResult::AwaitingSession);
    EXPECT_EQ(attempts[0].id,0x100u);EXPECT_EQ(attempts[0].data[1],180);
    EXPECT_EQ(independent_subscriber,1u);
    opened=true;
    middleware.publishFailSafe({1,3,4,75,61});
    ASSERT_EQ(attempts.size(),2u);EXPECT_EQ(attempts[1].id,0x101u);
    EXPECT_EQ(attempts[1].data[2],4);EXPECT_EQ(deliveries[1],CanPublishResult::Sent);
    EXPECT_THROW(CanPublisher(CanPublisher::AuthenticatedSender{}),std::invalid_argument);
}

TEST(SessionPolicy, CompleteExplicitValuesAndRejectAmbiguousOrUnboundedPolicy) {
    namespace session=capstone::session_v2;
    const std::string source=std::string(ECU_SOURCE_DIR)+"/data/session-v2-development.conf";
    const auto policy=session::loadExchangeLimits(source);
    EXPECT_EQ(policy.receive.order_ms,5u);EXPECT_EQ(policy.max_batches,64u);
    EXPECT_EQ(policy.diagnostic.assemblies,4u);
    std::ifstream input(source);const std::string valid((std::istreambuf_iterator<char>(input)),{});
    const auto path=std::filesystem::temp_directory_path()/
        ("capstone-policy-test-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
    struct Cleanup {std::filesystem::path p;~Cleanup(){std::error_code error;std::filesystem::remove(p,error);}} cleanup{path};
    auto check=[&](const std::string& text){std::ofstream(path)<<text;
        EXPECT_THROW(session::loadExchangeLimits(path.string()),std::invalid_argument);};
    check(valid+"\nretry_ms=10\n");check(valid+"\nunknown=1\n");check("retry_ms=100\n");
    check(std::string(4097,'#'));check(valid+"\nunknown=-1\n");
    auto bound=valid;const auto at=bound.find("receive_candidates=8");ASSERT_NE(at,std::string::npos);
    bound.replace(at,std::string("receive_candidates=8").size(),"receive_candidates=17");check(bound);
    bound=valid;const auto phase=bound.find("phase_ms=1000");ASSERT_NE(phase,std::string::npos);
    bound.replace(phase,std::string("phase_ms=1000").size(),"phase_ms=1");check(bound);
}
