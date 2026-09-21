#pragma once

#include "can_driver.h"

#include <mutex>
#include <string>
#include <vector>

class MockCanDriver : public CanDriver {
public:
    bool open(const std::string& interface_name) override;
    void close() override;
    bool send(const CanFrame& frame) override;
    void registerCallback(CanCallback callback) override;
    void startReceive() override;
    void stopReceive() override;

    bool isOpened() const;
    bool isReceiving() const;
    std::string interfaceName() const;
    std::vector<CanFrame> sentFrames() const;
    void clear();

private:
    mutable std::mutex mutex_;
    std::string interface_name_;
    bool opened_ = false;
    bool receiving_ = false;
    CanCallback callback_;
    std::vector<CanFrame> sent_frames_;
};
