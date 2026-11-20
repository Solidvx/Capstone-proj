// Offline numeric bridge to the exact production-independent estimation core.
// Input is validated CSV from estimate_physical_capture.py, never CAN or a key.
#include "physical_battery_meter.h"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>

namespace {
double number(const std::string& text){
    std::size_t used=0;const auto value=std::stod(text,&used);
    if(used!=text.size()||!std::isfinite(value))throw std::invalid_argument("invalid finite number");
    return value;
}
std::uint64_t positive(const std::string& text){
    if(text.empty()||text.find_first_not_of("0123456789")!=std::string::npos)throw std::invalid_argument("invalid integer");
    const auto value=std::stoull(text);if(!value)throw std::invalid_argument("positive integer required");return value;
}
const char* resultName(PhysicalMeterResult status){
    switch(status){
    case PhysicalMeterResult::Anchored:return "ANCHORED";
    case PhysicalMeterResult::Integrated:return "INTEGRATED";
    case PhysicalMeterResult::Duplicate:return "DUPLICATE";
    case PhysicalMeterResult::Rejected:return "REJECTED";
    case PhysicalMeterResult::Gap:return "GAP";
    }
    return "UNKNOWN";
}
}
int main(int argc,char** argv){
    try{
        PhysicalMeterConfig config{};std::optional<double> measured;
        bool capacity=false,max_gap=false,confirmed=false;
        for(int i=1;i<argc;++i){
            const std::string flag=argv[i];
            if(flag=="--help"){
                std::cout<<"evaluate_physical_capture --model-id ID --capacity-ah N --max-interval-ms N\n"
                    " [--initial-soc-percent N] [--measured-capacity-ah N --capacity-test-confirmed]\n"
                    "stdin: sequence,monotonic_ms,voltage_v,current_a,status (OK or ERROR).\n"
                    "Offline numeric bridge; no device, CAN, key, service or UI.\n";return 0;
            }
            if(flag=="--capacity-test-confirmed"){confirmed=true;continue;}
            if(i+1>=argc)throw std::invalid_argument("missing option");
            const std::string value=argv[++i];
            if(flag=="--model-id")config.model_calibration_id=value;
            else if(flag=="--capacity-ah"){config.nominal_capacity_ah=number(value);capacity=true;}
            else if(flag=="--max-interval-ms"){config.max_interval_ms=positive(value);max_gap=true;}
            else if(flag=="--initial-soc-percent"){const auto soc=number(value);if(soc<0||soc>100)throw std::invalid_argument("SOC percent range");config.initial_soc=soc/100;}
            else if(flag=="--measured-capacity-ah"){measured=number(value);if(*measured<=0)throw std::invalid_argument("positive measured capacity required");}
            else throw std::invalid_argument("unknown option");
        }
        if(!capacity||!max_gap||measured.has_value()!=confirmed)throw std::invalid_argument("explicit model/timing and independently confirmed capacity required");
        PhysicalBatteryMeter meter(config);
        auto start=meter.state(),end=start;
        if(measured)end.discharged_ah=*measured;
        const auto soh=estimatePhysicalSoh(start,end,confirmed);
        if(measured&&soh.status!=PhysicalSohStatus::Estimated)throw std::invalid_argument("invalid capacity basis");
        std::string line;
        if(!std::getline(std::cin,line)||line!="sequence,monotonic_ms,voltage_v,current_a,status")
            throw std::invalid_argument("normalized CSV header required");
        std::cout<<std::setprecision(15);std::uint64_t count=0,highest=0,last_time=0;
        bool loss=false;
        while(std::getline(std::cin,line)){
            if(line.size()>512||++count>100000||std::count(line.begin(),line.end(),',')!=4)
                throw std::invalid_argument("bounded five-column CSV input required");
            std::istringstream input(line);std::string seq,time,voltage,current,status,extra;
            if(!std::getline(input,seq,',')||!std::getline(input,time,',')||!std::getline(input,voltage,',')||
               !std::getline(input,current,',')||!std::getline(input,status,',')||std::getline(input,extra,','))
                throw std::invalid_argument("invalid normalized row");
            const auto sequence=positive(seq),at=positive(time);
            if(sequence<=highest||(last_time&&at<last_time))throw std::invalid_argument("repeated/backward input");
            const bool skipped=highest&&sequence-highest!=1;
            if(skipped){meter.unavailable();loss=true;}
            highest=sequence;last_time=at;
            const char* result="UNAVAILABLE";
            if(status=="OK"){
                const auto status_code=meter.accept(sequence,at,number(voltage),number(current));
                if(status_code==PhysicalMeterResult::Rejected)throw std::invalid_argument("rejected numeric measurement");
                if(status_code==PhysicalMeterResult::Gap)loss=true;
                result=resultName(status_code);
            }else if(status=="ERROR"&&voltage.empty()&&current.empty()){
                meter.unavailable();loss=true;
            }else throw std::invalid_argument("explicit OK or empty ERROR required");
            const auto& state=meter.state();
            std::cout<<"{\"sequence\":"<<sequence<<",\"monotonic_ms\":"<<at<<",\"result\":\""<<result
                <<"\",\"soc_estimate_percent\":";
            if(state.estimated_soc)std::cout<<*state.estimated_soc*100;else std::cout<<"null";
            std::cout<<",\"soc_input_valid\":"<<(status=="OK"?"true":"false")
                <<",\"soc_initial_basis\":\""<<(config.initial_soc?"operator-supplied":"unknown")
                <<"\",\"observation_gap\":"<<(state.observation_gap?"true":"false")
                <<",\"charged_ah\":"<<state.charged_ah<<",\"discharged_ah\":"<<state.discharged_ah
                <<",\"signed_energy_wh\":"<<state.signed_energy_wh<<",\"soh_estimate_percent\":";
            if(soh.display_percent)std::cout<<*soh.display_percent;else std::cout<<"null";
            std::cout<<",\"soh_capacity_ratio\":";
            if(soh.capacity_ratio)std::cout<<*soh.capacity_ratio;else std::cout<<"null";
            std::cout<<",\"soh_basis\":\""<<(measured?"operator-confirmed-external-capacity":"awaiting-capacity-test")
                <<"\",\"measured_capacity_ah\":";
            if(measured)std::cout<<*measured;else std::cout<<"null";
            std::cout<<",\"physical_accuracy_verified\":false}"<<'\n';
        }
        if(std::cin.bad()||!count)throw std::invalid_argument("empty or unreadable input");
        return loss?1:0;
    }catch(const std::exception& error){std::cerr<<"estimation input failed: "<<error.what()<<'\n';return 2;}
}
