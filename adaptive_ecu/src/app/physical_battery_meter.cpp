#include "physical_battery_meter.h"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <utility>

PhysicalBatteryMeter::PhysicalBatteryMeter(PhysicalMeterConfig config) {
    if(config.model_calibration_id.empty()||config.model_calibration_id.size()>128||
       !std::isfinite(config.nominal_capacity_ah)||config.nominal_capacity_ah<=0||
       !config.max_interval_ms||config.max_interval_ms>60000||
       (config.automatic_soc&&config.initial_soc)||
       (config.initial_soc && (!std::isfinite(*config.initial_soc)||*config.initial_soc<0||*config.initial_soc>1)))
        throw std::invalid_argument("explicit model/capacity/time and optional valid SOC prior required");
    state_.config=std::move(config);state_.estimated_soc=state_.config.initial_soc;
    if(state_.config.automatic_soc)automatic_soc_.emplace(state_.config.nominal_capacity_ah);
}
void PhysicalBatteryMeter::updateAutomaticSoc(std::uint64_t at,double seconds,double delta_ah,double voltage,double current){
    if(!automatic_soc_)return;
    automatic_soc_->accept(at,seconds,delta_ah,voltage,current);state_.estimated_soc=automatic_soc_->soc();
}
void PhysicalBatteryMeter::unavailable() {
    previous_.reset();state_.observation_gap=true;
    if(automatic_soc_)automatic_soc_->unavailable();
}
PhysicalMeterResult PhysicalBatteryMeter::accept(std::uint64_t sequence,std::uint64_t at,
    double voltage,double current) {
    if(!sequence||!std::isfinite(voltage)||voltage<0||voltage>26||!std::isfinite(current)){
        unavailable();return PhysicalMeterResult::Rejected;
    }
    if(sequence==highest_sequence_)return PhysicalMeterResult::Duplicate;
    if(sequence<highest_sequence_){unavailable();return PhysicalMeterResult::Rejected;}
    highest_sequence_=sequence;
    if(!previous_){previous_=Previous{at,voltage,current};updateAutomaticSoc(at,0,0,voltage,current);return PhysicalMeterResult::Anchored;}
    const auto prior=*previous_;
    if(at<=prior.at){unavailable();return PhysicalMeterResult::Rejected;}
    previous_=Previous{at,voltage,current};
    if(at-prior.at>state_.config.max_interval_ms){
        state_.observation_gap=true;if(automatic_soc_)automatic_soc_->unavailable();
        updateAutomaticSoc(at,0,0,voltage,current);return PhysicalMeterResult::Gap;
    }
    const double hours=double(at-prior.at)/3600000;
    double charge=0,discharge=0;
    // A zero-crossing interval is split into triangles, preserving both flows.
    if((prior.current<0&&current>0)||(prior.current>0&&current<0)){
        const double scale=std::max(std::abs(prior.current),std::abs(current));
        const double fraction=(std::abs(prior.current)/scale)/
            (std::abs(prior.current)/scale+std::abs(current)/scale);
        const double first=prior.current*hours*fraction/2;
        const double second=current*hours*(1-fraction)/2;
        charge=std::max(first,0.)+std::max(second,0.);
        discharge=std::max(-first,0.)+std::max(-second,0.);
    }else{
        const double integral=(prior.current/2+current/2)*hours;
        charge=std::max(integral,0.);discharge=std::max(-integral,0.);
    }
    const double energy=(prior.voltage*prior.current/2+voltage*current/2)*hours;
    if(!std::isfinite(state_.charged_ah+charge)||!std::isfinite(state_.discharged_ah+discharge)||
       !std::isfinite(state_.signed_energy_wh+energy)){
        unavailable();return PhysicalMeterResult::Rejected;
    }
    state_.charged_ah+=charge;state_.discharged_ah+=discharge;state_.signed_energy_wh+=energy;
    if(automatic_soc_)updateAutomaticSoc(at,double(at-prior.at)/1000,charge-discharge,voltage,current);
    else if(state_.estimated_soc)
        state_.estimated_soc=std::clamp(*state_.estimated_soc+(charge-discharge)/state_.config.nominal_capacity_ah,0.,1.);
    return PhysicalMeterResult::Integrated;
}
bool PhysicalBatteryMeter::restore(const PhysicalMeterState& saved) {
    const auto& a=state_.config;const auto& b=saved.config;
    // The physical application does not persist EKF/rest history yet. Never
    // restore just its SOC and silently discard covariance/initialization state.
    if(a.automatic_soc||b.automatic_soc||saved.version!=1||a.model_calibration_id!=b.model_calibration_id||
       a.nominal_capacity_ah!=b.nominal_capacity_ah||a.initial_soc!=b.initial_soc||
       a.max_interval_ms!=b.max_interval_ms||!std::isfinite(saved.charged_ah)||saved.charged_ah<0||
       !std::isfinite(saved.discharged_ah)||saved.discharged_ah<0||!std::isfinite(saved.signed_energy_wh)||
       saved.estimated_soc.has_value()!=a.initial_soc.has_value()||
       (saved.estimated_soc&&(!std::isfinite(*saved.estimated_soc)||*saved.estimated_soc<0||*saved.estimated_soc>1)))return false;
    state_=saved;
    // A prior host time/sample cannot bridge the process's unobserved downtime.
    unavailable();highest_sequence_=0;return true;
}

PhysicalSohEstimate estimatePhysicalSoh(const PhysicalMeterState& start,
    const PhysicalMeterState& end,bool endpoints_confirmed) {
    auto absent=[](PhysicalSohStatus status){return PhysicalSohEstimate{status,{},{},{}};};
    const auto& a=start.config;const auto& b=end.config;
    if(start.version!=1||end.version!=1||a.model_calibration_id.empty()||
       a.model_calibration_id!=b.model_calibration_id||a.nominal_capacity_ah!=b.nominal_capacity_ah||
       a.initial_soc!=b.initial_soc||a.max_interval_ms!=b.max_interval_ms||a.automatic_soc!=b.automatic_soc)
        return absent(PhysicalSohStatus::IncompatibleModel);
    if(!std::isfinite(a.nominal_capacity_ah)||a.nominal_capacity_ah<=0||
       !std::isfinite(start.charged_ah)||start.charged_ah<0||!std::isfinite(end.charged_ah)||
       end.charged_ah<start.charged_ah||!std::isfinite(start.discharged_ah)||start.discharged_ah<0||
       !std::isfinite(end.discharged_ah)||end.discharged_ah<start.discharged_ah)
        return absent(PhysicalSohStatus::InvalidCapacity);
    if(start.observation_gap||end.observation_gap)return absent(PhysicalSohStatus::ObservationGap);
    if(!endpoints_confirmed)return absent(PhysicalSohStatus::AwaitingCapacityTest);
    // A charge interruption is not the declared continuous full-discharge test.
    const double capacity=end.discharged_ah-start.discharged_ah;
    const double ratio=capacity/a.nominal_capacity_ah;
    if(end.charged_ah!=start.charged_ah||capacity<=0||!std::isfinite(ratio))
        return absent(PhysicalSohStatus::InvalidCapacity);
    return {PhysicalSohStatus::Estimated,capacity,ratio,std::clamp(ratio,0.,1.)*100};
}
