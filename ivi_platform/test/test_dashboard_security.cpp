#include "dashboard_view_model.h"
#include "test_support.h"
#include <QColor>
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QVariant>
#include <QUrl>
#include <QQuickItem>
#include <QQuickWindow>
#include <QSettings>
#include <QTemporaryDir>
#include <QEventLoop>
#include <QTimer>

void run() {
    DashboardViewModel model;
    QQmlApplicationEngine engine;
    engine.setInitialProperties({{"vehicleModel", QVariant::fromValue(&model)}});
    engine.load(QUrl::fromLocalFile(QStringLiteral(IVI_QML_FILE)));
    EXPECT_FALSE(engine.rootObjects().isEmpty());
    auto* root=engine.rootObjects().front();
    auto flush=[] { QEventLoop loop; QTimer::singleShot(40,&loop,&QEventLoop::quit); loop.exec(); };
    auto* canvas=root->findChild<QQuickItem*>("appCanvas");
    auto* tabs=root->findChild<QQuickItem*>("bottomTabs");
    auto* recent=root->findChild<QQuickItem*>("recentEventsCard");
    auto* summary=root->findChild<QQuickItem*>("batterySummaryCard");
    EXPECT_TRUE(canvas && tabs && recent && summary);
    for (auto size : {QSize(800,480),QSize(1024,600),QSize(480,800)}) {
        root->setProperty("width",size.width());root->setProperty("height",size.height());flush();
        for(auto* item : {tabs,recent,summary}) {
            auto rect=item->mapRectToItem(canvas,item->boundingRect());
            EXPECT_TRUE(rect.top()>=0 && rect.left()>=0);
            EXPECT_TRUE(rect.bottom()<=480 && rect.right()<=800);
            EXPECT_TRUE(item->height()>0 && item->width()>0);
        }
        EXPECT_TRUE(summary->height()>=170);
        EXPECT_EQ(tabs->height(),44.0);
        EXPECT_TRUE(recent->mapRectToItem(canvas,recent->boundingRect()).bottom() <
                    tabs->mapRectToItem(canvas,tabs->boundingRect()).top());
    }
    auto* landscapeScene=root->findChild<QObject*>("landscapeScene");
    EXPECT_TRUE(landscapeScene != nullptr);
    root->setProperty("width",720);
    root->setProperty("height",1280);
    QGuiApplication::processEvents();
    EXPECT_EQ(landscapeScene->property("width").toInt(),1280);
    EXPECT_EQ(landscapeScene->property("height").toInt(),720);
    EXPECT_EQ(landscapeScene->property("rotation").toInt(),-90);
    auto* socGauge=root->findChild<QObject*>("socGauge");
    auto* socGaugeArc=root->findChild<QObject*>("socGaugeArc");
    EXPECT_TRUE(socGauge != nullptr);
    EXPECT_TRUE(socGaugeArc != nullptr);
    EXPECT_EQ(socGaugeArc->property("width").toInt(),
              socGaugeArc->property("height").toInt());
    EXPECT_FALSE(socGauge->property("available").toBool());
    auto* indicator=root->findChild<QObject*>("authenticationErrorIndicator");
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
    model.dismissPopup();
    root->setProperty("currentPage",1);
    QGuiApplication::processEvents();
    EXPECT_TRUE(indicator->property("visible").toBool());
    EXPECT_FALSE(model.valid());
    const auto mac=ivi::SecOcVerifier(dummy).computeTruncatedMac(0x100,0,bms);
    ivi::CanPayload good{mac[0],mac[1],mac[2],mac[3],0,0,0,0};
    service.processFrame(0x102,good,now);
    QGuiApplication::processEvents();
    EXPECT_FALSE(model.authenticationError());
    EXPECT_FALSE(indicator->property("visible").toBool());
    root->setProperty("currentPage",0);
    QGuiApplication::processEvents();
    EXPECT_TRUE(model.valid());
    EXPECT_TRUE(socGauge->property("available").toBool());
    EXPECT_EQ(socGauge->property("value").toDouble(),75.0);
    EXPECT_EQ(socGauge->property("gaugeColor").value<QColor>(),QColor("#36d399"));
    auto updated_bms=bms;
    updated_bms[1]=180; // 90% SOH from the unchanged wire layout
    const auto updated_mac=ivi::SecOcVerifier(dummy).computeTruncatedMac(0x100,1,updated_bms);
    service.processFrame(0x100,updated_bms,now+std::chrono::milliseconds{20});
    service.processFrame(0x102,{updated_mac[0],updated_mac[1],updated_mac[2],updated_mac[3],0,0,0,1},
                         now+std::chrono::milliseconds{21});
    flush();
    auto* soh=root->findChild<QObject*>("sohValue");
    EXPECT_TRUE(soh != nullptr);
    EXPECT_EQ(soh->property("text").toString(),QStringLiteral("90.0%"));
    service.refreshTime(now+std::chrono::milliseconds{321});
    QGuiApplication::processEvents();
    EXPECT_TRUE(model.stale());
    model.dismissPopup();
    root->setProperty("width",800);root->setProperty("height",480);flush();
    auto* arc=root->findChild<QQuickItem*>("socGaugeArc");
    auto* label=root->findChild<QQuickItem*>("socGaugeLabel");
    EXPECT_TRUE(label && arc);
    EXPECT_TRUE(label->mapRectToItem(canvas,label->boundingRect()).bottom() <
                arc->mapRectToItem(canvas,arc->boundingRect()).top());
    auto* window=qobject_cast<QQuickWindow*>(root);
    EXPECT_TRUE(window != nullptr);
    for(bool dark : {false,true}) {
        model.setDarkMode(dark);flush();
        EXPECT_EQ(root->property("dark").toBool(),dark);
        EXPECT_TRUE(window->grabWindow().save(dark ? "dashboard-dark.png" : "dashboard-light.png"));
    }
    // A real service IDS event opens a popup; closing never clears source data.
    service.processFrame(0x200,{2,100,1,0,0,0,0,1},now+std::chrono::milliseconds{301});
    flush();
    EXPECT_TRUE(model.popupVisible());
    auto* overlay=root->findChild<QQuickItem*>("alertOverlay");
    EXPECT_TRUE(overlay != nullptr && overlay->isVisible());
    EXPECT_TRUE(window->grabWindow().save("dashboard-alert.png"));
    auto* dismiss=root->findChild<QObject*>("dismissAlert");
    EXPECT_TRUE(dismiss != nullptr);
    EXPECT_TRUE(QMetaObject::invokeMethod(dismiss,"clicked"));flush();
    EXPECT_FALSE(overlay->isVisible());
    EXPECT_TRUE(model.securityTitle().contains(QStringLiteral("Replay")));
    // Long details scroll inside their page; tabs remain outside the viewport.
    auto verbose=service.latest();
    for(int i=0;i<64;++i) verbose.logs.push_back(std::string(180,'x'));
    model.updateSnapshot(verbose);model.dismissPopup();
    root->setProperty("currentPage",1);flush();
    auto* scroll=root->findChild<QQuickItem*>("securityScroll");
    EXPECT_TRUE(scroll != nullptr);
    EXPECT_TRUE(scroll->property("contentHeight").toDouble()>scroll->height());
    auto* scroller=qvariant_cast<QObject*>(scroll->property("contentItem"));
    EXPECT_TRUE(scroller != nullptr);
    scroller->setProperty("contentY",100);flush();
    EXPECT_TRUE(scroller->property("contentY").toDouble()>0);
    EXPECT_TRUE(tabs->isVisible());
    root->setProperty("currentPage",0);flush();
    // Critical safety persists after modal close.
    ivi::VehicleSnapshot critical;
    critical.vehicle.valid=true;critical.vehicle.fail_safe_state=2;critical.vehicle.fail_safe_reason=2;
    model.updateSnapshot(critical);flush();
    model.dismissPopup();flush();
    EXPECT_TRUE(model.failSafeOverlayActive());
    EXPECT_TRUE(model.statusTitle().contains(QStringLiteral("위험")));
    for(int i=0;i<110;++i) {
        critical.vehicle.stale=!critical.vehicle.stale;
        model.updateSnapshot(critical);model.dismissPopup();
    }
    root->setProperty("currentPage",2);flush();
    auto* history=root->findChild<QQuickItem*>("historyList");
    EXPECT_TRUE(history != nullptr);
    EXPECT_TRUE(history->property("contentHeight").toDouble()>history->height());
    history->setProperty("contentY",100);flush();
    EXPECT_TRUE(history->property("contentY").toDouble()>0);
    EXPECT_TRUE(tabs->isVisible());
    EXPECT_TRUE(socGauge->property("stale").toBool());
    // The same product QML displays physical channels independently of SOC/SOH.
    ivi::VehicleSnapshot physical;physical.physical_measurement=capstone::session_v2::PhysicalMeasurement{};
    physical.physical_measurement->sequence=3;physical.vehicle.valid=true;physical.vehicle.stale=false;
    physical.vehicle.voltage_v=3.8531;physical.vehicle.current_a=-.3711;physical.vehicle.temperature_c=20.125;
    physical.physical_valid={true,true,true,false,false};
    model.updateSnapshot(physical);model.dismissPopup();root->setProperty("currentPage",0);flush();
    EXPECT_FALSE(socGauge->property("available").toBool());EXPECT_EQ(soh->property("text").toString(),QStringLiteral("--"));
    auto* voltage=root->findChild<QObject*>("voltageMetric");auto* current=root->findChild<QObject*>("currentMetric");
    auto* temperature=root->findChild<QObject*>("temperatureMetric");
    EXPECT_TRUE(voltage&&current&&temperature);
    EXPECT_EQ(voltage->property("title").toString(),QStringLiteral("셀 전압"));
    EXPECT_EQ(voltage->property("value").toString(),QStringLiteral("3.853 V"));
    EXPECT_EQ(current->property("value").toString(),QStringLiteral("-0.371 A"));
    EXPECT_EQ(temperature->property("value").toString(),QStringLiteral("20.1 °C"));
    EXPECT_TRUE(window->grabWindow().save("dashboard-physical.png"));
    physical.physical_valid[2]=false;model.updateSnapshot(physical);flush();
    EXPECT_EQ(temperature->property("value").toString(),QStringLiteral("--"));
    EXPECT_EQ(voltage->property("value").toString(),QStringLiteral("3.853 V"));
    EXPECT_TRUE(model.popupVisible());EXPECT_TRUE(window->grabWindow().save("dashboard-physical-partial.png"));
    physical.physical_valid[2]=true;model.updateSnapshot(physical);flush();EXPECT_FALSE(model.popupVisible());
}
int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);
    QTemporaryDir settings;
    QSettings::setDefaultFormat(QSettings::IniFormat);
    QSettings::setPath(QSettings::IniFormat,QSettings::UserScope,settings.path());
    return runTestProgram("Qt authentication warning and recovery",run);
}
