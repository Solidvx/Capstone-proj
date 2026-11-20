#pragma once
#include <cstdint>
#include <optional>
#include <string>

// Common model prior, not per-cell identification or calibrated capacity.
// Only the last estimate is restored; no interval may span process downtime.
class PhysicalSohTracker {
public:
    PhysicalSohTracker(double initial_percent,double nominal_ah,std::uint64_t max_interval_ms,
                       std::string state_path,std::string configuration);
    void accept(std::uint64_t sequence,std::uint64_t at,double voltage,double current,double temperature);
    void unavailable();
    double percent()const{return percent_;}
    const char* status()const{return status_;}
    std::uint64_t updates()const{return updates_;}
private:
    void clearRest();
    void save();
    double percent_,nominal_,net_ah_=0,rest_min_=0,rest_max_=0,rest_mean_=0,rest_temp_=0;
    std::uint64_t max_interval_,last_seq_=0,last_at_=0,rest_at_=0,rest_count_=0,updates_=0;
    double last_current_=0;
    std::string path_,configuration_;
    const char* status_="initial-prior";
    struct Anchor {double soc,ah,temperature;};
    std::optional<Anchor> anchor_;
};
