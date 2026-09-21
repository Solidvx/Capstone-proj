#pragma once
#include <cstdint>

// ADC-1=A / ADC-2=A. Monotonic milliseconds supplied by the caller.
// No I2C calls; a worker owns the outstanding transaction until finish().
class AdcAcquisitionGate {
public:
    static constexpr unsigned kDataRateSps = 128;
    static constexpr unsigned kRequestIntervalMs = 100;
    static constexpr unsigned kPollIntervalMs = 1;
    static constexpr unsigned kAcceptanceWindowMs = 20;

    bool begin(std::uint64_t now_ms) {
        if (pending_ || (started_ && (now_ms < start_ms_ || now_ms - start_ms_ < kRequestIntervalMs)))
            return false;
        start_ms_ = poll_ms_ = now_ms;
        started_ = pending_ = true;
        return true;
    }
    bool expired(std::uint64_t now_ms) const {
        return pending_ && (now_ms < start_ms_ || now_ms - start_ms_ >= kAcceptanceWindowMs);
    }
    bool pollDue(std::uint64_t now_ms) {
        if (!pending_ || expired(now_ms) || now_ms < poll_ms_ || now_ms - poll_ms_ < kPollIntervalMs)
            return false;
        poll_ms_ = now_ms;
        return true;
    }
    // Call only after the worker's I2C operation has actually returned.
    // Expiry alone never releases ownership or permits an overlapping request.
    bool finish(std::uint64_t now_ms, bool new_valid_result) {
        if (!pending_) return false;
        const bool accepted = new_valid_result && !expired(now_ms);
        pending_ = false;
        return accepted;
    }
    bool pending() const { return pending_; }
private:
    bool started_ = false;
    bool pending_ = false;
    std::uint64_t start_ms_ = 0;
    std::uint64_t poll_ms_ = 0;
};
