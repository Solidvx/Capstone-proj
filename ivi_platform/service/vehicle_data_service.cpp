#include "vehicle_data_service.h"

#include <fstream>
#include <utility>

namespace ivi {

VehicleDataService::VehicleDataService(SecOcKey key) : verifier_(SecOcVerifier(key)) {}

bool VehicleDataService::loadSecOcKey(const std::string& path) {
    SecOcKey key{};
    std::ifstream input(path, std::ios::binary);
    if (!input.read(reinterpret_cast<char*>(key.data()), static_cast<std::streamsize>(key.size()))) {
        std::lock_guard<std::mutex> lock(mutex_);
        appendLogLocked("SecOC key load failed");
        return false;
    }
    if (input.peek() != std::ifstream::traits_type::eof()) {
        std::lock_guard<std::mutex> lock(mutex_);
        appendLogLocked("SecOC key length must be exactly 32 bytes");
        return false;
    }
    setSecOcKey(key);
    return true;
}

void VehicleDataService::setSecOcKey(SecOcKey key) {
    std::lock_guard<std::mutex> lock(mutex_);
    verifier_.emplace(key);
    appendLogLocked("SecOC key configured");
}

bool VehicleDataService::hasSecOcKey() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return verifier_.has_value();
}

VehicleDataService::ObserverId VehicleDataService::registerObserver(Observer observer) {
    if (!observer) {
        return 0;
    }
    std::lock_guard<std::mutex> lock(mutex_);
    const auto id = next_observer_id_++;
    observers_.emplace(id, std::move(observer));
    return id;
}

bool VehicleDataService::unregisterObserver(ObserverId id) {
    std::lock_guard<std::mutex> lock(mutex_);
    return observers_.erase(id) == 1U;
}

ProcessResult VehicleDataService::processFrame(std::uint32_t can_id,
                                               const CanPayload& payload,
                                               Clock::time_point received_at) {
    VehicleSnapshot notification;
    std::vector<Observer> observers;
    ProcessResult result = ProcessResult::kIgnored;
    bool should_notify = false;

    {
        std::lock_guard<std::mutex> lock(mutex_);
        snapshot_.last_can_id = can_id;

        switch (can_id) {
            case kCanIdBmsStatus:
                if (!parseBmsStatus(payload).has_value()) {
                    snapshot_.last_message = "Rejected invalid BMS payload";
                    result = ProcessResult::kRejected;
                    break;
                }
                storePending(payload, received_at, bms_state_, "BMS");
                result = ProcessResult::kPendingAuthentication;
                break;

            case kCanIdBmsFailSafe:
                if (!parseFailSafeEvent(payload).has_value()) {
                    snapshot_.last_message = "Rejected invalid Fail-safe payload";
                    result = ProcessResult::kRejected;
                    break;
                }
                storePending(payload, received_at, fail_safe_state_, "Fail-safe");
                result = ProcessResult::kPendingAuthentication;
                break;

            case kCanIdBmsSecOc: {
                const auto auth = parseSecOcAuth(payload);
                result = processAuth(kCanIdBmsStatus, *auth, bms_state_, received_at, notification);
                should_notify = result == ProcessResult::kPublished ||
                                result == ProcessResult::kRejected;
                if (result == ProcessResult::kRejected) {
                    notification = snapshot_;
                }
                break;
            }

            case kCanIdFailSafeSecOc: {
                const auto auth = parseSecOcAuth(payload);
                result = processAuth(
                    kCanIdBmsFailSafe, *auth, fail_safe_state_, received_at, notification);
                should_notify = result == ProcessResult::kPublished ||
                                result == ProcessResult::kRejected;
                if (result == ProcessResult::kRejected) {
                    notification = snapshot_;
                }
                break;
            }

            case kCanIdIdsAlert: {
                const auto alert = parseIdsAlert(payload);
                if (!alert.has_value()) {
                    snapshot_.last_message = "Rejected invalid IDS payload";
                    result = ProcessResult::kRejected;
                    break;
                }
                if (alert->attack_type == 0U) {
                    snapshot_.last_message =
                        "Ignored IDS clear frame; user acknowledgement is required";
                    appendLogLocked(snapshot_.last_message);
                    result = ProcessResult::kIgnored;
                    break;
                }
                snapshot_.security_alert = *alert;
                ++snapshot_.security_alert_sequence;
                snapshot_.last_message = "IDS event published";
                appendLogLocked(snapshot_.last_message);
                notification = snapshot_;
                result = ProcessResult::kPublished;
                should_notify = true;
                break;
            }

            default:
                snapshot_.last_message = "Ignored unsupported CAN ID";
                result = ProcessResult::kIgnored;
                break;
        }

        if (should_notify) {
            observers.reserve(observers_.size());
            for (const auto& entry : observers_) {
                observers.push_back(entry.second);
            }
        }
    }

    if (should_notify) {
        notify(notification, observers);
    }
    return result;
}

bool VehicleDataService::refreshTime(Clock::time_point now) {
    VehicleSnapshot notification;
    std::vector<Observer> observers;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!snapshot_.vehicle.valid || !last_good_bms_at_.has_value()) {
            return false;
        }

        const auto age = now <= *last_good_bms_at_
                             ? std::chrono::milliseconds{0}
                             : std::chrono::duration_cast<std::chrono::milliseconds>(
                                   now - *last_good_bms_at_);
        const auto age_ms = static_cast<std::uint64_t>(age.count());
        const bool stale = age >= kStaleTimeout;
        if (snapshot_.last_good_age_ms == age_ms && snapshot_.vehicle.stale == stale) {
            return false;
        }

        const bool became_stale = !snapshot_.vehicle.stale && stale;
        snapshot_.last_good_age_ms = age_ms;
        snapshot_.vehicle.stale = stale;
        if (became_stale) {
            snapshot_.last_message = "BMS data became stale; preserving last good values";
            appendLogLocked(snapshot_.last_message);
        }
        notification = snapshot_;
        observers.reserve(observers_.size());
        for (const auto& entry : observers_) {
            observers.push_back(entry.second);
        }
    }
    notify(notification, observers);
    return true;
}

bool VehicleDataService::acknowledgeSecurityAlert(std::uint64_t sequence) {
    VehicleSnapshot notification;
    std::vector<Observer> observers;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!snapshot_.security_alert.has_value() ||
            snapshot_.security_alert_sequence != sequence) {
            return false;
        }
        snapshot_.security_alert.reset();
        snapshot_.last_message = "IDS event acknowledged by user";
        appendLogLocked(snapshot_.last_message);
        notification = snapshot_;
        observers.reserve(observers_.size());
        for (const auto& entry : observers_) {
            observers.push_back(entry.second);
        }
    }
    notify(notification, observers);
    return true;
}

VehicleSnapshot VehicleDataService::latest() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return snapshot_;
}

ProcessResult VehicleDataService::processAuth(std::uint32_t original_id,
                                              const SecOcAuth& auth,
                                              ProtectedState& state,
                                              Clock::time_point received_at,
                                              VehicleSnapshot& notification) {
    const char* channel_name = original_id == kCanIdBmsStatus ? "BMS" : "Fail-safe";
    if (!verifier_.has_value()) {
        recordSecOcFailureLocked("Rejected auth because SecOC key is unavailable");
        return ProcessResult::kRejected;
    }
    if (!state.pending_payload.has_value()) {
        ++snapshot_.orphan_auth_count;
        recordSecOcFailureLocked(std::string("Rejected ") + channel_name +
                                 " auth without pending original");
        return ProcessResult::kRejected;
    }
    if (expirePending(state, received_at, channel_name)) {
        recordSecOcFailureLocked(std::string("Rejected expired ") + channel_name +
                                 " pending original");
        return ProcessResult::kRejected;
    }

    const auto verification = verifier_->verify(static_cast<std::uint16_t>(original_id),
                                                 auth.rolling_counter,
                                                 *state.pending_payload,
                                                 auth.truncated_mac,
                                                 state.last_accepted_counter);
    if (!verification.accepted) {
        recordSecOcFailureLocked(verification.mac_valid
                                     ? "Rejected SecOC rolling counter"
                                     : "Rejected SecOC MAC");
        return ProcessResult::kRejected;
    }

    if (original_id == kCanIdBmsStatus) {
        const auto parsed = parseBmsStatus(*state.pending_payload);
        if (!parsed.has_value()) {
            return ProcessResult::kRejected;
        }
        snapshot_.vehicle.soc_percent = parsed->soc_percent;
        snapshot_.vehicle.soh_percent = parsed->soh_percent;
        snapshot_.vehicle.voltage_v = parsed->voltage_v;
        snapshot_.vehicle.current_a = parsed->current_a;
        snapshot_.vehicle.temperature_c = parsed->temperature_c;
        snapshot_.vehicle.valid = true;
        snapshot_.vehicle.stale = false;
        snapshot_.last_good_age_ms = 0;
        const auto original_received_at = *state.pending_received_at;
        last_good_bms_at_ = received_at;
        snapshot_.vehicle.received_monotonic_ns = monotonicNanoseconds(original_received_at);
        ++snapshot_.measurement_sequence;
        snapshot_.t1_received_ns = monotonicNanoseconds(original_received_at);
        snapshot_.t2_published_ns = monotonicNanoseconds(Clock::now());
    } else {
        const auto parsed = parseFailSafeEvent(*state.pending_payload);
        if (!parsed.has_value()) {
            return ProcessResult::kRejected;
        }
        snapshot_.vehicle.fail_safe_state = parsed->new_state;
        snapshot_.vehicle.fail_safe_reason = parsed->reason;
    }

    snapshot_.last_secoc_verified = true;
    snapshot_.consecutive_secoc_failure_count = 0;
    snapshot_.last_message = original_id == kCanIdBmsStatus
                                 ? "Authenticated BMS data published"
                                 : "Authenticated Fail-safe event published";
    appendLogLocked(snapshot_.last_message);
    state.last_accepted_counter = auth.rolling_counter;
    state.pending_payload.reset();
    state.pending_received_at.reset();
    notification = snapshot_;
    return ProcessResult::kPublished;
}

void VehicleDataService::storePending(const CanPayload& payload,
                                      Clock::time_point received_at,
                                      ProtectedState& state,
                                      const char* channel_name) {
    (void)expirePending(state, received_at, channel_name);
    if (state.pending_payload.has_value()) {
        ++snapshot_.pending_overwrite_count;
        appendLogLocked(std::string(channel_name) +
                        " pending original replaced by newer original");
    }
    state.pending_payload = payload;
    state.pending_received_at = received_at;
    snapshot_.last_message = std::string(channel_name) + " payload pending authentication";
}

bool VehicleDataService::expirePending(ProtectedState& state,
                                       Clock::time_point received_at,
                                       const char* channel_name) {
    if (!state.pending_payload.has_value() || !state.pending_received_at.has_value()) {
        return false;
    }
    if (received_at < *state.pending_received_at ||
        received_at - *state.pending_received_at < kPendingTimeout) {
        return false;
    }
    state.pending_payload.reset();
    state.pending_received_at.reset();
    ++snapshot_.pending_timeout_count;
    appendLogLocked(std::string(channel_name) + " pending original expired");
    return true;
}

void VehicleDataService::recordSecOcFailureLocked(std::string message) {
    snapshot_.last_secoc_verified = false;
    ++snapshot_.secoc_failure_count;
    ++snapshot_.consecutive_secoc_failure_count;

    if (snapshot_.consecutive_secoc_failure_count >= 10U) {
        message = "CRITICAL: " + message;
    } else if (snapshot_.consecutive_secoc_failure_count >= 4U) {
        message = "WARNING: " + message;
    }
    snapshot_.last_message = std::move(message);
    appendLogLocked(snapshot_.last_message);
}

void VehicleDataService::appendLogLocked(std::string message) {
    snapshot_.logs.push_back(std::move(message));
    constexpr std::size_t kMaxLogs = 80;
    if (snapshot_.logs.size() > kMaxLogs) {
        snapshot_.logs.erase(snapshot_.logs.begin(),
                             snapshot_.logs.begin() +
                                 static_cast<std::ptrdiff_t>(snapshot_.logs.size() - kMaxLogs));
    }
}

void VehicleDataService::notify(const VehicleSnapshot& snapshot,
                                const std::vector<Observer>& observers) const {
    for (const auto& observer : observers) {
        if (observer) {
            observer(snapshot);
        }
    }
}

std::uint64_t VehicleDataService::monotonicNanoseconds(Clock::time_point time) {
    return static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::nanoseconds>(time.time_since_epoch()).count());
}

}  // namespace ivi
