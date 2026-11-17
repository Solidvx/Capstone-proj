#pragma once

#include "ina219_acquirer.h"
#include "physical_battery_meter.h"
#include "sensor_quality.h"
#include <array>
#include <optional>
#include <string>
#include <vector>

struct PhysicalRuntimeConfig {
    std::string i2c_device,temperature_device,w1_root,calibration_id;
    unsigned ina_address=0,period_ms=0,read_timeout_ms=0,freshness_ms=0;
    Ina219Config ina{};
    PhysicalMeterConfig meter{};
    std::optional<double> measured_capacity_ah;
    std::string capacity_test_id;
    std::array<std::uint8_t,32> fingerprint{};
};
// Strict, explicit local configuration. No implicit sensor/model/timing prior.
PhysicalRuntimeConfig loadPhysicalRuntimeConfig(const std::string& path);

struct PhysicalSensorSample {
    std::uint64_t sequence=0,completed_ms=0,ina_ms=0,temperature_ms=0;
    std::optional<double> voltage_v,current_a,temperature_c;
    std::array<std::uint8_t,32> fingerprint{};
};
// Local owned-process IPC, separate from the authenticated CAN contract.
using PhysicalSensorPacket=std::array<std::uint8_t,84>;
PhysicalSensorPacket encodePhysicalSensorSample(const PhysicalSensorSample& sample);
std::optional<PhysicalSensorSample> decodePhysicalSensorSample(const PhysicalSensorPacket& packet);

struct PhysicalLiveValues {
    std::uint64_t sequence=0;
    std::optional<double> voltage_v,current_a,temperature_c,soc_percent,soh_percent;
    SensorQuality ina_quality=SensorQuality::Preparing,temperature_quality=SensorQuality::Preparing;
    std::uint32_t ina_age_ms=0xffffffffu,temperature_age_ms=0xffffffffu;
};
class PhysicalSampleFeed {
public:
    explicit PhysicalSampleFeed(PhysicalRuntimeConfig config);
    bool accept(const PhysicalSensorSample& sample,std::uint64_t now_ms);
    PhysicalLiveValues values(std::uint64_t now_ms);
    void unavailable();
    const PhysicalMeterState& meterState()const{return meter_.state();}
    unsigned socBasis()const{return meter_.socBasis();}
    const char* socUpdate()const{return meter_.socUpdate();}
    std::optional<double> socCovariance()const{return meter_.socCovariance();}
private:
    PhysicalRuntimeConfig config_;
    PhysicalBatteryMeter meter_;
    SensorQualityTracker ina_quality_,temperature_quality_;
    std::uint64_t sequence_=0,ina_ms_=0,temperature_ms_=0;
    std::optional<double> voltage_,current_,temperature_;
    bool ina_current_=false,temperature_current_=false;
};

// Owner-loop only; spawn/exec a single-thread reader before any device fork.
// Never invokes readSensorBounded inside the multithreaded ECU process.
class PhysicalSensorProcess {
public:
    PhysicalSensorProcess(const std::string& executable,const std::string& config_path,
                          std::array<std::uint8_t,32> fingerprint);
    ~PhysicalSensorProcess();
    PhysicalSensorProcess(const PhysicalSensorProcess&)=delete;
    PhysicalSensorProcess& operator=(const PhysicalSensorProcess&)=delete;
    std::vector<PhysicalSensorSample> poll();
    bool failed()const{return failed_;}
    bool stop();
private:
    int pid_=-1,fd_=-1;
    bool failed_=false;
    std::vector<std::uint8_t> pending_;
    std::array<std::uint8_t,32> fingerprint_;
};
