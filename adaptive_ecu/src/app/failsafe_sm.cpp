#include "failsafe_sm.h"

#include <utility>

FailSafeStateMachine::State FailSafeStateMachine::state() const {
    return state_;
}

void FailSafeStateMachine::setEventCallback(EventCallback callback) {
    callback_ = std::move(callback);
}

bool FailSafeStateMachine::evaluate(float soc_percent, int8_t temperature_c) {
    if (temperature_c > 60) {
        if (state_ == State::WARNING || state_ == State::CRITICAL) {
            return transitionTo(State::SHUTDOWN, REASON_HIGH_TEMP_SHUTDOWN, soc_percent, temperature_c);
        }
        if (state_ == State::NORMAL) {
            return transitionTo(State::WARNING, REASON_HIGH_TEMP_WARNING, soc_percent, temperature_c);
        }
        return false;
    }

    if (soc_percent < 5.0f && state_ == State::WARNING) {
        return transitionTo(State::CRITICAL, REASON_LOW_SOC_CRITICAL, soc_percent, temperature_c);
    }

    if (state_ == State::NORMAL) {
        if (soc_percent < 20.0f) {
            return transitionTo(State::WARNING, REASON_LOW_SOC_WARNING, soc_percent, temperature_c);
        }
        if (temperature_c > 55) {
            return transitionTo(State::WARNING, REASON_HIGH_TEMP_WARNING, soc_percent, temperature_c);
        }
        return false;
    }

    if (state_ == State::WARNING && soc_percent >= 20.0f && temperature_c <= 55) {
        return transitionTo(State::NORMAL, REASON_RECOVERED, soc_percent, temperature_c);
    }

    return false;
}

bool FailSafeStateMachine::manualReset(float soc_percent, int8_t temperature_c) {
    if (state_ != State::SHUTDOWN) {
        return false;
    }
    return transitionTo(State::NORMAL, REASON_MANUAL_RESET, soc_percent, temperature_c);
}

bool FailSafeStateMachine::transitionTo(
    State next_state,
    Reason reason,
    float soc_percent,
    int8_t temperature_c) {
    if (next_state == state_) {
        return false;
    }

    const State prev_state = state_;
    state_ = next_state;

    if (callback_) {
        callback_({
            static_cast<uint8_t>(prev_state),
            static_cast<uint8_t>(next_state),
            static_cast<uint8_t>(reason),
            soc_percent,
            temperature_c,
        });
    }
    return true;
}
