// Link-only Linux syscall fixture. Never part of the installed capture tool.
#include <array>
#include <cstdarg>
#include <cstddef>
#include <cstdint>
#include <linux/i2c.h>
#include <linux/i2c-dev.h>
#include <sys/types.h>

namespace {
int device=-1;
std::array<std::uint16_t,6> words{{0,3700,static_cast<std::uint16_t>((925<<3)|2),0,3700,0}};
}
extern "C" ssize_t __real_write(int,const void*,std::size_t);
extern "C" int __wrap_ioctl(int fd,unsigned long request,...) {
    if(request==I2C_SLAVE)return fd==device ? 0 : -1;
    va_list args;va_start(args,request);auto* value=va_arg(args,void*);va_end(args);
    if(request==I2C_FUNCS){device=fd;*static_cast<unsigned long*>(value)=I2C_FUNC_I2C;return 0;}
    if(request!=I2C_RDWR||fd!=device)return -1;
    auto* transfer=static_cast<i2c_rdwr_ioctl_data*>(value);
    if(transfer->nmsgs!=2||transfer->msgs[0].len!=1||transfer->msgs[1].len!=2||
       !(transfer->msgs[1].flags&I2C_M_RD))return -1;
    const auto index=transfer->msgs[0].buf[0];if(index>=words.size())return -1;
    transfer->msgs[1].buf[0]=static_cast<std::uint8_t>(words[index]>>8);
    transfer->msgs[1].buf[1]=static_cast<std::uint8_t>(words[index]);return 2;
}
extern "C" ssize_t __wrap_write(int fd,const void* data,std::size_t size) {
    if(fd!=device)return __real_write(fd,data,size);
    const auto* bytes=static_cast<const std::uint8_t*>(data);
    if(size!=3||bytes[0]>=words.size())return -1;
    words[bytes[0]]=(std::uint16_t(bytes[1])<<8)|bytes[2];return 3;
}
