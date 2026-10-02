#include "linux_i2c_transport.h"

#if defined(__linux__)
#include <fcntl.h>
#include <linux/i2c-dev.h>
#include <linux/i2c.h>
#include <sys/ioctl.h>
#include <unistd.h>
#endif

LinuxI2cTransport::LinuxI2cTransport(const std::string& device, std::uint8_t address)
    : address_(address) {
#if defined(__linux__)
    fd_ = ::open(device.c_str(), O_RDWR | O_CLOEXEC);
    unsigned long functions = 0;
    if (fd_ >= 0 && (ioctl(fd_, I2C_FUNCS, &functions) < 0 ||
        !(functions & I2C_FUNC_I2C) || ioctl(fd_, I2C_SLAVE, address_) < 0)) {
        ::close(fd_);
        fd_ = -1;
    }
#else
    (void)device;
#endif
}

LinuxI2cTransport::~LinuxI2cTransport() {
#if defined(__linux__)
    if (fd_ >= 0) ::close(fd_);
#endif
}

bool LinuxI2cTransport::write(const std::uint8_t* data, std::size_t count) {
#if defined(__linux__)
    return fd_ >= 0 && ::write(fd_, data, count) == static_cast<ssize_t>(count);
#else
    (void)data;
    (void)count;
    return false;
#endif
}

bool LinuxI2cTransport::readRegister(std::uint8_t pointer, std::uint8_t* data,
                                     std::size_t count) {
#if defined(__linux__)
    if (fd_ < 0 || count != 2) return false;
    i2c_msg messages[2]{};
    messages[0].addr = address_;
    messages[0].len = 1;
    messages[0].buf = &pointer;
    messages[1].addr = address_;
    messages[1].flags = I2C_M_RD;
    messages[1].len = 2;
    messages[1].buf = data;
    i2c_rdwr_ioctl_data request{messages, 2};
    return ioctl(fd_, I2C_RDWR, &request) == 2;
#else
    (void)pointer;
    (void)data;
    (void)count;
    return false;
#endif
}
