#pragma once
#ifdef __linux__
#include <sys/syscall.h>
#include <unistd.h>
#include <poll.h>
#include <stdexcept>

namespace capstone::session_v2 {
// pidfd pins the process lifetime: a recycled numeric PID is not a new owner.
class IdsProcessLifetime {
public:
    explicit IdsProcessLifetime(pid_t pid){
        if(pid<=0)throw std::invalid_argument("positive IDS PID required");
#ifdef SYS_pidfd_open
        fd_=static_cast<int>(syscall(SYS_pidfd_open,pid,0));
#else
        fd_=-1;
#endif
        if(fd_<0)throw std::runtime_error("IDS process lifetime unavailable");
    }
    ~IdsProcessLifetime(){if(fd_>=0)close(fd_);}
    IdsProcessLifetime(const IdsProcessLifetime&)=delete;
    IdsProcessLifetime& operator=(const IdsProcessLifetime&)=delete;
    bool alive()const{
        pollfd item{fd_,POLLIN,0};
        return poll(&item,1,0)==0;
    }
private:int fd_=-1;
};
}
#endif
