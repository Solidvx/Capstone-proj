#pragma once

#include <chrono>
#include <cstdint>
#include <functional>
#include <map>
#include <mutex>
#include <optional>
#include <string>
#include <vector>

#include "can_parser.h"
#include "secoc_verifier.h"

namespace ivi {

struct VehicleData {
    double soc_percent = 0.0;
    double soh_percent = 0.0;
    double voltage_v = 0.0;
    double current_a = 0.0;
    double temperature_c = 0.0;
    std::uint8_t fail_safe_state = 0;
    std::uint8_t fail_safe_reason = 0;
    std::uint8_t sensor_state = 0;
    bool stale = true;
    bool valid = false;
    std::uint64_t received_monotonic_ns = 0;
};

struct VehicleSnapshot {
    VehicleData vehicle{};
    std::optional<SecurityAlert> security_alert;
    std::uint64_t security_alert_sequence = 0;
    std::uint64_t last_good_age_ms = 0;
    std::uint64_t measurement_sequence = 0;
    std::uint64_t t1_received_ns = 0;
    std::uint64_t t2_published_ns = 0;
    bool last_secoc_verified = false;
    std::uint32_t secoc_failure_count = 0;
    std::uint32_t consecutive_secoc_failure_count = 0;
    std::uint32_t orphan_auth_count = 0;
    std::uint32_t pending_timeout_count = 0;
    std::uint32_t pending_overwrite_count = 0;
    std::uint32_t last_can_id = 0;
    std::string last_message = "Waiting for authenticated CAN data";
    std::vector<std::string> logs;
};

enum class ProcessResult {
    kIgnored,
    kPendingAuthentication,
    kPublished,
    kRejected,
};

class VehicleDataService {
public:
    using ObserverId = std::uint64_t;
    using Observer = std::function<void(const VehicleSnapshot&)>;
    using Clock = std::chrono::steady_clock;
    static constexpr auto kPendingTimeout = std::chrono::milliseconds{100};
    static constexpr auto kStaleTimeout = std::chrono::milliseconds{300};

    VehicleDataService() = default;
    explicit VehicleDataService(SecOcKey key);

    bool loadSecOcKey(const std::string& path);
    void setSecOcKey(SecOcKey key);
    bool hasSecOcKey() const;

    ObserverId registerObserver(Observer observer);
    bool unregisterObserver(ObserverId id);

    ProcessResult processFrame(std::uint32_t can_id,
                               const CanPayload& payload,
                               Clock::time_point received_at = Clock::now());
    bool refreshTime(Clock::time_point now = Clock::now());
    bool acknowledgeSecurityAlert(std::uint64_t sequence);
    VehicleSnapshot latest() const;
    // Expires unauthenticated pending originals on a silent bus; stale age stays in refreshTime().
    void pollTimeouts(Clock::time_point now = Clock::now());

private:
    struct ProtectedState {
        std::optional<CanPayload> pending_payload;
        std::optional<Clock::time_point> pending_received_at;
        std::optional<std::uint32_t> last_accepted_counter;
    };

    ProcessResult processAuth(std::uint32_t original_id,
                              const SecOcAuth& auth,
                              ProtectedState& state,
                              Clock::time_point received_at,
                              VehicleSnapshot& notification);
    void storePending(const CanPayload& payload,
                      Clock::time_point received_at,
                      ProtectedState& state,
                      const char* channel_name);
    bool expirePending(ProtectedState& state,
                       Clock::time_point received_at,
                       const char* channel_name);
    void recordSecOcFailureLocked(std::string message);
    void appendLogLocked(std::string message);
    void notify(const VehicleSnapshot& snapshot, const std::vector<Observer>& observers) const;
    static std::uint64_t monotonicNanoseconds(Clock::time_point time);

    mutable std::mutex mutex_;
    VehicleSnapshot snapshot_{};
    std::optional<SecOcVerifier> verifier_;
    ProtectedState bms_state_;
    ProtectedState fail_safe_state_;
    std::optional<Clock::time_point> last_good_bms_at_;
    std::map<ObserverId, Observer> observers_;
    ObserverId next_observer_id_ = 1;
};

}  // namespace ivi
