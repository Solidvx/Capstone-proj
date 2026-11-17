#include "physical_soc_ekf.h"

#include <algorithm>
#include <array>
#include <cmath>

namespace {
// Analog Devices, "Characterizing a Lithium-Ion (Li+) Cell for Use with an
// Open-Circuit-Voltage (OCV) Based Fuel Gauge", Table 1, typical-cell example:
// https://www.analog.com/en/resources/design-notes/characterizing-a-lithiumion-li-cell-for-use-with-an-opencircuitvoltage-ocv-based-fuel-gauge.html
// Ascending SOC, 0..100% in 5% steps. No claim of cell chemistry equivalence,
// calibrated accuracy, thermal compensation, or loaded-voltage compensation.
constexpr std::array<double,21> ocv{{3.305545,3.674776,3.686654,3.709800,3.741018,
    3.762185,3.775129,3.783504,3.793250,3.805737,3.820965,3.841219,3.884009,
    3.917968,3.945074,3.974769,4.008118,4.045427,4.085934,4.129486,4.177454}};
constexpr double process_variance_per_second=1e-7;
constexpr double voltage_variance=.03*.03;
constexpr double initial_variance=.20*.20;
unsigned segment(double soc){return std::min(19u,static_cast<unsigned>(soc*20));}
double voltageAt(double soc){
    const auto i=segment(soc);return ocv[i]+(soc*20-i)*(ocv[i+1]-ocv[i]);
}
double slopeAt(double soc){const auto i=segment(soc);return (ocv[i+1]-ocv[i])*20;}
double initialSoc(double voltage){
    if(voltage<=ocv.front())return 0;
    if(voltage>=ocv.back())return 1;
    const auto i=static_cast<unsigned>(std::upper_bound(ocv.begin(),ocv.end(),voltage)-ocv.begin()-1);
    return (i+(voltage-ocv[i])/(ocv[i+1]-ocv[i]))/20;
}
}

void PhysicalSocEkf::unavailable(){
    rest_started_.reset();rest_count_=0;step_=soc_?"held-gap":"waiting-rest";
}

void PhysicalSocEkf::accept(std::uint64_t at,double seconds,double delta_ah,double voltage,double current){
    // Do not show a retained SOC for an absent cell or an out-of-model input.
    // This invalidates this model, not the voltage/current measurement itself.
    if(voltage<3.0||voltage>4.25){
        soc_.reset();covariance_=0;unavailable();step_="voltage-out-of-range";return;
    }
    if(soc_){
        *soc_=std::clamp(*soc_+delta_ah/capacity_ah_,0.,1.);
        covariance_=std::min(1.,covariance_+process_variance_per_second*seconds);
        step_="predicted";
    }else step_="waiting-rest";
    // Reference-model input domain, not a charge/discharge cutoff. Endpoint
    // clamping below only bounds the estimate; it does not attest empty/full.
    if(std::abs(current)>kRestCurrentA){
        rest_started_.reset();rest_count_=0;return;
    }
    if(!rest_started_||std::max(rest_max_,voltage)-std::min(rest_min_,voltage)>kRestSpreadV){
        rest_started_=at;rest_min_=rest_max_=rest_mean_=voltage;rest_count_=1;return;
    }
    rest_min_=std::min(rest_min_,voltage);rest_max_=std::max(rest_max_,voltage);
    rest_mean_+=(voltage-rest_mean_)/++rest_count_;
    if(at-*rest_started_<kRestMs||rest_count_<3)return;
    if(!soc_){
        soc_=initialSoc(rest_mean_);covariance_=initial_variance;step_="initialized";
    }else{
        const double h=slopeAt(*soc_);
        const double gain=covariance_*h/(h*h*covariance_+voltage_variance);
        *soc_=std::clamp(*soc_+gain*(rest_mean_-voltageAt(*soc_)),0.,1.);
        const double residual=1-gain*h;
        covariance_=std::max(1e-12,residual*residual*covariance_+gain*gain*voltage_variance);
        step_="corrected";
    }
    // One update per independent stability window; repeated reports of the
    // same resting value must not collapse covariance at the CAN report rate.
    rest_started_.reset();rest_count_=0;
}
