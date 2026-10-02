#pragma once

#include "ads1115_registers.h"

#include <cstdint>
#include <string>

// Linux i2c-dev transport for the ADS1115 at a fixed 7-bit address.
// On non-Linux hosts the device never opens and every transfer fails.
class LinuxI2cTransport final : public Ads1115Transport {
public:
    static constexpr std::uint8_t kAds1115Address = 0x48;

    explicit LinuxI2cTransport(const std::string& device,
                               std::uint8_t address = kAds1115Address);
    ~LinuxI2cTransport() override;
    LinuxI2cTransport(const LinuxI2cTransport&) = delete;
    LinuxI2cTransport& operator=(const LinuxI2cTransport&) = delete;

    bool ready() const { return fd_ >= 0; }
    bool write(const std::uint8_t* data, std::size_t count) override;
    bool readRegister(std::uint8_t pointer, std::uint8_t* data, std::size_t count) override;

private:
    int fd_ = -1;
    std::uint8_t address_;
};
