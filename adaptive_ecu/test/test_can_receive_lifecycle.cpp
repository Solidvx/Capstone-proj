#include "can_cdd.h"
#include "can_receive_recovery.h"
#include <gtest/gtest.h>
#include <chrono>
#include <cstdlib>
#include <stdexcept>
#include <thread>
#include <atomic>
#include "bms_middleware.h"
#include "secoc_module.h"
#ifdef __linux__
#include <sys/socket.h>
#include <fcntl.h>
#include <unistd.h>
#include <cerrno>
#include <mutex>
#include <vector>
#include <iostream>

namespace {
std::atomic<bool> trace_faults{false};
std::atomic<unsigned> trace_send_calls{0};
std::atomic<int> trace_send_flags{0};
}
extern "C" ssize_t __real_send(int,const void*,size_t,int);
extern "C" ssize_t __wrap_send(int fd,const void* bytes,size_t length,int flags){
    if(trace_faults){
        const auto call=++trace_send_calls;trace_send_flags=flags;
        if(call==1 || call==3){errno=ENOBUFS;return -1;}
    }
    return __real_send(fd,bytes,length,flags);
}
#endif

namespace {
template<class Predicate> bool waitFor(Predicate predicate) {
    const auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(2);
    while(std::chrono::steady_clock::now()<deadline){
        if(predicate())return true;
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
    }
    return predicate();
}

TEST(CanReceiveLifecycle, OwnerRecoveryRequiresFrameAndPreservesQuietBus) {
#ifndef __linux__
    GTEST_SKIP()<<"Linux SocketCAN required";
#else
    const char* name=std::getenv("CAPSTONE_SESSION_TEST_INTERFACE");
    if(!name || std::string(name).rfind("vcan",0)!=0)GTEST_SKIP()<<"explicit vcan required";
    SocketCanCdd receiver,sender;
    ASSERT_TRUE(receiver.open(name));ASSERT_TRUE(sender.open(name));
    std::atomic<bool> fail{true};
    receiver.registerCallback([&](const CanFrame&){if(fail)throw std::runtime_error("test fault");});
    receiver.startReceive();
    CanReceiveRecovery recovery(receiver,0);
    ASSERT_TRUE(sender.send(CanFrame{0x123,8,{}}));
    ASSERT_TRUE(waitFor([&]{return receiver.receiveHealth().stopped;}));
    EXPECT_EQ(recovery.poll(1000),TaskRecovery::Event::Started);
    EXPECT_EQ(recovery.attempts(),1u);
    for(unsigned now=1100;now<=5100;now+=100){
        const auto before=receiver.receiveHealth().progress;
        ASSERT_TRUE(waitFor([&]{return receiver.receiveHealth().progress>before;}));
        EXPECT_EQ(recovery.poll(now),TaskRecovery::Event::None);
    }
    EXPECT_EQ(recovery.state(),TaskRecovery::State::AwaitingHeartbeat);
    EXPECT_EQ(recovery.failures(),0u);
    fail=false;
    ASSERT_TRUE(sender.send(CanFrame{0x124,8,{}}));
    ASSERT_TRUE(waitFor([&]{return receiver.receiveHealth().frames>0;}));
    EXPECT_EQ(recovery.poll(5200),TaskRecovery::Event::Recovered);
    EXPECT_EQ(recovery.state(),TaskRecovery::State::Idle);
    fail=true;
    ASSERT_TRUE(sender.send(CanFrame{0x125,8,{}}));
    ASSERT_TRUE(waitFor([&]{return receiver.receiveHealth().stopped;}));
    EXPECT_EQ(recovery.poll(6200),TaskRecovery::Event::Started);
    unsigned now=6200;
    for(unsigned attempt=1;attempt<=3;++attempt){
        ASSERT_TRUE(sender.send(CanFrame{0x126,8,{}}));
        ASSERT_TRUE(waitFor([&]{return receiver.receiveHealth().stopped;}));
        now+=3001;
        EXPECT_EQ(recovery.poll(now),TaskRecovery::Event::AttemptFailed);
        EXPECT_EQ(recovery.poll(++now),attempt==3 ? TaskRecovery::Event::Exhausted : TaskRecovery::Event::Started);
    }
    EXPECT_EQ(recovery.attempts(),3u);
    EXPECT_EQ(recovery.failures(),3u);
    EXPECT_TRUE(receiver.reapReceiveIfStopped());
#endif
}
}

TEST(CanReceiveLifecycle, QuietBusFaultReapAndNewFrame) {
#ifndef __linux__
    GTEST_SKIP()<<"Linux SocketCAN required";
#else
    const char* name=std::getenv("CAPSTONE_SESSION_TEST_INTERFACE");
    if(!name || std::string(name).rfind("vcan",0)!=0)GTEST_SKIP()<<"explicit vcan required";
    SocketCanCdd receiver,sender;
    ASSERT_TRUE(receiver.open(name));ASSERT_TRUE(sender.open(name));
    receiver.registerCallback([](const CanFrame&){throw std::runtime_error("test callback fault");});
    receiver.startReceive();
    ASSERT_TRUE(waitFor([&]{return receiver.receiveHealth().progress>0;}));
    EXPECT_FALSE(receiver.receiveHealth().faulted);
    EXPECT_FALSE(receiver.receiveHealth().stopped);
    ASSERT_TRUE(sender.send(CanFrame{0x123,8,{}}));
    ASSERT_TRUE(waitFor([&]{return receiver.receiveHealth().stopped;}));
    EXPECT_TRUE(receiver.receiveHealth().faulted);
    EXPECT_EQ(receiver.receiveHealth().frames,0u);
    receiver.startReceive(); // Old thread has ended, but is not yet joined.
    EXPECT_TRUE(receiver.receiveHealth().stopped);
    ASSERT_TRUE(receiver.reapReceiveIfStopped());
    std::atomic<unsigned> received{0};
    receiver.registerCallback([&](const CanFrame&){++received;});
    receiver.startReceive();
    ASSERT_TRUE(sender.send(CanFrame{0x124,8,{}}));
    ASSERT_TRUE(waitFor([&]{return received.load()==1 && receiver.receiveHealth().frames>=1;}));
    EXPECT_FALSE(receiver.receiveHealth().faulted);
    EXPECT_GE(receiver.receiveHealth().frames,1u);
    receiver.requestReceiveStop();
    ASSERT_TRUE(waitFor([&]{return receiver.reapReceiveIfStopped();}));
    EXPECT_TRUE(receiver.receiveHealth().stopped);
#endif
}

TEST(CanTransmitTrace, RealDriverSyscallFailuresPreservePairAndCounterRules) {
#ifndef __linux__
    GTEST_SKIP()<<"Linux SocketCAN required";
#else
    const char* name=std::getenv("CAPSTONE_SESSION_TEST_INTERFACE");
    if(!name || std::string(name).rfind("vcan",0)!=0)GTEST_SKIP()<<"explicit vcan required";
    SocketCanCdd receiver;ASSERT_TRUE(receiver.open(name));
    std::mutex mutex;std::vector<CanFrame> observed;
    receiver.registerCallback([&](const CanFrame& frame){std::lock_guard<std::mutex> lock(mutex);observed.push_back(frame);});
    receiver.startReceive();
    int pipe[2];ASSERT_EQ(::pipe2(pipe,O_NONBLOCK|O_CLOEXEC),0);
    struct Cleanup {int reader,writer;~Cleanup(){::close(reader);if(writer>=0)::close(writer);trace_faults=false;}} cleanup{pipe[0],pipe[1]};
    std::string trace;
    {
        SocketCanCdd sender;ASSERT_TRUE(sender.open(name));
        std::array<std::uint8_t,16> instance{};instance[6]=0x40;instance[8]=0x80;
        sender.enableTxTrace(pipe[1],instance);
        cleanup.writer=-1;
        SecOcModule secoc,verifier;std::array<std::uint8_t,32> dummy{};
        for(unsigned i=0;i<dummy.size();++i)dummy[i]=i;
        secoc.setKey(dummy);verifier.setKey(dummy);
        CanPublishResult result=CanPublishResult::Sent;
        BmsMiddleware middleware(sender,secoc,true,[&](std::uint32_t,CanPublishResult value){result=value;});
        trace_send_calls=0;trace_faults=true;
        middleware.publishBms({75,100,42,-2,25});
        EXPECT_EQ(result,CanPublishResult::OriginalSendFailed);
        EXPECT_EQ(trace_send_calls,1u);EXPECT_EQ(secoc.nextCounter(0x102),0u);EXPECT_EQ(errno,ENOBUFS);
        middleware.publishBms({74,100,42,-2,25});
        EXPECT_EQ(result,CanPublishResult::AuthenticationSendFailed);
        EXPECT_EQ(trace_send_calls,3u);EXPECT_EQ(secoc.nextCounter(0x102),1u);EXPECT_EQ(errno,ENOBUFS);
        middleware.publishBms({73,100,42,-2,25});
        EXPECT_EQ(result,CanPublishResult::Sent);
        EXPECT_EQ(trace_send_calls,5u);EXPECT_EQ(secoc.nextCounter(0x102),2u);
        EXPECT_EQ(trace_send_flags.load()&(MSG_DONTWAIT|MSG_NOSIGNAL),MSG_DONTWAIT|MSG_NOSIGNAL);
        trace_faults=false;
        ASSERT_TRUE(waitFor([&]{return receiver.receiveHealth().frames>=3;}));
        receiver.stopReceive();
        std::lock_guard<std::mutex> lock(mutex);ASSERT_EQ(observed.size(),3u);
        EXPECT_EQ(observed[0].id,0x100u);EXPECT_EQ(observed[1].id,0x100u);EXPECT_EQ(observed[2].id,0x102u);
        EXPECT_NE(observed[0].data,observed[1].data);
        EXPECT_TRUE(verifier.verify(0x100,observed[1].data,observed[2]));
    }
    char bytes[4096];
    for(;;){const auto size=::read(pipe[0],bytes,sizeof bytes);if(size<=0)break;trace.append(bytes,static_cast<std::size_t>(size));}
    std::size_t rows=0,at=0;while((at=trace.find("\"result\":\"ECU_CAN_TX\"",at))!=std::string::npos){++rows;++at;}
    EXPECT_EQ(rows,5u);
    EXPECT_NE(trace.find("\"attempts\":5"),std::string::npos);
    EXPECT_NE(trace.find("\"records_dropped\":0"),std::string::npos);
    EXPECT_NE(trace.find("\"counter\":0,\"syscall_attempted\":true,\"returned_bytes\":-1"),std::string::npos);
    EXPECT_NE(trace.find("\"counter\":1,\"syscall_attempted\":true,\"returned_bytes\":16"),std::string::npos);
    std::cout<<"TX_TRACE_SYSCALL_FIXTURE attempts=5 synthetic_enobufs=2 received=3 next_counter=2 normal_auth=1 no_retry=1\n";
#endif
}

TEST(CanTransmitTrace, DelayedConsumerIsSeparateFromSendAcceptanceAndIndependentArrival) {
#ifndef __linux__
    GTEST_SKIP()<<"Linux SocketCAN required";
#else
    const char* name=std::getenv("CAPSTONE_SESSION_TEST_INTERFACE");
    if(!name || std::string(name).rfind("vcan",0)!=0)GTEST_SKIP()<<"explicit vcan required";
    SocketCanCdd delayed,witness;
    std::atomic<bool> release{false},entered{false};
    std::atomic<unsigned> consumed{0},arrived{0};
    ASSERT_TRUE(delayed.open(name));ASSERT_TRUE(witness.open(name));
    delayed.registerCallback([&](const CanFrame&){
        entered=true;
        while(!release)std::this_thread::sleep_for(std::chrono::milliseconds(1));
        ++consumed;
    });
    std::mutex mutex;std::vector<CanFrame> observed;
    witness.registerCallback([&](const CanFrame& frame){
        std::lock_guard<std::mutex> lock(mutex);observed.push_back(frame);++arrived;
    });
    // Release/join before destroying callback captures, also on ASSERT failure.
    struct Release {
        std::atomic<bool>& flag;SocketCanCdd& delayed;SocketCanCdd& witness;
        ~Release(){flag=true;delayed.stopReceive();witness.stopReceive();}
    } guard{release,delayed,witness};
    delayed.startReceive();witness.startReceive();
    int pipe[2];ASSERT_EQ(::pipe2(pipe,O_NONBLOCK|O_CLOEXEC),0);
    struct Pipe {int reader,writer;~Pipe(){::close(reader);if(writer>=0)::close(writer);}} cleanup{pipe[0],pipe[1]};
    {
        SocketCanCdd sender;ASSERT_TRUE(sender.open(name));
        std::array<std::uint8_t,16> instance{};instance[6]=0x40;instance[8]=0x80;
        sender.enableTxTrace(pipe[1],instance);cleanup.writer=-1;
        SecOcModule secoc,verifier;std::array<std::uint8_t,32> dummy{};
        for(unsigned i=0;i<dummy.size();++i)dummy[i]=i;
        secoc.setKey(dummy);verifier.setKey(dummy);
        CanPublishResult result=CanPublishResult::OriginalSendFailed;
        BmsMiddleware middleware(sender,secoc,true,[&](std::uint32_t,CanPublishResult value){result=value;});
        middleware.publishBms({75,100,42,-2,25});
        ASSERT_EQ(result,CanPublishResult::Sent);
        ASSERT_TRUE(waitFor([&]{return entered.load() && arrived.load()==2;}));
        EXPECT_EQ(consumed,0u);
        EXPECT_EQ(delayed.receiveHealth().frames,0u); // Callback has not completed.
        EXPECT_FALSE(delayed.receiveHealth().faulted);
        EXPECT_EQ(secoc.nextCounter(0x102),1u);
        {
            std::lock_guard<std::mutex> lock(mutex);ASSERT_EQ(observed.size(),2u);
            EXPECT_EQ(observed[0].id,0x100u);EXPECT_EQ(observed[1].id,0x102u);
            EXPECT_TRUE(verifier.verify(0x100,observed[0].data,observed[1]));
        }
        release=true;
        ASSERT_TRUE(waitFor([&]{return consumed.load()==2 && delayed.receiveHealth().frames==2;}));
        delayed.stopReceive();witness.stopReceive();
    }
    char bytes[4096];std::string trace;
    for(;;){const auto size=::read(pipe[0],bytes,sizeof bytes);if(size<=0)break;trace.append(bytes,static_cast<std::size_t>(size));}
    const std::string accepted="\"returned_bytes\":16,\"error_number\":0,\"kernel_accepted\":true";
    std::size_t count=0,at=0;while((at=trace.find(accepted,at))!=std::string::npos){++count;++at;}
    EXPECT_EQ(count,2u);EXPECT_NE(trace.find("\"attempts\":2,\"records_written\":2,\"records_dropped\":0"),std::string::npos);
    std::cout<<"TX_TRACE_RECEIVE_DELAY_FIXTURE accepted=2 independent_received=2 blocked_consumed=0 resumed_consumed=2 valid_auth=1\n";
#endif
}
