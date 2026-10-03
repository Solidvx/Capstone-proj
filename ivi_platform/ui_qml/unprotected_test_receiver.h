#pragma once

#include "vehicle_data_service.h"

// Used only by the separately built experiment executable. Product Service
// authentication is never disabled and its API remains unchanged.
class UnprotectedTestReceiver {
public:
    ivi::ProcessResult process(std::uint32_t id, const ivi::CanPayload& data) {
        if (id == ivi::kCanIdBmsStatus) {
            const auto value = ivi::parseBmsStatus(data);
            if (!value) return ivi::ProcessResult::kRejected;
            snapshot_.vehicle.soc_percent = value->soc_percent;
            snapshot_.vehicle.soh_percent = value->soh_percent;
            snapshot_.vehicle.voltage_v = value->voltage_v;
            snapshot_.vehicle.current_a = value->current_a;
            snapshot_.vehicle.temperature_c = value->temperature_c;
            snapshot_.vehicle.valid = true;
            snapshot_.vehicle.stale = false;
        } else if (id == ivi::kCanIdBmsFailSafe) {
            const auto value = ivi::parseFailSafeEvent(data);
            if (!value) return ivi::ProcessResult::kRejected;
            snapshot_.vehicle.fail_safe_state = value->new_state;
            snapshot_.vehicle.fail_safe_reason = value->reason;
        } else {
            return ivi::ProcessResult::kIgnored;
        }
        snapshot_.last_secoc_verified = false;
        snapshot_.last_message = "EXPERIMENT ONLY: unauthenticated data published";
        return ivi::ProcessResult::kPublished;
    }
    ivi::VehicleSnapshot latest() const { return snapshot_; }
private:
    ivi::VehicleSnapshot snapshot_;
};
