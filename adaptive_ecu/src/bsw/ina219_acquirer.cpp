#include "ina219_acquirer.h"

#include <cmath>
#include <stdexcept>

namespace {
// 16V range, +/-320mV shunt, both ADCs 12bit, shunt+bus triggered.
constexpr std::uint16_t triggered = 0x199b;
std::int16_t signedWord(std::uint16_t value) {
    return static_cast<std::int16_t>(value < 0x8000 ? int(value) : int(value)-65536);
}
}

const char* ina219StatusName(Ina219Status status) {
    switch (status) {
    case Ina219Status::Waiting:return "WAITING";
    case Ina219Status::Complete:return "OK";
    case Ina219Status::NotStarted:return "NOT_STARTED";
    case Ina219Status::IoError:return "IO_ERROR";
    case Ina219Status::ConfigurationChanged:return "CONFIGURATION_CHANGED";
    case Ina219Status::Overflow:return "OVERFLOW";
    case Ina219Status::RangeError:return "RANGE_ERROR";
    case Ina219Status::Inconsistent:return "INCONSISTENT_REGISTERS";
    }
    return "UNKNOWN";
}

Ina219Acquirer::Ina219Acquirer(Ads1115Transport& transport, Ina219Config config)
    : transport_(transport), config_(config), calibration_(0), effective_lsb_(0) {
    if (!std::isfinite(config.shunt_ohm) || config.shunt_ohm<=0 ||
        !std::isfinite(config.requested_current_lsb_a) || config.requested_current_lsb_a<=0 ||
        (config.battery_current_sign!=1 && config.battery_current_sign!=-1) ||
        !std::isfinite(config.current_zero_a) || !std::isfinite(config.terminal_offset_v))
        throw std::invalid_argument("explicit finite INA219 calibration/sign required");
    const double value=std::floor(.04096/(config.requested_current_lsb_a*config.shunt_ohm));
    if (!std::isfinite(value) || value<2 || value>65535)
        throw std::invalid_argument("INA219 calibration outside register range");
    calibration_=static_cast<std::uint16_t>(value)&0xfffe; // FS0 is read-only zero
    effective_lsb_=.04096/(double(calibration_)*config.shunt_ohm);
    if (!std::isfinite(effective_lsb_) || !std::isfinite(effective_lsb_*32768))
        throw std::invalid_argument("INA219 current scale overflow");
}
bool Ina219Acquirer::read(std::uint8_t address,std::uint16_t& value) {
    std::uint8_t bytes[2];
    if (!transport_.readRegister(address,bytes,2))return false;
    value=(std::uint16_t(bytes[0])<<8)|bytes[1];return true;
}
bool Ina219Acquirer::write(std::uint8_t address,std::uint16_t value) {
    const std::uint8_t bytes[]{address,static_cast<std::uint8_t>(value>>8),static_cast<std::uint8_t>(value)};
    return transport_.write(bytes,3);
}
bool Ina219Acquirer::start() {
    pending_=false;
    // Calibration is volatile; restore explicitly before every new conversion.
    if (!write(5,calibration_) || !write(0,triggered))return false;
    pending_=true;return true;
}
Ina219Result Ina219Acquirer::poll() {
    if (!pending_)return {Ina219Status::NotStarted,{}};
    std::uint16_t bus=0;
    if (!read(2,bus)){pending_=false;return {Ina219Status::IoError,{}};}
    if (!(bus&2))return {Ina219Status::Waiting,{}};
    pending_=false;
    if (bus&1)return {Ina219Status::Overflow,{}};
    std::uint16_t shunt=0,current=0,cal=0,config=0;
    if (!read(1,shunt) || !read(4,current) || !read(5,cal) || !read(0,config))
        return {Ina219Status::IoError,{}};
    if (cal!=calibration_ || (config&0xfff8)!=(triggered&0xfff8) ||
        ((config&7)!=3 && (config&7)!=0))
        return {Ina219Status::ConfigurationChanged,{}};
    Ina219Measurement m{};
    m.bus_raw=bus;m.shunt_raw=signedWord(shunt);m.current_raw=signedWord(current);
    m.bus_v=double(bus>>3)*.004;m.shunt_v=double(m.shunt_raw)*.00001;
    m.terminal_v=m.bus_v+m.shunt_v+config_.terminal_offset_v;
    m.ina_current_a=double(m.current_raw)*effective_lsb_;
    m.battery_current_a=config_.battery_current_sign*(m.ina_current_a-config_.current_zero_a);
    if ((bus&4) || m.bus_v>16 || std::abs(int(m.shunt_raw))>32000 ||
        !std::isfinite(m.terminal_v) || !std::isfinite(m.battery_current_a) ||
        m.terminal_v<0 || m.terminal_v>26)
        return {Ina219Status::RangeError,{}};
    const double expected=double(m.shunt_raw)*calibration_/4096;
    if (std::abs(double(m.current_raw)-expected)>2)
        return {Ina219Status::Inconsistent,{}};
    return {Ina219Status::Complete,m};
}
