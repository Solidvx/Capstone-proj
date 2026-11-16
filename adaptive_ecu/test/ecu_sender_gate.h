#pragma once
// Test executable only. Never include this in the installed ECU target.
#include <cerrno>
#include <cstdint>
#include <functional>
#include <utility>
#include <stdexcept>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

class TestSenderGate {
public:
    using Report=std::function<void(bool,const char*,std::uint64_t)>;
    TestSenderGate(int fd,Report report):fd_(fd),report_(std::move(report)){
        struct stat info{};const int flags=::fcntl(fd,F_GETFL);
        if(fd<3 || flags<0 || ::fstat(fd,&info)!=0 || !S_ISFIFO(info.st_mode) ||
           !(flags&O_NONBLOCK) || (flags&O_ACCMODE)!=O_RDONLY)
            throw std::invalid_argument("test sender gate requires nonblocking inherited read pipe");
    }
    ~TestSenderGate(){if(fd_>=0)::close(fd_);}
    TestSenderGate(const TestSenderGate&)=delete;
    TestSenderGate& operator=(const TestSenderGate&)=delete;
    bool paused(std::uint64_t now){
        if(paused_ && now>=deadline_){release("deadline",now);close();}
        if(fd_<0)return false;
        char commands[32];const auto n=::read(fd_,commands,sizeof commands);
        if(n==0){release("controller-eof",now);close();}
        else if(n<0){
            if(errno!=EAGAIN && errno!=EWOULDBLOCK){release("control-error",now);close();}
        }else for(ssize_t i=0;i<n;++i){
            if(commands[i]=='P'){
                if(!paused_){paused_=true;deadline_=now+2000;report_(true,"pause",now);}
            }else if(commands[i]=='R')release("resume",now);
            else{release("invalid-command",now);close();break;}
        }
        return paused_;
    }
private:
    void release(const char* reason,std::uint64_t now){
        if(paused_){paused_=false;report_(false,reason,now);}
    }
    void close(){::close(fd_);fd_=-1;}
    int fd_;
    Report report_;
    bool paused_=false;
    std::uint64_t deadline_=0; // Fixed 2s test guard, never an operating policy.
};
