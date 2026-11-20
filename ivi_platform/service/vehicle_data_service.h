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
#include "can_session_exchange.h"
#include "ids_submission_order.h"
#include "publication_metrics.h"
#include "diagnostic_tx_queue.h"
#include "incident_rejection_link.h"

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
    // Observation evidence for the last applied BMS, never an unauthenticated
    // pending candidate. No keys or new CAN fields are exposed here.
    std::optional<capstone::session_v2::AuthenticatedMessage> authenticated_bms;
    std::optional<capstone::session_v2::Nonce> authenticated_bms_context;
    std::uint32_t secoc_failure_count = 0;
    std::uint32_t consecutive_secoc_failure_count = 0;
    std::uint32_t orphan_auth_count = 0;
    std::uint32_t pending_timeout_count = 0;
    std::uint32_t pending_overwrite_count = 0;
    std::uint32_t last_can_id = 0;
    std::string last_message = "Waiting for authenticated CAN data";
    std::vector<std::string> logs;
    bool session_protocol=false;
    bool fail_safe_known=false;
    bool session_bms_ready=false;
    std::uint64_t session_generation=0;
    std::string connection_stage="legacy";
    std::optional<capstone::session_v2::DiagnosticMessage> authenticated_diagnostic;
    std::uint64_t diagnostic_revision=0;
    // A valid MAC/body alone does not establish freshness in the IDS ordering.
    bool incident_semantic_accepted=false;
    std::uint64_t incident_semantic_verified_ns=0;
    std::optional<std::vector<std::uint8_t>> local_rejection_record;
    std::uint64_t rejection_record_revision=0,rejection_report_drops=0;
    std::optional<capstone::session_v2::DiagnosticMessage> ecu_node_status;
    std::optional<capstone::session_v2::DiagnosticMessage> ecu_protection_status;
    bool protection_confirmed=false;
    bool session_state_ready=false;
    std::optional<capstone::session_v2::DiagnosticMessage> ecu_restart_plan;
    // ECU-origin measurements must never stand in for IVI receive statistics.
    std::optional<capstone::session_v2::DiagnosticMessage> ecu_metrics;
    bool ecu_metrics_fresh=false;
    PublicationMetrics ivi_publication_metrics;
    std::string last_rejection_message;
    bool security_observation_ready=false;
    std::optional<double> ecu_observed_fps;
    std::optional<std::uint32_t> ecu_observed_drops;
    std::optional<std::uint64_t> ivi_socket_drops;
    std::uint8_t unreconciled_incident_mask=0;
    std::uint8_t reconciled_unknown_mask=0;
    std::uint8_t observed_condition_mask=0;
    std::array<std::optional<capstone::session_v2::Nonce>,4> security_incident_ids{};
    capstone::session_v2::IncidentRejectionLink::Matches incident_rejection_ids{};
    std::uint64_t snapshot_revision=0;
};

enum class ProcessResult {
    kIgnored,
    kPendingAuthentication,
    kPublished,
    kRejected,
};

struct SessionServiceResult {
    ProcessResult result=ProcessResult::kIgnored;
    std::vector<capstone::session_v2::Frame> outgoing;
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
    // Select once at startup. A transport recovery must not reset protocol keys
    // or counters through this API. Normal reload is not a new session.
    void configureRejectionReports(std::size_t capacity,unsigned frame_budget,std::uint64_t expiry_ms);
    bool enableSession(SecOcKey key,capstone::session_v2::ExchangeLimits limits,
                       Clock::time_point now=Clock::now());
    SessionServiceResult processSessionFrame(const capstone::session_v2::Frame& frame,
        Clock::time_point received_at,Clock::time_point now=Clock::time_point::min());
    SessionServiceResult pollSession(Clock::time_point now=Clock::time_point::min());

    ObserverId registerObserver(Observer observer);
    bool unregisterObserver(ObserverId id);

    ProcessResult processFrame(std::uint32_t can_id,
                               const CanPayload& payload,
                               Clock::time_point received_at = Clock::now());
    bool refreshTime(Clock::time_point now = Clock::now());
    // Local filtered socket epoch; unknown when ancillary/receiver is unavailable.
    // This is not an ECU measurement, whole-bus coverage or interface RX errors.
    bool updateSocketDrops(std::optional<std::uint64_t> drops);
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
    SessionServiceResult updateSession(const capstone::session_v2::Frame* frame,
        Clock::time_point received_at,Clock::time_point now);
    bool applySessionLocked(Clock::time_point now,SessionServiceResult& result);

    mutable std::mutex mutex_;
    VehicleSnapshot snapshot_{};
    std::optional<SecOcVerifier> verifier_;
    ProtectedState bms_state_;
    ProtectedState fail_safe_state_;
    std::optional<Clock::time_point> last_good_bms_at_;
    std::map<ObserverId, Observer> observers_;
    ObserverId next_observer_id_ = 1;
    std::unique_ptr<capstone::session_v2::Exchange> session_;
    capstone::session_v2::Nonce verifier_instance_{};
    std::unique_ptr<capstone::session_v2::DiagnosticTxQueue> rejection_reports_;
    std::size_t rejection_capacity_=0;
    std::uint64_t rejection_queue_full_=0;
    std::optional<capstone::session_v2::Nonce> ids_source_;
    std::uint32_t ids_tick_=0;
    capstone::session_v2::IdsSubmissionOrder ids_order_;
    capstone::session_v2::IncidentRejectionLink incident_links_;
    PublicationMeter publication_meter_;
    std::optional<std::uint32_t> protection_sequence_;
    bool protection_inconsistent_=false;
    std::array<std::uint64_t,4> ids_quiet_ms_{};
    std::array<bool,4> ids_pending_end_{};
    std::uint8_t inherited_ids_mask_=0;
    std::optional<Clock::time_point> ids_observation_at_;
    std::optional<Clock::time_point> session_opened_at_;
    capstone::session_v2::Phase previous_session_phase_=capstone::session_v2::Phase::Dormant;
    std::optional<Clock::time_point> last_plan_receipt_at_;
    std::chrono::milliseconds session_receipt_cooldown_{0};
};

}  // namespace ivi
