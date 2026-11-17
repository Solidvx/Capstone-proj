#include "bounded_sensor_read.h"

#include <array>
#include <chrono>
#include <stdexcept>
#include <thread>
#if defined(__linux__)
#include <cerrno>
#include <csignal>
#include <fcntl.h>
#include <poll.h>
#include <sys/prctl.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

BoundedSensorRead readSensorBounded(const std::function<std::string()>& read,
    unsigned timeout_ms,const std::function<bool()>& keep_running) {
    if(!read||!keep_running||timeout_ms<1||timeout_ms>10000)
        throw std::invalid_argument("explicit bounded sensor read required");
#if defined(__linux__)
    using Clock=std::chrono::steady_clock;using Status=BoundedSensorRead::Status;
    if(!keep_running())return {Status::Interrupted,{}};
    int pipe_fd[2];
    if(::pipe2(pipe_fd,O_CLOEXEC|O_NONBLOCK))return {Status::ChildError,{}};
    const auto parent=::getpid();
    const auto child=::fork();
    if(child<0){::close(pipe_fd[0]);::close(pipe_fd[1]);return {Status::ChildError,{}};}
    if(child==0){
        // Even an abrupt owner death must not leave a blocked device reader.
        if(::prctl(PR_SET_PDEATHSIG,SIGKILL) || ::getppid()!=parent)::_exit(2);
        ::close(pipe_fd[0]);
        try{
            const auto text=read();
            if(text.empty()||text.size()>4096)::_exit(2);
            ssize_t written;
            do{written=::write(pipe_fd[1],text.data(),text.size());}while(written<0&&errno==EINTR);
            ::_exit(written==static_cast<ssize_t>(text.size()) ? 0 : 2);
        }catch(...){::_exit(2);}
    }
    ::close(pipe_fd[1]);
    const auto deadline=Clock::now()+std::chrono::milliseconds(timeout_ms);
    std::string text;Status status=Status::Timeout;bool reaped=false;int code=0;
    while(Clock::now()<deadline){
        if(!keep_running()){status=Status::Interrupted;break;}
        pollfd descriptor{pipe_fd[0],POLLIN,0};
        const auto polled=::poll(&descriptor,1,10);
        if(polled<0 && errno!=EINTR){status=Status::ChildError;break;}
        std::array<char,4097> bytes{};const auto count=::read(pipe_fd[0],bytes.data(),bytes.size());
        if(count>0)text.append(bytes.data(),static_cast<std::size_t>(count));
        if(text.size()>4096){status=Status::ChildError;break;}
        const auto waited=::waitpid(child,&code,WNOHANG);
        if(waited==child){
            reaped=true;
            // Child exit may precede the parent's first pipe drain.
            const auto tail=::read(pipe_fd[0],bytes.data(),bytes.size());
            if(tail>0)text.append(bytes.data(),static_cast<std::size_t>(tail));
            status=WIFEXITED(code)&&WEXITSTATUS(code)==0&&!text.empty()&&text.size()<=4096
                ? Status::Complete : Status::ChildError;
            break;
        }
        if(waited<0){status=Status::ChildError;break;}
    }
    ::close(pipe_fd[0]);
    if(!reaped){
        ::kill(child,SIGKILL);
        const auto until=Clock::now()+std::chrono::milliseconds(100);
        do{
            const auto waited=::waitpid(child,&code,WNOHANG);
            if(waited==child){reaped=true;break;}
            if(waited<0&&errno==ECHILD){reaped=true;break;}
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }while(Clock::now()<until);
        if(!reaped)status=Status::Unreclaimed;
    }
    return {status,status==Status::Complete ? std::move(text) : std::string{}};
#else
    return {BoundedSensorRead::Status::ChildError,{}};
#endif
}
