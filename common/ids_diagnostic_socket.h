#pragma once
#ifdef __linux__
#include "ids_diagnostic_ipc.h"
#include "ids_process_lifetime.h"
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <unistd.h>
#include <cerrno>
#include <chrono>
#include <cstring>
#include <stdexcept>

namespace capstone::session_v2 {
// Caller creates a private, owned runtime directory. Never removes an existing
// socket: a stale path is an explicit startup error, not permission to unlink.
class IdsDiagnosticSocket {
public:
    IdsDiagnosticSocket(const std::string& path,uid_t allowed_uid,pid_t allowed_pid=0):path_(path),uid_(allowed_uid),pid_(allowed_pid){
        if(allowed_pid<0)throw std::invalid_argument("invalid IDS sender PID");
        sockaddr_un address{};address.sun_family=AF_UNIX;
        const auto slash=path.rfind('/');
        if(path.empty() || path[0]!='/' || slash==std::string::npos ||
           path.size()>=sizeof(address.sun_path) || path.find('\0')!=std::string::npos)
            throw std::invalid_argument("invalid IDS socket path");
        if(pid_>0)lifetime_=std::make_unique<IdsProcessLifetime>(pid_);
        struct stat parent{};
        if(lstat(path.substr(0,slash).c_str(),&parent)!=0 || !S_ISDIR(parent.st_mode) ||
           parent.st_uid!=geteuid() || (parent.st_mode&0077))
            throw std::invalid_argument("IDS socket requires owned private directory");
        std::memcpy(address.sun_path,path.c_str(),path.size()+1);
        fd_=socket(AF_UNIX,SOCK_DGRAM|SOCK_NONBLOCK|SOCK_CLOEXEC,0);
        if(fd_<0)throw std::runtime_error("IDS socket creation failed");
        int enabled=1;
        if(setsockopt(fd_,SOL_SOCKET,SO_PASSCRED,&enabled,sizeof(enabled))!=0 ||
           bind(fd_,reinterpret_cast<sockaddr*>(&address),sizeof(address))!=0){
            close(fd_);fd_=-1;throw std::runtime_error("IDS socket bind/credentials failed");
        }
        if(lstat(path.c_str(),&owned_)!=0){close(fd_);fd_=-1;throw std::runtime_error("IDS socket identity unavailable");}
    }
    ~IdsDiagnosticSocket(){
        if(fd_>=0)close(fd_);
        struct stat current{};
        if(lstat(path_.c_str(),&current)==0 && current.st_dev==owned_.st_dev && current.st_ino==owned_.st_ino)
            unlink(path_.c_str());
    }
    IdsDiagnosticSocket(const IdsDiagnosticSocket&)=delete;
    IdsDiagnosticSocket& operator=(const IdsDiagnosticSocket&)=delete;
    static std::uint64_t monotonicMs(){return static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
    std::optional<IdsDiagnosticSubmission> receive(std::optional<std::uint64_t> test_now_ms=std::nullopt){
        if(lifetime_ && !lifetime_->alive()){
            if(!owner_dead_){++rejected_;owner_dead_=true;}
            return std::nullopt;
        }
        std::array<std::uint8_t,119> data{};
        alignas(cmsghdr) char control[CMSG_SPACE(sizeof(ucred))]{};
        iovec vector{data.data(),data.size()};msghdr message{};
        message.msg_iov=&vector;message.msg_iovlen=1;
        message.msg_control=control;message.msg_controllen=sizeof(control);
        const auto size=recvmsg(fd_,&message,MSG_DONTWAIT);
        if(size<0){if(errno==EAGAIN || errno==EWOULDBLOCK || errno==EINTR)return std::nullopt;
            throw std::runtime_error("IDS socket receive failed");}
        if(message.msg_flags&(MSG_TRUNC|MSG_CTRUNC)){++rejected_;return std::nullopt;}
        unsigned credentials=0;bool authorized=false;
        for(auto* item=CMSG_FIRSTHDR(&message);item;item=CMSG_NXTHDR(&message,item)){
            if(item->cmsg_level==SOL_SOCKET && item->cmsg_type==SCM_CREDENTIALS && item->cmsg_len==CMSG_LEN(sizeof(ucred))){
                ucred peer{};std::memcpy(&peer,CMSG_DATA(item),sizeof(peer));
                ++credentials;authorized=peer.uid==uid_ && peer.pid>0 && (pid_==0 || peer.pid==pid_);
            }
        }
        if(credentials!=1 || !authorized){++rejected_;return std::nullopt;}
        auto parsed=parseIdsDiagnosticSubmission({data.begin(),data.begin()+size});
        const auto now_ms=test_now_ms.value_or(monotonicMs());
        if(!parsed || !parsed->observed_at_ms || now_ms<*parsed->observed_at_ms ||
           now_ms-*parsed->observed_at_ms>=3000){++rejected_;return std::nullopt;}
        return parsed;
    }
    std::uint64_t rejected()const{return rejected_;}
private:
    std::unique_ptr<IdsProcessLifetime> lifetime_;
    std::string path_;uid_t uid_;pid_t pid_;int fd_=-1;struct stat owned_{};std::uint64_t rejected_=0;bool owner_dead_=false;
};
}
#endif
