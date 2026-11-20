#include "bounded_sensor_read.h"
#include <gtest/gtest.h>
#include <chrono>
#include <thread>
#include <stdexcept>
#include <cerrno>
#include <sys/wait.h>
#include <sys/prctl.h>
#include <unistd.h>
#include <csignal>

TEST(BoundedSensor, CompletedReplyAndChildAreReaped){
    const auto value=readSensorBounded([]{return std::string("{\"status\":\"OK\"}");},1000,[]{return true;});
    EXPECT_EQ(value.status,BoundedSensorRead::Status::Complete);EXPECT_EQ(value.text,"{\"status\":\"OK\"}");
    int code=0;EXPECT_EQ(::waitpid(-1,&code,WNOHANG),-1);EXPECT_EQ(errno,ECHILD);
}
TEST(BoundedSensor, HungReadTimesOutAndCannotLeaveAnExtraReader){
    const auto value=readSensorBounded([]{std::this_thread::sleep_for(std::chrono::seconds(2));return std::string("late");},30,[]{return true;});
    EXPECT_EQ(value.status,BoundedSensorRead::Status::Timeout);EXPECT_TRUE(value.text.empty());
    int code=0;EXPECT_EQ(::waitpid(-1,&code,WNOHANG),-1);EXPECT_EQ(errno,ECHILD);
}
TEST(BoundedSensor, EmptyOversizedOrThrowingReadIsNotAValue){
    for(const auto& text:{std::string{},std::string(4097,'x')}){
        const auto value=readSensorBounded([&]{return text;},1000,[]{return true;});
        EXPECT_EQ(value.status,BoundedSensorRead::Status::ChildError);EXPECT_TRUE(value.text.empty());
    }
    const auto value=readSensorBounded([]()->std::string{throw std::runtime_error("sensor failed");},1000,[]{return true;});
    EXPECT_EQ(value.status,BoundedSensorRead::Status::ChildError);
}
TEST(BoundedSensor, StopAndExplicitBudgetAreEnforced){
    auto read=[]{return std::string("unused");};
    EXPECT_EQ(readSensorBounded(read,30,[]{return false;}).status,BoundedSensorRead::Status::Interrupted);
    unsigned calls=0;
    EXPECT_EQ(readSensorBounded([]{std::this_thread::sleep_for(std::chrono::seconds(2));return std::string("late");},1000,
        [&]{return ++calls<3;}).status,BoundedSensorRead::Status::Interrupted);
    EXPECT_THROW(readSensorBounded(read,0,[]{return true;}),std::invalid_argument);
    EXPECT_THROW(readSensorBounded(read,10001,[]{return true;}),std::invalid_argument);
}
TEST(BoundedSensor, AbruptOwnerDeathKillsAndReapsBlockedDeviceReader){
    // Adopt the test grandchild so this negative case cannot leave a zombie.
    int previous=0;ASSERT_EQ(::prctl(PR_GET_CHILD_SUBREAPER,&previous),0);
    ASSERT_EQ(::prctl(PR_SET_CHILD_SUBREAPER,1),0);
    int descriptor[2];ASSERT_EQ(::pipe(descriptor),0);
    const auto owner=::fork();ASSERT_GE(owner,0);
    if(owner==0){
        ::close(descriptor[0]);
        readSensorBounded([&]{
            const auto reader=::getpid();
            if(::write(descriptor[1],&reader,sizeof(reader))!=sizeof(reader))::_exit(2);
            for(;;)::pause();
            return std::string{};
        },10000,[]{return true;});
        ::_exit(2);
    }
    ::close(descriptor[1]);pid_t reader=0;
    const auto count=::read(descriptor[0],&reader,sizeof(reader));::close(descriptor[0]);
    EXPECT_EQ(count,sizeof(reader));EXPECT_GT(reader,0);
    ::kill(owner,SIGKILL);int code=0;EXPECT_EQ(::waitpid(owner,&code,0),owner);
    if(reader>0){
        pid_t waited=0;
        for(int i=0;i<100 && waited==0;++i){waited=::waitpid(reader,&code,WNOHANG);if(!waited)std::this_thread::sleep_for(std::chrono::milliseconds(5));}
        if(!waited){::kill(reader,SIGKILL);::waitpid(reader,&code,0);}
        EXPECT_EQ(waited,reader);EXPECT_TRUE(WIFSIGNALED(code));EXPECT_EQ(WTERMSIG(code),SIGKILL);
    }
    EXPECT_EQ(::prctl(PR_SET_CHILD_SUBREAPER,previous),0);
}
