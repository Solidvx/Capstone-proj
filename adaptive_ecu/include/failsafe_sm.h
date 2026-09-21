#pragma once

#include "bms_types.h"

#include <cstdint>
#include <functional>

class FailSafeStateMachine {
public:
    enum class State : uint8_t {
        NORMAL = 0,
        WARNING = 1,
        CRITICAL = 2,
        SHUTDOWN = 3
    };

    enum Reason : uint8_t {
        REASON_NONE = 0x00,
        REASON_LOW_SOC_WARNING = 0x01,
        REASON_LOW_SOC_CRITICAL = 0x02,
        REASON_HIGH_TEMP_WARNING = 0x03,
        REASON_HIGH_TEMP_SHUTDOWN = 0x04,
        REASON_RECOVERED = 0x05,
        REASON_MANUAL_RESET = 0x06
    };

    using EventCallback = std::function<void(const FailSafeEvent&)>;

    State state() const;
    void setEventCallback(EventCallback callback);
    bool evaluate(float soc_percent, int8_t temperature_c);
    bool manualReset(float soc_percent = 100.0f, int8_t temperature_c = 25);

private:
    bool transitionTo(State next_state, Reason reason, float soc_percent, int8_t temperature_c);

    State state_ = State::NORMAL;
    EventCallback callback_;
};
