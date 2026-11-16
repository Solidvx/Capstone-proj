#include "failsafe_sm.h"

#include <utility>
#include <chrono>
#include <cmath>

namespace {
// The clock and its integral duration conversion do not throw. Keep this
// contract local: state-transition callbacks below may still propagate errors.
std::uint64_t monotonicMilliseconds() noexcept {
    return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}
}

FailSafeStateMachine::State FailSafeStateMachine::state() const {
    return state_;
}

FailSafeStateMachine::Snapshot FailSafeStateMachine::exportState() const {
    return {2, state_, reason_, critical_latched_};
}

bool FailSafeStateMachine::restoreState(const Snapshot& snapshot) {
    if (snapshot.version != 1 && snapshot.version != 2) return false;
    const auto reason = snapshot.reason;
    bool valid = false;
    switch (snapshot.state) {
    case State::NORMAL:
        valid = reason == REASON_NONE || reason == REASON_RECOVERED || reason == REASON_MANUAL_RESET;
        break;
    case State::WARNING:
        valid = reason == REASON_LOW_SOC_WARNING || reason == REASON_HIGH_TEMP_WARNING ||
                reason == REASON_WATCHDOG_RESTART_FAILED;
        break;
    case State::CRITICAL: valid = reason == REASON_LOW_SOC_CRITICAL; break;
    case State::SHUTDOWN: valid = reason == REASON_HIGH_TEMP_SHUTDOWN; break;
    }
    if (!valid) return false;
    if(snapshot.version==2 && ((snapshot.state==State::CRITICAL && !snapshot.critical_latched) ||
       (snapshot.critical_latched && snapshot.state!=State::CRITICAL && snapshot.state!=State::SHUTDOWN)))return false;
    // Old thermal snapshots did not record prior CRITICAL; never silently clear it.
    critical_latched_=snapshot.version==1 ?
        (snapshot.state==State::CRITICAL || snapshot.state==State::SHUTDOWN) : snapshot.critical_latched;
    inputUnavailable();
    state_ = snapshot.state;
    reason_ = reason;
    return true;
}

void FailSafeStateMachine::setEventCallback(EventCallback callback) {
    callback_ = std::move(callback);
}

void FailSafeStateMachine::inputUnavailable() {
    cooling_since_.reset();last_input_at_.reset();
}

bool FailSafeStateMachine::evaluate(float soc_percent, int8_t temperature_c) {
    return evaluate(soc_percent,temperature_c,monotonicMilliseconds());
}

bool FailSafeStateMachine::evaluate(float soc_percent, int8_t temperature_c,std::uint64_t now_ms) {
    if(!std::isfinite(soc_percent) || soc_percent<0 || soc_percent>100 || temperature_c<-10 || temperature_c>70){
        inputUnavailable();return false;
    }
    if(!last_input_at_ || now_ms<*last_input_at_ || now_ms-*last_input_at_>kInputGapMs)cooling_since_.reset();
    last_input_at_=now_ms;
    if(state_==State::SHUTDOWN){
        if(soc_percent<5)critical_latched_=true;
        if(temperature_c>55){cooling_since_.reset();return false;}
        if(!cooling_since_)cooling_since_=now_ms;
        if(now_ms-*cooling_since_<kCoolingHoldMs)return false;
        cooling_since_.reset();
        if(critical_latched_)return transitionTo(State::CRITICAL,REASON_LOW_SOC_CRITICAL,soc_percent,temperature_c);
        if(soc_percent<20)return transitionTo(State::WARNING,REASON_LOW_SOC_WARNING,soc_percent,temperature_c);
        return transitionTo(State::NORMAL,REASON_RECOVERED,soc_percent,temperature_c);
    }

    if (temperature_c > 60) {
        if (state_ == State::WARNING || state_ == State::CRITICAL) {
            return transitionTo(State::SHUTDOWN, REASON_HIGH_TEMP_SHUTDOWN, soc_percent, temperature_c);
        }
        // SHUTDOWN returned above; WARNING/CRITICAL returned just above.
        // The only remaining valid state is NORMAL.
        return transitionTo(State::WARNING, REASON_HIGH_TEMP_WARNING, soc_percent, temperature_c);
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

    // Healthy battery measurements do not prove a failed task was repaired.
    // Higher battery risks above still take precedence; the owner's independent
    // operator-required status remains authoritative for the task fault.
    if (state_ == State::WARNING && reason_ != REASON_WATCHDOG_RESTART_FAILED &&
        soc_percent >= 20.0f && temperature_c <= 55) {
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

bool FailSafeStateMachine::watchdogRestartsFailed(float soc_percent, int8_t temperature_c) {
    if (state_ != State::NORMAL) return false;
    return transitionTo(State::WARNING, REASON_WATCHDOG_RESTART_FAILED,
                        soc_percent, temperature_c);
}

bool FailSafeStateMachine::transitionTo(
    State next_state,
    Reason reason,
    float soc_percent,
    int8_t temperature_c) {
    // Private helper: every caller checks its source state and requests a
    // different destination. No externally callable same-state transition.
    if(next_state==State::CRITICAL)critical_latched_=true;
    if(next_state==State::NORMAL)critical_latched_=false;
    cooling_since_.reset();
    const State prev_state = state_;
    state_ = next_state;
    reason_ = reason;

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
