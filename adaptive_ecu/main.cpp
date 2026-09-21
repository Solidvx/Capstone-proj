#include "can_cdd.h"
#include "can_publisher.h"
#include "ekf_soc_estimator.h"
#include "failsafe_sm.h"
#include "secoc_module.h"
#include "sensor_simulator.h"
#include "soh_estimator.h"
#include "watchdog_manager.h"

#include <atomic>
#include <chrono>
#include <csignal>
#include <iostream>
#include <string>
#include <thread>

namespace {
std::atomic<bool> running{true};

void handleSignal(int) {
    running = false;
}

SensorSimulator::Mode parseSensorMode(const std::string& mode) {
    if (mode == "potentiometer") {
        return SensorSimulator::Mode::POTENTIOMETER;
    }
    if (mode == "profile_csv") {
        return SensorSimulator::Mode::PROFILE_CSV;
    }
    if (mode == "random_walk") {
        return SensorSimulator::Mode::RANDOM_WALK;
    }
    if (mode == "ads1115") {
        return SensorSimulator::Mode::ADS1115_HARDWARE;
    }
    return SensorSimulator::Mode::CONSTANT;
}
}

int main(int argc, char** argv) {
    std::string interface_name = "vcan0";
    std::string sensor_mode = "constant";
    std::string profile_path = "adaptive_ecu/data/battery_profile.csv";
    std::string key_path = "/etc/secoc/key.bin";
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
        }
    }

    std::signal(SIGINT, handleSignal);
    std::signal(SIGTERM, handleSignal);

    SocketCanCdd driver;
    if (!driver.open(interface_name)) {
        std::cerr << "CAN open failed: " << interface_name << '\n';
        return 1;
    }

    SensorSimulator sensor(parseSensorMode(sensor_mode), profile_path);
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

    while (running) {
        const auto cycle_start = std::chrono::steady_clock::now();
        watchdog.kick();

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

    watchdog.stop();
    driver.close();
    std::cout << "adaptive_ecu stopped\n";
    return 0;
}
