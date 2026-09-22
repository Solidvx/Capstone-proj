#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QUrl>
#include <QTimer>

#include <iostream>
#include <string>

#include "dashboard_view_model.h"
#include "socketcan_receiver.h"
#include "vehicle_data_service.h"

namespace {

struct Arguments {
    std::string interface_name = "vcan0";
    std::string key_path;
};

Arguments parseArguments(int argc, char** argv) {
    Arguments result;
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--interface" && index + 1 < argc) {
            result.interface_name = argv[++index];
        } else if (argument == "--secoc-key" && index + 1 < argc) {
            result.key_path = argv[++index];
        }
    }
    return result;
}

}  // namespace

int main(int argc, char* argv[]) {
    QGuiApplication application(argc, argv);
    const auto arguments = parseArguments(argc, argv);

    ivi::VehicleDataService service;
    if (arguments.key_path.empty() || !service.loadSecOcKey(arguments.key_path)) {
        std::cerr << "A valid 32-byte SecOC key is required via --secoc-key\n";
        return 2;
    }

    DashboardViewModel view_model;
    const auto observer_id = service.registerObserver(
        [&view_model](const ivi::VehicleSnapshot& snapshot) { view_model.updateSnapshot(snapshot); });

    ivi::SocketCanReceiver receiver;
    receiver.setCallback([&service](std::uint32_t can_id, const ivi::CanPayload& payload) {
        service.processFrame(can_id, payload);
    });
    if (!receiver.open(arguments.interface_name) || !receiver.start()) {
        std::cerr << "SocketCAN startup failed: " << receiver.lastError() << '\n';
        return 3;
    }

    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty("vehicleModel", &view_model);
    engine.load(QUrl(QStringLiteral(
        "qrc:/qt/qml/IviDashboard/ui_qml/qml/Main.qml")));
    if (engine.rootObjects().isEmpty()) {
        receiver.stop();
        return 4;
    }

    QTimer service_timer;
    QObject::connect(&service_timer, &QTimer::timeout, &application,
                     [&service]() { service.pollTimeouts(); });
    service_timer.start(10);
    const int result = application.exec();
    service_timer.stop();
    receiver.stop();
    service.unregisterObserver(observer_id);
    return result;
}
