#pragma once
#include "can_diagnostic.h"
#include <array>
#include <algorithm>
#include <limits>
#include <stdexcept>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

namespace capstone::session_v2 {
// Private inherited pipe protocol; not a CAN envelope or an authentication key.
inline std::array<std::uint8_t,144> peerRejectionPacket(const DiagnosticMessage& message,
    std::uint64_t generation,std::uint64_t published_ns,std::uint64_t dropped) {
    constexpr auto max_ms=std::numeric_limits<std::uint64_t>::max()/1000000;
    if(!generation || !published_ns || message.duplicate || message.sender_id!=0x303 ||
       message.kind!=DiagnosticKind::Rejection || !validDiagnosticBody(0x303,message.kind,message.body) ||
       message.received_ms>message.verified_ms || message.verified_ms>max_ms ||
       message.verified_ms*1000000>published_ns)
        throw std::invalid_argument("invalid authenticated peer rejection forwarding");
    std::array<std::uint8_t,144> packet{};
    std::copy_n("CPR1",4,packet.begin());
    const auto put=[&](unsigned at,std::uint64_t value,unsigned width){
        for(unsigned i=0;i<width;++i)packet[at+i]=static_cast<std::uint8_t>(value>>(8*(width-1-i)));
    };
    put(4,generation,8);put(12,published_ns,8);put(20,message.received_ms*1000000,8);
    put(28,message.verified_ms*1000000,8);put(36,message.sequence,4);
    std::copy(message.session_id.begin(),message.session_id.end(),packet.begin()+40);
    put(56,dropped,8);std::copy(message.body.begin(),message.body.end(),packet.begin()+64);
    return packet;
}

class PeerDiagnosticWriter {
public:
    explicit PeerDiagnosticWriter(int fd):fd_(fd){
        struct stat info{};const int flags=::fcntl(fd,F_GETFL);
        if(fd<3 || flags<0 || ::fstat(fd,&info)!=0 || !S_ISFIFO(info.st_mode) ||
           !(flags&O_NONBLOCK) || (flags&O_ACCMODE)!=O_WRONLY)
            throw std::invalid_argument("peer diagnostics require inherited nonblocking write pipe");
    }
    ~PeerDiagnosticWriter(){if(fd_>=0)::close(fd_);}
    PeerDiagnosticWriter(const PeerDiagnosticWriter&)=delete;
    PeerDiagnosticWriter& operator=(const PeerDiagnosticWriter&)=delete;
    bool forward(const DiagnosticMessage& message,std::uint64_t generation,std::uint64_t published_ns){
        if(fd_<0)return false;
        std::array<std::uint8_t,144> packet{};
        try{packet=peerRejectionPacket(message,generation,published_ns,dropped_);}
        catch(const std::exception&){drop();return false;}
        // 144B <= POSIX PIPE_BUF. Nonblocking write is atomic or fails; no retry.
        if(::write(fd_,packet.data(),packet.size())==static_cast<ssize_t>(packet.size()))return true;
        drop();
        return false;
    }
    std::uint64_t dropped()const{return dropped_;}
private:
    void drop(){
        if(dropped_==std::numeric_limits<std::uint64_t>::max()){::close(fd_);fd_=-1;}
        else ++dropped_;
    }
    int fd_;
    std::uint64_t dropped_=0;
};
}
