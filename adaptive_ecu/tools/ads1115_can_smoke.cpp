// Physical input-to-display diagnostic. Not the product BMS runtime.
#include "ads1115_sample.h"
#include "sensor_quality.h"
#include "can_publisher.h"
#include "can_cdd.h"
#include "ekf_soc_estimator.h"
#include "linux_i2c_transport.h"

#include <chrono>
#include <csignal>
#include <iostream>
#include <thread>
#include <string>

namespace {
volatile std::sig_atomic_t running = 1;
void stop(int) { running = 0; }
using Clock = std::chrono::steady_clock;
std::uint64_t nowMs() {
    return std::chrono::duration_cast<std::chrono::milliseconds>(
        Clock::now().time_since_epoch()).count();
}
}

int main(int argc, char** argv) {
    std::string device = "/dev/i2c-1";
    std::string interface;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--help") {
            std::cout << "ads1115_can_smoke [--i2c-device /dev/i2c-1] [--interface can0]\n"
                         "No --interface: ADC read-only diagnostic (no CAN transmission).\n";
            return 0;
        }
        if ((arg != "--i2c-device" && arg != "--interface") || i + 1 >= argc) {
            std::cerr << "Unknown or incomplete option: " << arg << '\n';
            return 2;
        }
        (arg == "--i2c-device" ? device : interface) = argv[++i];
    }
    LinuxI2cTransport bus(device);
    if (!bus.ready()) {
        std::cerr << "I2C open/setup failed: " << device << " (address 0x48)\n";
        return 2;
    }
    SocketCanCdd can;
    if (!interface.empty() && !can.open(interface)) {
        std::cerr << "CAN open failed: " << interface << '\n';
        return 2;
    }
    std::signal(SIGINT, stop);
    std::signal(SIGTERM, stop);
    Ads1115Registers adc(bus);
    SensorQualityTracker quality;
    EkfSocEstimator estimator;
    bool calculation_continuous = false;
    unsigned failures = 0;
    std::cout << "DIAGNOSTIC ONLY: A0 real; pack=30..42V virtual; current=-2A, temp=25C, SOH=100% simulated.\n"
                 "No SecOC/FailSafe events. On ADC error no frames are sent; IVI may retain old values.\n";
    while (running) {
        const auto start = Clock::now();
        Ads1115Sample sample;
        const bool valid = acquireAds1115Sample(adc, nowMs, [] {
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }, sample);
        if (!running) break;
        if (!valid) {
            quality.error();
            calculation_continuous = false;
            if (++failures == 1 || failures % 10 == 0)
                std::cerr << "ADC ERROR: I/O, config, range or >=20ms result; CAN TX PAUSED\n";
        } else if (quality.accept(true)) {
            failures = 0;
            // No invented integration across acquisition gaps; restart this diagnostic estimator.
            if (!calculation_continuous) estimator = EkfSocEstimator{};
            calculation_continuous = true;
            const float soc = estimator.update(0.1f, -2.0f, sample.pack_v) * 100.0f;
            if (!interface.empty() && !can.send(encodeBmsStatusFrame(
                    {soc, 100.0f, sample.pack_v, -2.0f, 25}))) {
                std::cerr << "CAN send failed; diagnostic stopped\n";
                return 3;
            }
            std::cout << "RAW=" << sample.raw << " A0=" << sample.adc_v
                      << "V PACK=" << sample.pack_v << "V SOC=" << soc
                      << (interface.empty() ? " ADC_ONLY" : " TX=0x100") << std::endl;
        } else {
            std::cout << "ADC preparing/recovering: waiting for 3 consecutive new valid samples\n";
        }
        std::this_thread::sleep_until(start + std::chrono::milliseconds(100));
    }
    return 0;
}
