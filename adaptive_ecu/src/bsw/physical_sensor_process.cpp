#include "physical_sensor_runtime.h"

#include <algorithm>
#include <chrono>
#include <stdexcept>
#include <thread>
#if defined(__linux__)
#include <cerrno>
#include <csignal>
#include <fcntl.h>
#include <spawn.h>
#include <sys/wait.h>
#include <unistd.h>
extern char** environ;
#endif

PhysicalSensorProcess::PhysicalSensorProcess(const std::string& executable,const std::string& config,
    std::array<std::uint8_t,32> fingerprint):fingerprint_(fingerprint){
#if defined(__linux__)
    if(executable.empty()||executable.front()!='/'||config.empty()||config.front()!='/')
        throw std::invalid_argument("physical reader requires absolute executable/config paths");
    int pipes[2];
    if(::pipe2(pipes,O_NONBLOCK|O_CLOEXEC))throw std::runtime_error("physical reader pipe failed");
    posix_spawn_file_actions_t actions;posix_spawnattr_t attr;
    if(posix_spawn_file_actions_init(&actions)){
        ::close(pipes[0]);::close(pipes[1]);throw std::runtime_error("physical reader spawn actions failed");
    }
    if(posix_spawnattr_init(&attr)){
        posix_spawn_file_actions_destroy(&actions);::close(pipes[0]);::close(pipes[1]);
        throw std::runtime_error("physical reader spawn attributes failed");
    }
    sigset_t mask;::sigemptyset(&mask);
    int error=posix_spawn_file_actions_adddup2(&actions,pipes[1],STDOUT_FILENO);
    if(!error)error=posix_spawn_file_actions_addclose(&actions,pipes[0]);
    if(!error&&pipes[1]!=STDOUT_FILENO)error=posix_spawn_file_actions_addclose(&actions,pipes[1]);
    if(!error)error=posix_spawn_file_actions_addclosefrom_np(&actions,3);
    if(!error)error=posix_spawnattr_setpgroup(&attr,0);
    if(!error)error=posix_spawnattr_setsigmask(&attr,&mask);
    if(!error)error=posix_spawnattr_setflags(&attr,POSIX_SPAWN_SETPGROUP|POSIX_SPAWN_SETSIGMASK);
    const auto parent=std::to_string(::getpid());
    std::vector<std::string> args{executable,"--config",config,"--parent-pid",parent};
    std::vector<char*> argv;for(auto& text:args)argv.push_back(text.data());argv.push_back(nullptr);
    pid_t pid=-1;
    if(!error)error=::posix_spawn(&pid,executable.c_str(),&actions,&attr,argv.data(),environ);
    posix_spawn_file_actions_destroy(&actions);posix_spawnattr_destroy(&attr);::close(pipes[1]);
    if(error){::close(pipes[0]);throw std::runtime_error("physical reader spawn failed");}
    pid_=pid;fd_=pipes[0];
#else
    (void)executable;(void)config;
    throw std::runtime_error("physical acquisition process requires Linux");
#endif
}
PhysicalSensorProcess::~PhysicalSensorProcess(){stop();}
std::vector<PhysicalSensorSample> PhysicalSensorProcess::poll(){
    std::vector<PhysicalSensorSample> result;
#if defined(__linux__)
    if(failed_||fd_<0)return result;
    // A bounded amount per owner-loop turn; no blocking pipe reads or unbounded queue.
    std::array<std::uint8_t,84*8> bytes{};
    const auto count=::read(fd_,bytes.data(),bytes.size());
    if(count<0){if(errno!=EAGAIN&&errno!=EWOULDBLOCK&&errno!=EINTR)failed_=true;}
    else if(count==0){failed_=true;}
    else{
        pending_.insert(pending_.end(),bytes.begin(),bytes.begin()+count);
        while(pending_.size()>=84){
            PhysicalSensorPacket packet{};std::copy_n(pending_.begin(),84,packet.begin());
            pending_.erase(pending_.begin(),pending_.begin()+84);
            const auto sample=decodePhysicalSensorSample(packet);
            if(!sample||sample->fingerprint!=fingerprint_){failed_=true;result.clear();pending_.clear();break;}
            result.push_back(*sample);
        }
    }
    // Do not reap here: stop() first signals the still-owned process group so
    // an abruptly exited reader cannot leave its descendant running.
#endif
    return result;
}
bool PhysicalSensorProcess::stop(){
#if defined(__linux__)
    if(fd_>=0){::close(fd_);fd_=-1;}
    if(pid_<0)return true;
    const auto pid=pid_;
    auto reap=[&](unsigned milliseconds){
        const auto end=std::chrono::steady_clock::now()+std::chrono::milliseconds(milliseconds);
        do{
            int status=0;const auto reaped=::waitpid(pid,&status,WNOHANG);
            if(reaped==pid||(reaped<0&&errno==ECHILD)){pid_=-1;return true;}
            if(reaped<0&&errno!=EINTR)return false;
            std::this_thread::sleep_for(std::chrono::milliseconds(2));
        }while(std::chrono::steady_clock::now()<end);
        return false;
    };
    ::kill(-pid,SIGTERM);
    if(reap(200))return true;
    ::kill(-pid,SIGKILL);
    if(reap(200))return true;
    failed_=true;return false; // never start another reader over an unreclaimed process
#else
    return true;
#endif
}
