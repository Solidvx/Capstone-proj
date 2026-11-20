#pragma once

#include "bms_types.h"

#include <cstdint>
#include <functional>
#include <optional>

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
        REASON_MANUAL_RESET = 0x06,
        REASON_WATCHDOG_RESTART_FAILED = 0x07
    };

    using EventCallback = std::function<void(const FailSafeEvent&)>;

    State state() const;
    struct Snapshot {
        unsigned version = 2;
        State state = State::NORMAL;
        Reason reason = REASON_NONE;
        bool critical_latched = false;
    };
    Snapshot exportState() const;
    // Local recovery is not a new transition; it must not emit a CAN event.
    bool restoreState(const Snapshot& snapshot);
    void setEventCallback(EventCallback callback);
    bool evaluate(float soc_percent, int8_t temperature_c);
    // Monotonic milliseconds; invalid input or >200ms gaps restart cooling observation.
    bool evaluate(float soc_percent, int8_t temperature_c, std::uint64_t now_ms);
    void inputUnavailable();
    static constexpr std::uint64_t kCoolingHoldMs = 5000;
    static constexpr std::uint64_t kInputGapMs = 200;
    bool manualReset(float soc_percent = 100.0f, int8_t temperature_c = 25);
    // Call only after three real restart failures, never for timeout count.
    bool watchdogRestartsFailed(float soc_percent, int8_t temperature_c);

private:
    bool transitionTo(State next_state, Reason reason, float soc_percent, int8_t temperature_c);

    std::optional<std::uint64_t> cooling_since_, last_input_at_;
    bool critical_latched_ = false;
    State state_ = State::NORMAL;
    Reason reason_ = REASON_NONE;
    EventCallback callback_;
};
