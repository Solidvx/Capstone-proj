#pragma once

#include <cstdint>
#include <optional>

// Experimental single-cell SOC model. The reference curve is a typical Li-ion
// example, NOT a characterization of the installed cell or a protection policy.
class PhysicalSocEkf {
public:
    static constexpr const char* kModel = "auto-ekf-adi-liion-v1";
    static constexpr std::uint64_t kRestMs = 60000;
    static constexpr double kRestCurrentA = .020;
    static constexpr double kRestSpreadV = .010;
    explicit PhysicalSocEkf(double capacity_ah):capacity_ah_(capacity_ah){}
    void accept(std::uint64_t at_ms,double seconds,double delta_ah,double voltage,double current);
    void unavailable();
    std::optional<double> soc()const{return soc_;}
    std::optional<double> covariance()const{return soc_?std::optional<double>(covariance_):std::nullopt;}
    const char* step()const{return step_;}
private:
    double capacity_ah_,covariance_=0;
    std::optional<double> soc_;
    std::optional<std::uint64_t> rest_started_;
    double rest_min_=0,rest_max_=0,rest_mean_=0;
    unsigned rest_count_=0;
    const char* step_="waiting-rest";
};
