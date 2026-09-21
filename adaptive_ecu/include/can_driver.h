#pragma once

#include <array>
#include <cstdint>
#include <functional>
#include <string>

struct CanFrame {
    uint32_t id = 0;
    uint8_t dlc = 0;
    std::array<uint8_t, 8> data{};
};

using CanCallback = std::function<void(const CanFrame&)>;

class CanDriver {
public:
    virtual ~CanDriver() = default;
    virtual bool open(const std::string& interface_name) = 0;
    virtual void close() = 0;
    virtual bool send(const CanFrame& frame) = 0;
    virtual void registerCallback(CanCallback callback) = 0;
    virtual void startReceive() = 0;
    virtual void stopReceive() = 0;
};
