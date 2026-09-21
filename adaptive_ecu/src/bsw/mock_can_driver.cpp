#include "mock_can_driver.h"

#include <utility>

bool MockCanDriver::open(const std::string& interface_name) {
    std::lock_guard<std::mutex> lock(mutex_);
    interface_name_ = interface_name;
    opened_ = true;
    receiving_ = false;
    return true;
}

void MockCanDriver::close() {
    std::lock_guard<std::mutex> lock(mutex_);
    receiving_ = false;
    opened_ = false;
}

bool MockCanDriver::send(const CanFrame& frame) {
    CanCallback callback;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!opened_ || frame.dlc > frame.data.size()) {
            return false;
        }
        sent_frames_.push_back(frame);
        callback = callback_;
    }

    if (callback) {
        callback(frame);
    }
    return true;
}

void MockCanDriver::registerCallback(CanCallback callback) {
    std::lock_guard<std::mutex> lock(mutex_);
    callback_ = std::move(callback);
}

void MockCanDriver::startReceive() {
    std::lock_guard<std::mutex> lock(mutex_);
    receiving_ = opened_;
}

void MockCanDriver::stopReceive() {
    std::lock_guard<std::mutex> lock(mutex_);
    receiving_ = false;
}

bool MockCanDriver::isOpened() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return opened_;
}

bool MockCanDriver::isReceiving() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return receiving_;
}

std::string MockCanDriver::interfaceName() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return interface_name_;
}

std::vector<CanFrame> MockCanDriver::sentFrames() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return sent_frames_;
}

void MockCanDriver::clear() {
    std::lock_guard<std::mutex> lock(mutex_);
    sent_frames_.clear();
}
