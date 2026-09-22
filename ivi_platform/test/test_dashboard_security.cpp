#include "dashboard_view_model.h"
#include "test_support.h"
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QUrl>

void run() {
    DashboardViewModel model;
    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty("vehicleModel", &model);
    engine.load(QUrl::fromLocalFile(QStringLiteral(IVI_QML_FILE)));
    EXPECT_FALSE(engine.rootObjects().isEmpty());
    auto* indicator=engine.rootObjects().front()->findChild<QObject*>("authenticationErrorIndicator");
    EXPECT_TRUE(indicator != nullptr);
    const ivi::SecOcKey dummy{};
    ivi::VehicleDataService service(dummy);
    service.registerObserver([&](const auto& snapshot) { model.updateSnapshot(snapshot); });
    const ivi::CanPayload bms{150,190,0x10,0x68,0xff,0xec,65,0};
    const auto now=ivi::VehicleDataService::Clock::now();
    service.processFrame(0x100,bms,now);
    ivi::CanPayload bad{};
    for(int i=0;i<10;++i) service.processFrame(0x102,bad,now);
    QGuiApplication::processEvents();
    EXPECT_TRUE(model.authenticationError());
    EXPECT_TRUE(indicator->property("visible").toBool());
    EXPECT_FALSE(model.valid());
    const auto mac=ivi::SecOcVerifier(dummy).computeTruncatedMac(0x100,0,bms);
    ivi::CanPayload good{mac[0],mac[1],mac[2],mac[3],0,0,0,0};
    service.processFrame(0x102,good,now);
    QGuiApplication::processEvents();
    EXPECT_FALSE(model.authenticationError());
    EXPECT_FALSE(indicator->property("visible").toBool());
    EXPECT_TRUE(model.valid());
    service.pollTimeouts(now+std::chrono::milliseconds{300});
    QGuiApplication::processEvents();
    EXPECT_TRUE(model.stale());
}
int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);
    return runTestProgram("Qt authentication warning and recovery",run);
}
