// Test-only probe of the actual product CSV loader. No EKF, CAN or device.
#include "sensor_simulator.h"

#include <cmath>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

int main(int argc,char** argv) {
    try {
        if(argc!=5 || std::string(argv[1])!="--profile" || std::string(argv[3])!="--samples")
            throw std::invalid_argument("expected --profile FILE --samples N");
        const std::string count(argv[4]);
        if(count.empty() || count.size()>5 || count.find_first_not_of("0123456789")!=std::string::npos)
            throw std::invalid_argument("samples must be an integer");
        const auto size=std::stoul(count);
        if(size<1 || size>36000)throw std::invalid_argument("samples out of range");
        SensorSimulator source(SensorSimulator::Mode::PROFILE_CSV,argv[2]);
        if(source.exportState().profile_size!=size)
            throw std::invalid_argument("actual row count differs; no last-row hold allowed");
        std::cout<<std::setprecision(17)<<"voltage_v,current_a,temperature_c\n";
        for(unsigned long k=0;k<size;++k) {
            const auto value=source.next();
            if(!std::isfinite(value.voltage_v) || !std::isfinite(value.current_a))
                throw std::invalid_argument("nonfinite observed value");
            std::cout<<value.voltage_v<<','<<value.current_a<<','<<static_cast<int>(value.temperature_c)<<'\n';
        }
        std::cout.flush();
        if(!std::cout)throw std::runtime_error("loader output failed");
        return 0;
    }catch(const std::exception& error) {
        std::cerr<<"profile loader fixture: "<<error.what()<<'\n';return 2;
    }
}
