#pragma once

#include "ads1115_acquirer.h"
#include "sensor_quality.h"

#include <cstdint>
#include <optional>

// Per-cycle gate between the ADC worker and the 100 ms BMS loop.
// Each finished request counts once by sequence (R-3=A: three new valid
// results first and after any error). The cycle yields a pack voltage only
// while quality is Valid and the latest valid result is fresh; otherwise the
// caller pauses BMS transmission instead of resending an old value (D1).
// Byte 7 sensor state stays inactive until the ICD section 8 joint switch.
class HardwareSampleFeed {
public:
    // Two ADC-2 request intervals absorb phase drift between the worker and
    // the CAN loop. Design value to revisit with measurements.
    static constexpr std::uint64_t kFreshnessMs = 2 * AdcAcquisitionGate::kRequestIntervalMs;

    std::optional<float> cycle(const AdcSnapshot& adc, std::uint64_t now_ms) {
        if (adc.last_error_sequence > seen_sequence_) quality_.error();
        if (adc.last_valid_sequence > seen_sequence_ &&
            adc.last_valid_sequence > adc.last_error_sequence) {
            quality_.accept(true);
        }
        seen_sequence_ = adc.sequence;

        const bool fresh = adc.last_valid_sequence > 0 && now_ms >= adc.last_valid_ms &&
                           now_ms - adc.last_valid_ms <= kFreshnessMs;
        // A silent or stalled worker is an acquisition error once requests have run.
        if (!fresh && adc.sequence > 0) quality_.error();

        if (!fresh || quality_.state() != SensorQuality::Valid) return std::nullopt;
        return adc.pack_v;
    }

    SensorQuality quality() const { return quality_.state(); }

private:
    SensorQualityTracker quality_;
    std::uint64_t seen_sequence_ = 0;
};
