#pragma once
#include <cstdint>

// ICD section 8 approved target. Not yet connected to CAN serialization.
enum class SensorQuality : std::uint8_t {
    Preparing = 1, Valid = 2, ErrorWithoutValue = 3, ErrorWithValue = 4,
    RecoveringWithoutValue = 5, RecoveringWithValue = 6
};

class SensorQualityTracker {
public:
    // Caller must identify a genuinely new completed conversion. A repeated
    // read/retransmission is not new; I2C/freshness failure calls error().
    bool accept(bool new_valid_conversion) {
        if (!new_valid_conversion) return false;
        if (consecutive_ < 3) ++consecutive_;
        if (consecutive_ == 3) {
            has_value_ = true;
            state_ = SensorQuality::Valid;
            return true;
        }
        state_ = recovering_
            ? (has_value_ ? SensorQuality::RecoveringWithValue : SensorQuality::RecoveringWithoutValue)
            : SensorQuality::Preparing;
        return false;
    }
    void error() {
        consecutive_ = 0;
        recovering_ = true;
        state_ = has_value_ ? SensorQuality::ErrorWithValue : SensorQuality::ErrorWithoutValue;
    }
    SensorQuality state() const { return state_; }
private:
    SensorQuality state_ = SensorQuality::Preparing;
    unsigned consecutive_ = 0;
    bool has_value_ = false;
    bool recovering_ = false;
};
