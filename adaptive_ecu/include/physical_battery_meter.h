#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include "physical_soc_ekf.h"

struct PhysicalMeterConfig {
    std::string model_calibration_id;
    double nominal_capacity_ah;
    std::optional<double> initial_soc;  // 0..1, explicit prior; exclusive with automatic_soc
    std::uint64_t max_interval_ms;
    bool automatic_soc=false; // explicit selection of PhysicalSocEkf::kModel
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

enum class PhysicalSohStatus { Estimated, AwaitingCapacityTest, ObservationGap,
                               IncompatibleModel, InvalidCapacity };
struct PhysicalSohEstimate {
    PhysicalSohStatus status;
    std::optional<double> usable_capacity_ah;
    std::optional<double> capacity_ratio;  // measured/reference, may exceed 1
    std::optional<double> display_percent; // bounded 0..100, retain raw ratio above
};

// Capacity-based SOH estimate from an independently confirmed full discharge
// interval. Never infer full endpoints from the coulomb SOC computed using the
// same nominal capacity: that circular calculation would always return 100%.
// Confirmation of actual start/end/temperature/load conditions belongs to the
// capacity test operator, not to the current/voltage trace alone.
PhysicalSohEstimate estimatePhysicalSoh(const PhysicalMeterState& start,
    const PhysicalMeterState& end,bool full_discharge_endpoints_confirmed);

// Integrates accepted INA voltage/current samples before CAN quantization.
// Positive current means charging. Optional reference EKF is single-cell only;
// no automatic full-cycle detection or cell-specific accuracy claim.
class PhysicalBatteryMeter {
public:
    explicit PhysicalBatteryMeter(PhysicalMeterConfig config);
    PhysicalMeterResult accept(std::uint64_t sequence,std::uint64_t monotonic_ms,
                              double terminal_v,double battery_current_a);
    void unavailable();
    const PhysicalMeterState& state() const { return state_; }
    bool restore(const PhysicalMeterState& saved);
    unsigned socBasis()const{return state_.config.automatic_soc?2:state_.config.initial_soc?1:0;}
    const char* socUpdate()const{return automatic_soc_?automatic_soc_->step():state_.estimated_soc?"coulomb":"unknown";}
    std::optional<double> socCovariance()const{return automatic_soc_?automatic_soc_->covariance():std::nullopt;}
private:
    void updateAutomaticSoc(std::uint64_t at,double seconds,double delta_ah,double voltage,double current);
    struct Previous {std::uint64_t at;double voltage,current;};
    PhysicalMeterState state_;
    std::optional<Previous> previous_;
    std::uint64_t highest_sequence_=0;
    std::optional<PhysicalSocEkf> automatic_soc_;
};
