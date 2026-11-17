#pragma once

#include <cstdint>
#include <optional>
#include <string>

struct PhysicalMeterConfig {
    std::string model_calibration_id;
    double nominal_capacity_ah;
    std::optional<double> initial_soc;  // 0..1, explicit prior; absent stays unknown
    std::uint64_t max_interval_ms;
};
struct PhysicalMeterState {
    unsigned version=1;
    PhysicalMeterConfig config;
    double charged_ah=0;
    double discharged_ah=0;
    double signed_energy_wh=0;
    std::optional<double> estimated_soc;
    bool observation_gap=false;
};
enum class PhysicalMeterResult { Anchored, Integrated, Duplicate, Rejected, Gap };

// Integrates accepted INA voltage/current samples before CAN quantization.
// Positive current means charging. No OCV claim, no automatic capacity/SOH fit.
class PhysicalBatteryMeter {
public:
    explicit PhysicalBatteryMeter(PhysicalMeterConfig config);
    PhysicalMeterResult accept(std::uint64_t sequence,std::uint64_t monotonic_ms,
                              double terminal_v,double battery_current_a);
    void unavailable();
    const PhysicalMeterState& state() const { return state_; }
    bool restore(const PhysicalMeterState& saved);
private:
    struct Previous {std::uint64_t at;double voltage,current;};
    PhysicalMeterState state_;
    std::optional<Previous> previous_;
    std::uint64_t highest_sequence_=0;
};
