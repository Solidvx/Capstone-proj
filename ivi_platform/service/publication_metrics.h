#pragma once
#include <cstdint>
#include <optional>
#include <stdexcept>

namespace ivi {
struct PublicationMetrics {
    std::uint64_t authenticated_bms=0,intervals=0;
    std::optional<double> mean_interval_us;
    std::optional<std::uint64_t> max_interval_us;
};
// Per-session application publication timing, not bus latency or bus load.
class PublicationMeter {
public:
    void reset(){value_={};last_.reset();mean_ns_=0;max_ns_=0;}
    void observe(std::uint64_t published_ns){
        if(last_ && published_ns<*last_)throw std::invalid_argument("publication clock regressed");
        ++value_.authenticated_bms;
        if(last_){
            const auto gap=published_ns-*last_;
            ++value_.intervals;
            mean_ns_+=(static_cast<long double>(gap)-mean_ns_)/value_.intervals;
            if(gap>max_ns_)max_ns_=gap;
            value_.mean_interval_us=static_cast<double>(mean_ns_/1000);
            value_.max_interval_us=max_ns_/1000;
        }
        last_=published_ns;
    }
    const PublicationMetrics& value()const{return value_;}
private:
    PublicationMetrics value_;
    std::optional<std::uint64_t> last_;
    long double mean_ns_=0;std::uint64_t max_ns_=0;
};
}
