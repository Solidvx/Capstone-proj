#include "can_tx_trace.h"

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cstdio>
#include <fcntl.h>
#include <stdexcept>
#include <sys/stat.h>
#include <unistd.h>

namespace {
std::uint64_t monotonicNs() noexcept {
    return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}
constexpr char hex[]="0123456789abcdef";
}

CanTxTrace::CanTxTrace(int fd, const std::array<std::uint8_t,16>& instance):fd_(fd) {
    validateFd(fd);
    for(std::size_t i=0;i<instance.size();++i){
        instance_[i*2]=hex[instance[i]>>4];instance_[i*2+1]=hex[instance[i]&15];
    }
}

void CanTxTrace::validateFd(int fd){
    struct stat info{};
    const auto flags=::fcntl(fd,F_GETFL);
    if(fd<3 || flags<0 || !(flags&O_NONBLOCK) || (flags&O_ACCMODE)!=O_WRONLY ||
       ::fstat(fd,&info)!=0 || !S_ISFIFO(info.st_mode) || info.st_uid!=::geteuid() ||
       ::fpathconf(fd,_PC_PIPE_BUF)<512)
        throw std::invalid_argument("TX trace requires private owned nonblocking write pipe");
}

CanTxTrace::~CanTxTrace(){
    char record[512];
    const int length=std::snprintf(record,sizeof record,
        "{\"result\":\"ECU_CAN_TX_END\",\"schema\":\"ecu-can-tx-v1\",\"instance_id\":\"%s\","
        "\"attempts\":%llu,\"records_written\":%llu,\"records_dropped\":%llu,\"ended_ns\":%llu}\n",
        instance_.data(),static_cast<unsigned long long>(attempts_.load()),
        static_cast<unsigned long long>(written_.load()),static_cast<unsigned long long>(dropped_.load()),
        static_cast<unsigned long long>(monotonicNs()));
    emit(record,length);
    ::close(fd_);
}

CanTxTrace::Attempt CanTxTrace::begin() noexcept {
    const int saved_errno=errno;
    const Attempt value{attempts_.fetch_add(1)+1,monotonicNs()};
    errno=saved_errno;
    return value;
}

bool CanTxTrace::emit(const char* bytes,int length) noexcept {
    const int saved_errno=errno;
    // Format overflow and short pipe writes are missing evidence, never success.
    const bool success=length>0 && length<512 && ::write(fd_,bytes,static_cast<std::size_t>(length))==length;
    if(success)++written_;else ++dropped_;
    errno=saved_errno;
    return success;
}

void CanTxTrace::complete(Attempt attempt,const CanFrame& frame,bool syscall_attempted,
                         std::int64_t returned_bytes,int error_number,bool accepted) noexcept {
    const int saved_errno=errno;
    const auto ended=monotonicNs();
    char data[17]{};
    for(std::size_t i=0;i<std::min<std::size_t>(frame.dlc,frame.data.size());++i){
        data[i*2]=hex[frame.data[i]>>4];data[i*2+1]=hex[frame.data[i]&15];
    }
    char counter[16]="null";
    if(frame.dlc==8 && (frame.id==0x102 || frame.id==0x103 || frame.id==0x105)){
        const std::uint32_t value=(std::uint32_t(frame.data[4])<<24)|(std::uint32_t(frame.data[5])<<16)|
                                  (std::uint32_t(frame.data[6])<<8)|frame.data[7];
        std::snprintf(counter,sizeof counter,"%u",value);
    }
    char record[512];
    const int length=std::snprintf(record,sizeof record,
        "{\"result\":\"ECU_CAN_TX\",\"schema\":\"ecu-can-tx-v1\",\"instance_id\":\"%s\","
        "\"sequence\":%llu,\"started_ns\":%llu,\"ended_ns\":%llu,\"can_id\":%u,\"dlc\":%u,"
        "\"data\":\"%s\",\"counter\":%s,\"syscall_attempted\":%s,\"returned_bytes\":%lld,"
        "\"error_number\":%d,\"kernel_accepted\":%s,\"records_dropped\":%llu}\n",
        instance_.data(),static_cast<unsigned long long>(attempt.sequence),
        static_cast<unsigned long long>(attempt.started_ns),static_cast<unsigned long long>(ended),
        frame.id,static_cast<unsigned>(frame.dlc),data,counter,syscall_attempted?"true":"false",
        static_cast<long long>(returned_bytes),error_number,accepted?"true":"false",
        static_cast<unsigned long long>(dropped_.load()));
    emit(record,length);
    errno=saved_errno;
}
