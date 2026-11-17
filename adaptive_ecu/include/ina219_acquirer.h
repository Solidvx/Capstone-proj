#pragma once

#include "ads1115_registers.h"

#include <cstdint>
#include <optional>

// Reuse the existing exact two-byte, MSB-first I2C transport seam. No ADS1115
// conversion settings or potentiometer/pack scaling are used here.
struct Ina219Config {
    double shunt_ohm;
    double requested_current_lsb_a;
    int battery_current_sign;  // explicitly +1 or -1; positive means charging
    double current_zero_a;    // INA-direction offset, before sign conversion
    double terminal_offset_v;
};

struct Ina219Measurement {
    std::uint16_t bus_raw;
    std::int16_t shunt_raw;
    std::int16_t current_raw;
    double bus_v;             // IN- relative to sensor GND
    double shunt_v;           // IN+ minus IN-
    double terminal_v;        // bus + shunt + explicit offset; not DMM-certified
    double ina_current_a;
    double battery_current_a;
};

enum class Ina219Status { Waiting, Complete, NotStarted, IoError,
                         ConfigurationChanged, Overflow, RangeError, Inconsistent };
struct Ina219Result {
    Ina219Status status;
    std::optional<Ina219Measurement> measurement;
};
const char* ina219StatusName(Ina219Status status);

// One triggered shunt+bus conversion at a time. Caller owns deadline/I/O
// lifetime. Reading only a completed single-shot avoids mixing live cycles.
class Ina219Acquirer {
public:
    explicit Ina219Acquirer(Ads1115Transport& transport, Ina219Config config);
    bool start();
    Ina219Result poll();
    std::uint16_t calibration() const { return calibration_; }
    double effectiveCurrentLsbA() const { return effective_lsb_; }
private:
    bool read(std::uint8_t address, std::uint16_t& value);
    bool write(std::uint8_t address, std::uint16_t value);
    Ads1115Transport& transport_;
    Ina219Config config_;
    std::uint16_t calibration_;
    double effective_lsb_;
    bool pending_ = false;
};
