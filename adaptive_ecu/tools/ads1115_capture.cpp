// EXQ-10: preserve raw ADC results, including out-of-range values. No CAN output.
#include "ads1115_registers.h"
#include "linux_i2c_transport.h"

#include <chrono>
#include <csignal>
#include <iostream>
#include <string>
#include <thread>

namespace {
volatile std::sig_atomic_t running = 1;
void stop(int) { running = 0; }
using Clock = std::chrono::steady_clock;
}

int main(int argc, char** argv) {
    std::string device = "/dev/i2c-1";
    int count = 1000;
    try {
        for (int i = 1; i < argc; ++i) {
            const std::string arg = argv[i];
            if (arg == "--help") {
                std::cout << "ads1115_capture [--i2c-device /dev/i2c-1] [--count 1000]\n"
                             "Stop other ADC users first. CSV to stdout, no CAN.\n";
                return 0;
            }
            if (i + 1 >= argc) return 2;
            if (arg == "--i2c-device") device = argv[++i];
            else if (arg == "--count") {
                const std::string value = argv[++i];
                std::size_t consumed = 0;
                count = std::stoi(value, &consumed);
                if (consumed != value.size()) return 2;
            } else return 2;
        }
    } catch (const std::exception&) { return 2; }
    if (count < 1 || count > 10000) return 2;
    LinuxI2cTransport bus(device);
    if (!bus.ready()) {
        std::cerr << "I2C open/setup failed\n";
        return 2;
    }
    std::signal(SIGINT, stop);
    std::signal(SIGTERM, stop);
    Ads1115Registers adc(bus);
    const auto origin = Clock::now();
    unsigned errors = 0;
    std::cout << "sample,t_s,status,raw,conversion_ms\n";
    for (int i = 0; i < count; ++i) {
        if (!running) return 130;
        const auto start = Clock::now();
        const char* status = "START_ERROR";
        std::int16_t raw = 0;
        bool complete = false;
        if (adc.start()) {
            Ads1115Read state = Ads1115Read::Waiting;
            while (running && Clock::now() - start < std::chrono::milliseconds(20)) {
                state = adc.poll(raw);
                if (state != Ads1115Read::Waiting) break;
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
            }
            complete = state == Ads1115Read::Complete;
            status = complete ? "OK" : state == Ads1115Read::Error ? "READ_ERROR" : "TIMEOUT";
            if (complete && Clock::now() - start >= std::chrono::milliseconds(20)) status = "LATE";
            adc.abandon();
        }
        if (std::string(status) != "OK") ++errors;
        std::cout << i << ',' << std::chrono::duration<double>(start - origin).count() << ',' << status << ',';
        if (complete) std::cout << raw;
        std::cout << ',' << std::chrono::duration<double, std::milli>(Clock::now() - start).count() << std::endl;
        std::this_thread::sleep_until(start + std::chrono::milliseconds(100));
    }
    return errors ? 1 : 0;
}
