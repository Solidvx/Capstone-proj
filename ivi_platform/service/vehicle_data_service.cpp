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
                bms_state_.pending_payload = payload;
                bms_state_.pending_received_at = received_at;
                snapshot_.last_message = "BMS payload pending authentication";
                result = ProcessResult::kPendingAuthentication;
                break;

            case kCanIdBmsFailSafe:
                if (!parseFailSafeEvent(payload).has_value()) {
                    snapshot_.last_message = "Rejected invalid Fail-safe payload";
                    result = ProcessResult::kRejected;
                    break;
                }
                fail_safe_state_.pending_payload = payload;
                fail_safe_state_.pending_received_at = received_at;
                snapshot_.last_message = "Fail-safe payload pending authentication";
                result = ProcessResult::kPendingAuthentication;
                break;

            case kCanIdBmsSecOc: {
                const auto auth = parseSecOcAuth(payload);
                result = processAuth(kCanIdBmsStatus, *auth, bms_state_, received_at, notification);
                should_notify = result == ProcessResult::kPublished;
                break;
            }

            case kCanIdFailSafeSecOc: {
                const auto auth = parseSecOcAuth(payload);
                result = processAuth(
                    kCanIdBmsFailSafe, *auth, fail_safe_state_, received_at, notification);
                should_notify = result == ProcessResult::kPublished;
                break;
            }

            case kCanIdIdsAlert: {
                const auto alert = parseIdsAlert(payload);
                if (!alert.has_value()) {
                    snapshot_.last_message = "Rejected invalid IDS payload";
                    result = ProcessResult::kRejected;
                    break;
                }
                snapshot_.security_alert = alert->attack_type == 0U
                                               ? std::optional<SecurityAlert>{}
                                               : std::optional<SecurityAlert>{*alert};
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

VehicleSnapshot VehicleDataService::latest() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return snapshot_;
}

ProcessResult VehicleDataService::processAuth(std::uint32_t original_id,
                                              const SecOcAuth& auth,
                                              ProtectedState& state,
                                              Clock::time_point received_at,
                                              VehicleSnapshot& notification) {
    if (!verifier_.has_value() || !state.pending_payload.has_value()) {
        snapshot_.last_secoc_verified = false;
        ++snapshot_.secoc_failure_count;
        snapshot_.last_message = verifier_.has_value()
                                     ? "Rejected auth without pending original"
                                     : "Rejected auth because SecOC key is unavailable";
        appendLogLocked(snapshot_.last_message);
        return ProcessResult::kRejected;
    }

    const auto verification = verifier_->verify(static_cast<std::uint16_t>(original_id),
                                                 auth.rolling_counter,
                                                 *state.pending_payload,
                                                 auth.truncated_mac,
                                                 state.last_accepted_counter);
    if (!verification.accepted) {
        snapshot_.last_secoc_verified = false;
        ++snapshot_.secoc_failure_count;
        snapshot_.last_message = verification.mac_valid
                                     ? "Rejected SecOC rolling counter"
                                     : "Rejected SecOC MAC";
        appendLogLocked(snapshot_.last_message);
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
    } else {
        const auto parsed = parseFailSafeEvent(*state.pending_payload);
        if (!parsed.has_value()) {
            return ProcessResult::kRejected;
        }
        snapshot_.vehicle.fail_safe_state = parsed->new_state;
        snapshot_.vehicle.fail_safe_reason = parsed->reason;
    }

    snapshot_.vehicle.received_monotonic_ns = monotonicNanoseconds(received_at);
    snapshot_.last_secoc_verified = true;
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
