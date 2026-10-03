#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQuickWindow>
#include <QTimer>
#include <QUrl>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>

#include <chrono>
#include <deque>
#include <fstream>
#include <iostream>
#include <map>
#include <mutex>
#include <string>

#include "dashboard_view_model.h"
#include "socketcan_receiver.h"
#include "vehicle_data_service.h"
#ifdef IVI_EXPERIMENT_BUILD
#include "unprotected_test_receiver.h"
#endif

namespace {

struct Arguments {
    std::string interface_name = "vcan0";
    std::string key_path;
    std::string demo_scenario;
    std::string demo_screenshot;
    int demo_exit_ms = 0;
    std::string latency_csv;
    std::size_t latency_samples = 0;
    bool experiment_secoc_off = false;
    bool isolated_bus = false;
    std::string observation_jsonl;
    std::string ready_file;
    std::string run_id = "development";
};

Arguments parseArguments(int argc, char** argv) {
    Arguments result;
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--interface" && index + 1 < argc) {
            result.interface_name = argv[++index];
        } else if (argument == "--secoc-key" && index + 1 < argc) {
            result.key_path = argv[++index];
        } else if (argument == "--demo" && index + 1 < argc) {
            result.demo_scenario = argv[++index];
        } else if (argument == "--demo-screenshot" && index + 1 < argc) {
            result.demo_screenshot = argv[++index];
        } else if (argument == "--demo-exit-ms" && index + 1 < argc) {
            result.demo_exit_ms = std::stoi(argv[++index]);
        } else if (argument == "--latency-csv" && index + 1 < argc) {
            result.latency_csv = argv[++index];
        } else if (argument == "--latency-samples" && index + 1 < argc) {
            result.latency_samples = static_cast<std::size_t>(std::stoul(argv[++index]));
        } else if (argument == "--experiment-secoc-off") {
            result.experiment_secoc_off = true;
        } else if (argument == "--confirm-isolated-test-bus") {
            result.isolated_bus = true;
        } else if (argument == "--observation-jsonl" && index + 1 < argc) {
            result.observation_jsonl = argv[++index];
        } else if (argument == "--ready-file" && index + 1 < argc) {
            result.ready_file = argv[++index];
        } else if (argument == "--run-id" && index + 1 < argc) {
            result.run_id = argv[++index];
        }
    }
    return result;
}

struct PendingMeasurement {
    qulonglong sequence;
    qulonglong t1_ns;
    qulonglong t2_ns;
    qulonglong t3_ns;
};

class LatencyRecorder {
public:
    LatencyRecorder(const std::string& path, std::size_t expected_samples)
        : expected_samples_(expected_samples) {
        if (!path.empty()) {
            output_.open(path, std::ios::out | std::ios::trunc);
            if (output_) {
                output_ << "run_id,boot_id,sample_id,stage,timestamp_ns\n";
            }
        }
    }

    bool enabled() const { return output_.is_open(); }

    void queue(qulonglong sequence, qulonglong t1, qulonglong t2, qulonglong t3) {
        if (enabled()) {
            pending_.push_back({sequence, t1, t2, t3});
        }
    }

    bool framePresented() {
        if (pending_.empty()) {
            return false;
        }
        const auto t4 = static_cast<qulonglong>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(
                std::chrono::steady_clock::now().time_since_epoch())
                .count());
        while (!pending_.empty()) {
            const auto sample = pending_.front();
            pending_.pop_front();
            write(sample.sequence, "T1", sample.t1_ns);
            write(sample.sequence, "T2", sample.t2_ns);
            write(sample.sequence, "T3", sample.t3_ns);
            write(sample.sequence, "T4", t4);
            ++completed_samples_;
        }
        output_.flush();
        return expected_samples_ > 0 && completed_samples_ >= expected_samples_;
    }

private:
    void write(qulonglong sequence, const char* stage, qulonglong timestamp) {
        output_ << "ivi-p4,local," << sequence << ',' << stage << ',' << timestamp << '\n';
    }

    std::ofstream output_;
    std::deque<PendingMeasurement> pending_;
    std::size_t expected_samples_ = 0;
    std::size_t completed_samples_ = 0;
};

ivi::VehicleSnapshot demoSnapshot(const std::string& scenario) {
    ivi::VehicleSnapshot snapshot;
    snapshot.last_message = "P3 demo scenario: " + scenario;
    if (scenario == "waiting") {
        return snapshot;
    }
    snapshot.vehicle.valid = true;
    snapshot.vehicle.stale = false;
    snapshot.vehicle.soc_percent = 74.5;
    snapshot.vehicle.soh_percent = 96.0;
    snapshot.vehicle.voltage_v = 41.8;
    snapshot.vehicle.current_a = -2.4;
    snapshot.vehicle.temperature_c = 31.0;
    snapshot.last_secoc_verified = true;
    if (scenario == "stale") {
        snapshot.vehicle.stale = true;
        snapshot.last_good_age_ms = 850;
    } else if (scenario == "sensor-error") {
        snapshot.vehicle.sensor_state = 4;
        snapshot.last_good_age_ms = 1200;
    } else if (scenario == "warning") {
        snapshot.vehicle.fail_safe_state = 1;
        snapshot.vehicle.fail_safe_reason = 7;
    } else if (scenario == "critical") {
        snapshot.vehicle.fail_safe_state = 2;
        snapshot.vehicle.fail_safe_reason = 2;
    } else if (scenario == "shutdown") {
        snapshot.vehicle.fail_safe_state = 3;
        snapshot.vehicle.fail_safe_reason = 4;
    } else if (scenario == "ids") {
        snapshot.security_alert = ivi::SecurityAlert{4, 1.5, 0x100, 1};
        snapshot.security_alert_sequence = 1;
    }
    return snapshot;
}

}  // namespace

int main(int argc, char* argv[]) {
    QGuiApplication application(argc, argv);
    const auto arguments = parseArguments(argc, argv);

#ifndef IVI_EXPERIMENT_BUILD
    if (arguments.experiment_secoc_off) {
        std::cerr << "Unprotected mode requires the separately built ivi_dashboard_experiment\n";
        return 2;
    }
#endif
    if (arguments.experiment_secoc_off && !arguments.isolated_bus) {
        std::cerr << "Experiment SecOC OFF requires --confirm-isolated-test-bus\n";
        return 2;
    }
    QFile observations(QString::fromStdString(arguments.observation_jsonl));
    const bool observation_opened = arguments.observation_jsonl.empty() ||
        (arguments.observation_jsonl == "-" ? observations.open(stdout, QIODevice::WriteOnly) :
         observations.open(QIODevice::WriteOnly | QIODevice::NewOnly));
    if (!observation_opened) {
        std::cerr << "Observation path must be a new writable file\n";
        return 2;
    }

    ivi::VehicleDataService service;
    const bool demo_mode = !arguments.demo_scenario.empty();
    if (!demo_mode && !arguments.experiment_secoc_off &&
        (arguments.key_path.empty() || !service.loadSecOcKey(arguments.key_path))) {
        std::cerr << "A valid 32-byte SecOC key is required via --secoc-key\n";
        return 2;
    }

    DashboardViewModel view_model;
    const auto observer_id = service.registerObserver(
        [&view_model](const ivi::VehicleSnapshot& snapshot) { view_model.updateSnapshot(snapshot); });
    QObject::connect(
        &view_model,
        &DashboardViewModel::securityAlertAcknowledgementRequested,
        [&service](qulonglong sequence) {
            service.acknowledgeSecurityAlert(static_cast<std::uint64_t>(sequence));
        });

    ivi::SocketCanReceiver receiver;
#ifdef IVI_EXPERIMENT_BUILD
    UnprotectedTestReceiver unprotected_receiver;
#endif
    std::map<std::uint32_t, ivi::CanPayload> observation_pending;
    std::mutex observation_mutex;
    auto record_timeouts = [&](std::uint32_t before, const ivi::VehicleSnapshot& snapshot,
                               ivi::SocketCanReceiver::Clock::time_point at) {
        if (!observations.isOpen() || snapshot.pending_timeout_count <= before) return;
        auto remaining = snapshot.pending_timeout_count - before;
        for (auto it = snapshot.logs.rbegin(); it != snapshot.logs.rend() && remaining; ++it) {
            if (it->find("reason=AUTH_TIMEOUT") == std::string::npos) continue;
            --remaining;
            const auto id = it->find("channel=BMS") != std::string::npos ?
                ivi::kCanIdBmsStatus : ivi::kCanIdBmsFailSafe;
            const auto pending = observation_pending.find(id);
            if (pending == observation_pending.end()) continue;
            const auto data = QString::fromLatin1(QByteArray(
                reinterpret_cast<const char*>(pending->second.data()), 8).toHex());
            const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(at.time_since_epoch()).count();
            QJsonObject row{{"result", "TIMEOUT"}, {"run_id", QString::fromStdString(arguments.run_id)},
                {"can_id", static_cast<int>(id)}, {"data", data}, {"source_data", data},
                {"timestamp_ns", QString::number(ns)},
                {"process_result", static_cast<int>(ivi::ProcessResult::kRejected)},
                {"secoc_on", true}, {"soc", snapshot.vehicle.soc_percent},
                {"message", QString::fromStdString(*it)}};
            observations.write(QJsonDocument(row).toJson(QJsonDocument::Compact) + '\n');
            observations.flush();
            observation_pending.erase(pending);
        }
    };
    receiver.setCallback(
        [&](std::uint32_t can_id,
                   const ivi::CanPayload& payload,
                   ivi::SocketCanReceiver::Clock::time_point received_at) {
            std::lock_guard<std::mutex> observation_lock(observation_mutex);
            const auto timeout_before = service.latest().pending_timeout_count;
            auto result = ivi::ProcessResult::kIgnored;
            ivi::VehicleSnapshot snapshot;
#ifdef IVI_EXPERIMENT_BUILD
            if (arguments.experiment_secoc_off) {
                result = unprotected_receiver.process(can_id, payload);
                snapshot = unprotected_receiver.latest();
                if (result == ivi::ProcessResult::kPublished) view_model.updateSnapshot(snapshot);
            } else
#endif
            {
                result = service.processFrame(can_id, payload, received_at);
                snapshot = service.latest();
            }
            if (observations.isOpen()) {
                record_timeouts(timeout_before, snapshot, received_at);
                const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(received_at.time_since_epoch()).count();
                QJsonObject row{{"result", "FRAME"}, {"run_id", QString::fromStdString(arguments.run_id)},
                    {"can_id", static_cast<int>(can_id)},
                    {"data", QString::fromLatin1(QByteArray(reinterpret_cast<const char*>(payload.data()), 8).toHex())},
                    {"timestamp_ns", QString::number(ns)},
                    {"process_result", static_cast<int>(result)},
                    {"secoc_on", !arguments.experiment_secoc_off},
                    {"soc", snapshot.vehicle.soc_percent},
                    {"message", QString::fromStdString(snapshot.last_message)}};
                if ((can_id == ivi::kCanIdBmsStatus || can_id == ivi::kCanIdBmsFailSafe) &&
                    (result == ivi::ProcessResult::kPendingAuthentication || result == ivi::ProcessResult::kPublished))
                    observation_pending[can_id] = payload;
                const auto original_id = can_id == ivi::kCanIdBmsSecOc ? ivi::kCanIdBmsStatus :
                    can_id == ivi::kCanIdFailSafeSecOc ? ivi::kCanIdBmsFailSafe : can_id;
                if (observation_pending.count(original_id)) {
                    const auto& original = observation_pending.at(original_id);
                    row["source_data"] = QString::fromLatin1(QByteArray(reinterpret_cast<const char*>(original.data()), 8).toHex());
                }
                observations.write(QJsonDocument(row).toJson(QJsonDocument::Compact) + '\n');
                observations.flush();
                if ((can_id == ivi::kCanIdBmsSecOc || can_id == ivi::kCanIdFailSafeSecOc) && result == ivi::ProcessResult::kPublished)
                    observation_pending.erase(original_id);
            }
        });
    if (!demo_mode &&
        (!receiver.open(arguments.interface_name) || !receiver.start())) {
        std::cerr << "SocketCAN startup failed: " << receiver.lastError() << '\n';
        return 3;
    }

    QTimer stale_timer;
    QTimer pending_timer;
    if (demo_mode) {
        if (arguments.demo_scenario == "ids") {
            const ivi::CanPayload ids{0x04, 0x96, 0x01, 0x00, 0, 0, 0, 1};
            service.processFrame(ivi::kCanIdIdsAlert, ids);
        } else {
            view_model.updateSnapshot(demoSnapshot(arguments.demo_scenario));
        }
    } else if (!arguments.experiment_secoc_off) {
        QObject::connect(&stale_timer, &QTimer::timeout, [&service]() {
            service.refreshTime();
        });
        stale_timer.start(50);
        // The 100ms pending deadline needs a finer tick than the 50ms stale refresh.
        QObject::connect(&pending_timer, &QTimer::timeout, [&]() {
            std::lock_guard<std::mutex> observation_lock(observation_mutex);
            const auto before = service.latest().pending_timeout_count;
            const auto now = ivi::SocketCanReceiver::Clock::now();
            service.pollTimeouts(now);
            record_timeouts(before, service.latest(), now);
        });
        pending_timer.start(10);
    }

    LatencyRecorder latency_recorder(arguments.latency_csv, arguments.latency_samples);
    if (!arguments.latency_csv.empty() && !latency_recorder.enabled()) {
        std::cerr << "Failed to open latency CSV: " << arguments.latency_csv << '\n';
        receiver.stop();
        return 5;
    }

    QQmlApplicationEngine engine;
    engine.setInitialProperties({{"vehicleModel", QVariant::fromValue(&view_model)}});
    engine.load(QUrl(QStringLiteral(
        "qrc:/qt/qml/IviDashboard/ui_qml/qml/Main.qml")));
    if (engine.rootObjects().isEmpty()) {
        receiver.stop();
        return 4;
    }
    if (!demo_mode) {
        const QJsonObject ready{{"result", "READY"}, {"run_id", QString::fromStdString(arguments.run_id)},
                               {"secoc_on", !arguments.experiment_secoc_off}};
        if (!arguments.ready_file.empty()) {
            QFile ready_file(QString::fromStdString(arguments.ready_file));
            if (!ready_file.open(QIODevice::WriteOnly | QIODevice::NewOnly)) {
                receiver.stop();
                std::cerr << "Ready file must be new\n";
                return 2;
            }
            ready_file.write(QJsonDocument(ready).toJson(QJsonDocument::Compact));
        }
        std::cout << QJsonDocument(ready).toJson(QJsonDocument::Compact).constData() << std::endl;
    }

    if (latency_recorder.enabled()) {
        auto* window = qobject_cast<QQuickWindow*>(engine.rootObjects().constFirst());
        if (window == nullptr) {
            std::cerr << "Latency measurement requires a QQuickWindow\n";
            receiver.stop();
            return 5;
        }
        QObject::connect(&view_model,
                         &DashboardViewModel::measurementReady,
                         window,
                         [&latency_recorder, window](qulonglong sequence,
                                                     qulonglong t1,
                                                     qulonglong t2,
                                                     qulonglong t3) {
                             latency_recorder.queue(sequence, t1, t2, t3);
                             window->update();
        });
        QObject::connect(window, &QQuickWindow::frameSwapped, window, [&]() {
            if (latency_recorder.framePresented()) {
                QTimer::singleShot(0, &application, &QCoreApplication::quit);
            }
        });
    }

    if (demo_mode && !arguments.demo_screenshot.empty()) {
        QTimer::singleShot(250, [&application, &engine, arguments]() {
            auto* window = qobject_cast<QQuickWindow*>(engine.rootObjects().constFirst());
            if (window == nullptr ||
                !window->grabWindow().save(
                    QString::fromStdString(arguments.demo_screenshot))) {
                std::cerr << "Failed to save demo screenshot\n";
                application.exit(5);
            } else if (arguments.demo_exit_ms <= 0) {
                application.quit();
            }
        });
    }

    if (arguments.demo_exit_ms > 0) {
        QTimer::singleShot(arguments.demo_exit_ms, &application, &QCoreApplication::quit);
    }

    const int result = application.exec();
    pending_timer.stop();
    stale_timer.stop();
    receiver.stop();
    service.unregisterObserver(observer_id);
    return result;
}
