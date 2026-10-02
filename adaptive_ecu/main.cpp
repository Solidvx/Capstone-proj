#include "ads1115_acquirer.h"
#include "can_cdd.h"
#include "can_publisher.h"
#include "ekf_soc_estimator.h"
#include "failsafe_sm.h"
#include "hardware_sample_feed.h"
#include "linux_i2c_transport.h"
#include "secoc_module.h"
#include "sensor_simulator.h"
#include "soh_estimator.h"
#include "watchdog_manager.h"

#include <atomic>
#include <chrono>
#include <csignal>
#include <iostream>
#include <memory>
#include <string>
#include <thread>

namespace {
std::atomic<bool> running{true};

void handleSignal(int) {
    running = false;
}

std::uint64_t monotonicMs() {
    return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}

const char* qualityName(SensorQuality quality) {
    switch (quality) {
    case SensorQuality::Preparing: return "PREPARING";
    case SensorQuality::Valid: return "VALID";
    case SensorQuality::ErrorWithoutValue: return "ERROR";
    case SensorQuality::ErrorWithValue: return "ERROR_WITH_LAST_VALUE";
    case SensorQuality::RecoveringWithoutValue: return "RECOVERING";
    case SensorQuality::RecoveringWithValue: return "RECOVERING_WITH_LAST_VALUE";
    }
    return "UNKNOWN";
}
}

int main(int argc, char** argv) {
    std::string interface_name = "vcan0";
    std::string sensor_mode = "constant";
    std::string profile_path = "adaptive_ecu/data/battery_profile.csv";
    std::string key_path = "/etc/secoc/key.bin";
    std::string i2c_device = "/dev/i2c-1";
    bool secoc_enabled = false;

    for (int i = 1; i + 1 < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--interface") {
            interface_name = argv[++i];
        } else if (arg == "--sensor-mode") {
            sensor_mode = argv[++i];
        } else if (arg == "--profile") {
            profile_path = argv[++i];
        } else if (arg == "--secoc") {
            secoc_enabled = (std::string(argv[++i]) == "on");
        } else if (arg == "--key") {
            key_path = argv[++i];
        } else if (arg == "--i2c-device") {
            i2c_device = argv[++i];
        }
    }

    const auto mode = SensorSimulator::parseMode(sensor_mode);
    if (!mode) {
        std::cerr << "Unsupported sensor mode: " << sensor_mode
                  << " (constant|profile_csv|random_walk|ads1115)\n";
        return 2;
    }

    std::signal(SIGINT, handleSignal);
    std::signal(SIGTERM, handleSignal);

    SocketCanCdd driver;
    if (!driver.open(interface_name)) {
        std::cerr << "CAN open failed: " << interface_name << '\n';
        return 1;
    }

    // ADS1115 mode reads the real ADC on its own worker; never fall back to
    // a simulated mode when the device is unavailable.
    std::unique_ptr<LinuxI2cTransport> i2c;
    std::unique_ptr<Ads1115AcquisitionWorker> adc_worker;
    HardwareSampleFeed adc_feed;
    if (*mode == SensorSimulator::Mode::ADS1115_HARDWARE) {
        i2c = std::make_unique<LinuxI2cTransport>(i2c_device);
        if (!i2c->ready()) {
            std::cerr << "I2C open/setup failed: " << i2c_device << " (address 0x48)\n";
            return 2;
        }
        adc_worker = std::make_unique<Ads1115AcquisitionWorker>(*i2c, monotonicMs);
    }

    SensorSimulator sensor(*mode, profile_path);
    EkfSocEstimator soc_estimator;
    SohEstimator soh_estimator;
    FailSafeStateMachine failsafe;
    SecOcModule secoc;

    if (secoc_enabled && !secoc.loadKey(key_path)) {
        std::cerr << "SecOC key load failed: " << key_path << '\n';
        return 1;
    }

    failsafe.setEventCallback([&](const FailSafeEvent& event) {
        const auto event_frame = encodeFailSafeFrame(event);
        driver.send(event_frame);
        if (secoc_enabled) {
            driver.send(secoc.sign(0x103, 0x101, event_frame.data));
        }
        std::cout << "Fail-safe transition: " << static_cast<int>(event.prev_state)
                  << " -> " << static_cast<int>(event.new_state)
                  << " reason=0x" << std::hex << static_cast<int>(event.reason)
                  << std::dec << '\n';
    });

    WatchdogManager watchdog(1000, 3000);
    watchdog.start([](std::uint32_t count) {
        std::cerr << "Watchdog timeout count=" << count << '\n';
    });

    std::cout << "adaptive_ecu on " << interface_name
              << " sensor=" << sensor_mode
              << " secoc=" << (secoc_enabled ? "on" : "off") << '\n';
    if (adc_worker) {
        std::cout << "ADS1115: A0 real -> pack 30..42V virtual; current "
                  << SensorSimulator::kHardwareCurrentA << "A and temperature "
                  << static_cast<int>(SensorSimulator::kHardwareTemperatureC)
                  << "C virtual. BMS TX paused until 3 new valid conversions.\n";
        adc_worker->start();
    }

    auto reported_quality = adc_feed.quality();
    while (running) {
        const auto cycle_start = std::chrono::steady_clock::now();
        watchdog.kick();

        if (adc_worker) {
            const auto pack_voltage = adc_feed.cycle(adc_worker->snapshot(), monotonicMs());
            if (adc_feed.quality() != reported_quality) {
                reported_quality = adc_feed.quality();
                std::cout << "ADS1115 quality: " << qualityName(reported_quality)
                          << (pack_voltage ? "" : " (BMS TX paused)") << '\n';
            }
            if (!pack_voltage) {
                // D1: no estimate, Fail-safe evaluation or frame from an invalid or
                // stale input. D3: the estimator resumes from its last state.
                std::this_thread::sleep_until(cycle_start + std::chrono::milliseconds(100));
                continue;
            }
            sensor.setHardwareVoltage(*pack_voltage);
        }

        const auto sample = sensor.next();
        const float soc_percent =
            soc_estimator.update(0.1f, sample.current_a, sample.voltage_v) * 100.0f;
        const float soh_percent = soh_estimator.soh() * 100.0f;

        failsafe.evaluate(soc_percent, sample.temperature_c);

        const auto status_frame = encodeBmsStatusFrame({
            soc_percent,
            soh_percent,
            sample.voltage_v,
            sample.current_a,
            sample.temperature_c,
        });
        driver.send(status_frame);
        if (secoc_enabled) {
            driver.send(secoc.sign(0x102, 0x100, status_frame.data));
        }

        std::this_thread::sleep_until(cycle_start + std::chrono::milliseconds(100));
    }

    if (adc_worker) adc_worker->stop();
    watchdog.stop();
    driver.close();
    std::cout << "adaptive_ecu stopped\n";
    return 0;
}
