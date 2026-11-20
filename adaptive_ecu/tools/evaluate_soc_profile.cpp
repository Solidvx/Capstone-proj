// S-21 synthetic evaluation: actual product CSV input and estimator, no CAN.
// Only observations are passed here. Separate truth remains in the PC scorer.
#include "ekf_soc_estimator.h"
#include "sensor_simulator.h"
#include "can_publisher.h"

#include <algorithm>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <sstream>

int main(int argc,char** argv) {
    if(argc==2 && std::string(argv[1])=="--help") {
        std::cout<<"evaluate_soc_profile --profile OBSERVATIONS.csv --samples N [--emit-bms]\n"
                 <<"S-21: dt=0.1s, initial SOC=80%, capacity=50Ah. No truth/key/CAN input.\n";
        return 0;
    }
    try {
        if((argc!=5 && argc!=6) || std::string(argv[1])!="--profile" || std::string(argv[3])!="--samples" ||
            (argc==6 && std::string(argv[5])!="--emit-bms"))
            throw std::invalid_argument("expected --profile FILE --samples N");
        const bool emit_bms=argc==6;
        const std::string count(argv[4]);
        if(count.empty() || count.size()>5 || count.find_first_not_of("0123456789")!=std::string::npos)
            throw std::invalid_argument("samples must be an integer in [1,36000]");
        const auto samples=std::stoul(count);
        if(samples<1 || samples>36000)throw std::invalid_argument("samples out of range");
        SensorSimulator sensor(SensorSimulator::Mode::PROFILE_CSV,argv[2]);
        // Prevent the product simulator's intentional last-row hold from
        // turning an incomplete capture into a complete measurement sequence.
        if(sensor.exportState().profile_size!=samples)
            throw std::invalid_argument("profile row count does not match requested samples");
        EkfSocEstimator::Config config;config.initial_soc=.8f;config.capacity_ah=50.f;
        EkfSocEstimator estimator(config);
        double coulomb=config.initial_soc;
        constexpr float dt=.1f;
        std::cout<<std::setprecision(17)
                 <<"time_s,observed_voltage_v,observed_current_a,estimated_soc_pct,coulomb_soc_pct";
        if(emit_bms)std::cout<<",bms_payload_hex";
        std::cout<<'\n';
        for(unsigned long k=1;k<=samples;++k) {
            const auto sample=sensor.next();
            if(!std::isfinite(sample.voltage_v) || !std::isfinite(sample.current_a) ||
               sample.voltage_v<30 || sample.voltage_v>42 || sample.current_a<-10 || sample.current_a>5 ||
               sample.temperature_c!=25)
                throw std::invalid_argument("invalid S-21 observation");
            const double estimated=estimator.update(dt,sample.current_a,sample.voltage_v);
            // Identical float-quantized current, dt, initial SOC and capacity.
            coulomb=std::clamp(coulomb+double(sample.current_a)*double(dt)/(double(config.capacity_ah)*3600.),0.,1.);
            if(!std::isfinite(estimated) || estimated<0 || estimated>1 || !std::isfinite(coulomb))
                throw std::runtime_error("nonfinite or out-of-range estimate");
            std::cout<<k*.1<<','<<sample.voltage_v<<','<<sample.current_a<<','
                     <<estimated*100<<','<<coulomb*100;
            if(emit_bms){
                const auto frame=encodeBmsStatusFrame({static_cast<float>(estimated)*100.f,100.f,
                    sample.voltage_v,sample.current_a,sample.temperature_c});
                std::ostringstream bytes;bytes<<std::hex<<std::setfill('0');
                for(auto value:frame.data)bytes<<std::setw(2)<<static_cast<unsigned>(value);
                std::cout<<','<<bytes.str();
            }
            std::cout<<'\n';
        }
        std::cout.flush();
        if(!std::cout)throw std::runtime_error("evaluation output failed");
        return 0;
    }catch(const std::exception& error) {
        std::cerr<<"SOC profile evaluation failed: "<<error.what()<<'\n';
        return 2;
    }
}
