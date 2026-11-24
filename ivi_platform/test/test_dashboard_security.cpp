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
#include <QFontDatabase>
#include <QRawFont>
#include <QFileInfo>
#include <QDir>
#include <QElapsedTimer>
#include <QtTest>

void run() {
    DashboardViewModel model;
    QQmlApplicationEngine engine;
    engine.setInitialProperties({{"vehicleModel", QVariant::fromValue(&model)}});
    engine.load(QUrl::fromLocalFile(QStringLiteral(IVI_QML_FILE)));
    EXPECT_FALSE(engine.rootObjects().isEmpty());
    auto* root=engine.rootObjects().front();
    auto flush=[](int ms=40) { QEventLoop loop; QTimer::singleShot(ms,Qt::PreciseTimer,&loop,&QEventLoop::quit); loop.exec(); };
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
    auto* gaugeValue=root->findChild<QObject*>("socGaugeValue");
    EXPECT_TRUE(gaugeValue != nullptr);
    for(double soc:{0.,97.3,100.}){
        socGauge->setProperty("value",soc);flush();
        EXPECT_EQ(gaugeValue->property("text").toString(),QString::number(soc,'f',1)+"%");
        EXPECT_EQ(gaugeValue->property("lineCount").toInt(),1);
        EXPECT_TRUE(gaugeValue->property("contentWidth").toDouble()<=gaugeValue->property("width").toDouble());
    }
    socGauge->setProperty("value",75.0);
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
    const QPoint dragStart=scroll->mapToScene(QPointF(scroll->width()/2,scroll->height()-45)).toPoint();
    QTest::mousePress(window,Qt::LeftButton,Qt::NoModifier,dragStart);
    for(int dy=20;dy<=180;dy+=20){QTest::mouseMove(window,dragStart-QPoint(0,dy),20);flush(20);}
    QTest::mouseRelease(window,Qt::LeftButton,Qt::NoModifier,dragStart-QPoint(0,180));flush();
    EXPECT_TRUE(scroll->property("contentY").toDouble()>20);
    QMetaObject::invokeMethod(scroll,"cancelFlick");scroll->setProperty("contentY",0);flush();
    auto* touchDevice=QTest::createTouchDevice();
    QTest::touchEvent(window,touchDevice).press(0,dragStart,window).commit();
    for(int dy=20;dy<=180;dy+=20){
        QTest::touchEvent(window,touchDevice).move(0,dragStart-QPoint(0,dy),window).commit();flush(20);
    }
    QTest::touchEvent(window,touchDevice).release(0,dragStart-QPoint(0,180),window).commit();flush();
    EXPECT_TRUE(scroll->property("contentY").toDouble()>20);
    auto* healthHeading=root->findChild<QObject*>("canHealthHeading");
    EXPECT_TRUE(healthHeading != nullptr);
    EXPECT_EQ(healthHeading->property("text").toString(),QStringLiteral("CAN 통신 상태"));
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
    auto* sohHint=root->findChild<QObject*>("sohHint");
    EXPECT_TRUE(sohHint != nullptr);
    EXPECT_EQ(sohHint->property("text").toString(),QStringLiteral("용량 시험 후 표시됩니다"));
    EXPECT_EQ(voltage->property("value").toString(),QStringLiteral("3.853 V"));
    EXPECT_EQ(current->property("value").toString(),QStringLiteral("-0.371 A"));
    EXPECT_EQ(temperature->property("value").toString(),QStringLiteral("20.1 °C"));
    for(auto* metric:{voltage,current,temperature}){
        EXPECT_FALSE(metric->property("inputWaiting").toBool());
        auto* reading=metric->findChild<QObject*>("metricReading");
        EXPECT_TRUE(reading != nullptr);
        const auto font=qvariant_cast<QFont>(reading->property("font"));
        EXPECT_TRUE(font.pixelSize()>=24);
        EXPECT_TRUE(QRawFont::fromFont(font).weight()>=QFont::Bold);
        EXPECT_EQ(reading->property("horizontalAlignment").toInt(),int(Qt::AlignHCenter));
        auto* contents=metric->findChild<QQuickItem*>("metricContents");
        auto* item=qobject_cast<QQuickItem*>(metric);
        EXPECT_TRUE(contents != nullptr);
        EXPECT_TRUE(std::abs(contents->x()+contents->width()/2-item->width()/2)<.5);
        EXPECT_TRUE(std::abs(contents->y()+contents->height()/2-item->height()/2)<.5);
    }
    EXPECT_TRUE(window->grabWindow().save("dashboard-physical.png"));
    physical.physical_valid[2]=false;model.updateSnapshot(physical);flush();
    EXPECT_EQ(temperature->property("value").toString(),QStringLiteral("--"));
    EXPECT_TRUE(temperature->property("inputWaiting").toBool());
    EXPECT_EQ(temperature->property("statusText").toString(),QStringLiteral("센서 입력 대기"));
    auto* waitingReading=temperature->findChild<QObject*>("metricReading");
    EXPECT_EQ(waitingReading->property("text").toString(),QStringLiteral("센서 입력 대기"));
    EXPECT_FALSE(waitingReading->property("truncated").toBool());
    EXPECT_FALSE(voltage->property("inputWaiting").toBool());
    EXPECT_FALSE(current->property("inputWaiting").toBool());
    EXPECT_EQ(voltage->property("value").toString(),QStringLiteral("3.853 V"));
    EXPECT_FALSE(model.popupVisible());flush(2100);
    EXPECT_TRUE(model.popupVisible());EXPECT_TRUE(window->grabWindow().save("dashboard-physical-partial.png"));
    physical.physical_valid[2]=true;model.updateSnapshot(physical);flush();
    EXPECT_TRUE(model.popupVisible()); // a short recovery does not close an unread notice
    model.dismissPopup();
    // Missing inputs stay visible after closing a popup. Zero current and
    // missing SOH capacity are distinct from unavailable sensor channels.
    for(bool dark:{false,true}){
        physical.physical_valid[2]=false;
        model.setDarkMode(dark);model.updateSnapshot(physical);flush();
        EXPECT_TRUE(temperature->property("inputWaiting").toBool());
        EXPECT_FALSE(waitingReading->property("truncated").toBool());
        EXPECT_EQ(temperature->property("color").value<QColor>(),root->property("waitingPanel").value<QColor>());
        EXPECT_TRUE(window->grabWindow().save(dark?"dashboard-sensor-wait-dark.png":"dashboard-sensor-wait-light.png"));
        physical.physical_valid[2]=true;physical.physical_valid[0]=physical.physical_valid[1]=false;
        model.updateSnapshot(physical);flush();
        EXPECT_TRUE(voltage->property("inputWaiting").toBool());
        EXPECT_TRUE(current->property("inputWaiting").toBool());
        EXPECT_FALSE(temperature->property("inputWaiting").toBool());
        for(auto* metric:{voltage,current}){
            auto* reading=metric->findChild<QObject*>("metricReading");
            EXPECT_EQ(reading->property("text").toString(),QStringLiteral("센서 입력 대기"));
            EXPECT_FALSE(reading->property("truncated").toBool());
        }
        EXPECT_TRUE(window->grabWindow().save(dark?"dashboard-electrical-wait-dark.png":"dashboard-electrical-wait-light.png"));
        physical.physical_valid[0]=physical.physical_valid[1]=true;physical.vehicle.current_a=0;
        model.updateSnapshot(physical);flush();
        for(auto* metric:{voltage,current,temperature}){
            EXPECT_FALSE(metric->property("inputWaiting").toBool());
            EXPECT_EQ(metric->property("color").value<QColor>(),root->property("panel").value<QColor>());
            auto* item=qobject_cast<QQuickItem*>(metric);
            const auto bounds=item->mapRectToItem(canvas,item->boundingRect());
            EXPECT_TRUE(bounds.left()>=0 && bounds.right()<=800 && bounds.bottom()<tabs->y());
        }
        EXPECT_EQ(current->property("value").toString(),QStringLiteral("0.000 A"));
        EXPECT_EQ(soh->property("text").toString(),QStringLiteral("--"));
        auto* description=root->findChild<QObject*>("statusDescriptionLabel");
        EXPECT_TRUE(description != nullptr);
        EXPECT_FALSE(description->property("truncated").toBool());
        EXPECT_TRUE(description->property("lineHeight").toDouble()>=1.15);
        EXPECT_TRUE(qvariant_cast<QFont>(description->property("font")).pixelSize()>=14);
        EXPECT_TRUE(QRawFont::fromFont(qvariant_cast<QFont>(description->property("font"))).weight()>=QFont::DemiBold);
        for(const auto* name:{"systemStatusContents","securityStatusContents","recentEventsContents"}){
            auto* contents=root->findChild<QQuickItem*>(name);
            EXPECT_TRUE(contents != nullptr);
            const auto bounds=contents->mapRectToItem(contents->parentItem(),contents->boundingRect());
            EXPECT_TRUE(bounds.left()>=8 && bounds.right()<=contents->parentItem()->width()-8);
            EXPECT_TRUE(bounds.top()>=0 && bounds.bottom()<=contents->parentItem()->height());
            EXPECT_TRUE(std::abs(bounds.center().y()-contents->parentItem()->height()/2)<.5);
        }
        for(auto* item:root->findChildren<QQuickItem*>()){
            if(!item->isVisible()||item->metaObject()->indexOfProperty("lineHeight")<0)continue;
            for(auto* parent=item->parentItem();parent;parent=parent->parentItem())if(parent->clip()){
                const auto bounds=item->mapRectToItem(parent,item->boundingRect());
                EXPECT_TRUE(bounds.top()>=-.5 && bounds.bottom()<=parent->height()+.5);
                break;
            }
        }
        EXPECT_TRUE(window->grabWindow().save(dark?"dashboard-sensor-restored-dark.png":"dashboard-sensor-restored-light.png"));
        physical.physical_valid[2]=false;
    }
    physical.physical_valid[2]=true;physical.vehicle.current_a=-.3711;
    model.updateSnapshot(physical);model.dismissPopup();flush();
    // All four names must still fit in the compact security summary.
    auto compound=physical;compound.session_protocol=true;compound.security_observation_ready=true;
    compound.observed_condition_mask=15;model.updateSnapshot(compound);model.dismissPopup();flush();
    auto* securityTitle=root->findChild<QQuickItem*>("securityTitle");
    EXPECT_TRUE(securityTitle && !securityTitle->property("truncated").toBool());
    auto* securityContents=root->findChild<QQuickItem*>("securityStatusContents");
    EXPECT_TRUE(securityContents->y()>=0 && securityContents->y()+securityContents->height()<=securityContents->parentItem()->height());
    EXPECT_TRUE(window->grabWindow().save("dashboard-four-attacks-bold.png"));
    model.updateSnapshot(physical);model.dismissPopup();flush();
    // On other pages a temporary top notice leaves navigation/history usable.
    auto* toast=root->findChild<QQuickItem*>("notificationToast");
    EXPECT_TRUE(toast != nullptr);
    for(int page : {1,2,3}){
        root->setProperty("currentPage",page);
        model.setHistoryStorageStatus(QString::number(page)+QStringLiteral(" 기록 저장 실패"));flush();
        EXPECT_FALSE(overlay->isVisible());EXPECT_TRUE(toast->isVisible());
        EXPECT_TRUE(tabs->isEnabled());
        if(page==2){
            EXPECT_TRUE(history->isEnabled());
            EXPECT_TRUE(window->grabWindow().save("dashboard-history-notification.png"));
        }
        auto* closeToast=root->findChild<QObject*>("dismissNotification");
        EXPECT_TRUE(closeToast && QMetaObject::invokeMethod(closeToast,"clicked"));flush();
        EXPECT_FALSE(toast->isVisible());EXPECT_FALSE(model.popupVisible());
    }
    root->setProperty("currentPage",2);
    model.setHistoryStorageStatus(QStringLiteral("알림 만료 시험 · 기록 저장 실패"));flush();
    EXPECT_TRUE(toast->isVisible());
    QElapsedTimer notificationWait;notificationWait.start();
    while(toast->isVisible()&&notificationWait.elapsed()<7000)flush();
    EXPECT_FALSE(toast->isVisible());EXPECT_FALSE(model.popupVisible());
    root->setProperty("currentPage",0);flush();EXPECT_FALSE(overlay->isVisible());
    physical.physical_measurement->soc_basis=2;physical.physical_measurement->soc_percent.reset();
    physical.physical_valid={true,true,true,false,false};model.updateSnapshot(physical);flush();
    auto* initializationHint=root->findChild<QQuickItem*>("socInitializationHint");
    EXPECT_TRUE(initializationHint && initializationHint->isVisible());
    EXPECT_FALSE(socGauge->property("available").toBool());
    const auto hintRect=initializationHint->mapRectToItem(canvas,initializationHint->boundingRect());
    EXPECT_TRUE(hintRect.top()>=0 && hintRect.bottom()<tabs->mapRectToItem(canvas,tabs->boundingRect()).top());
    EXPECT_TRUE(window->grabWindow().save("dashboard-physical-soc-initializing.png"));
    physical.physical_measurement->voltage_v=2.66;physical.vehicle.voltage_v=2.66;
    model.updateSnapshot(physical);flush();
    auto* socStatus=root->findChild<QObject*>("socStatusLabel");
    EXPECT_TRUE(socStatus != nullptr);
    EXPECT_EQ(socStatus->property("text").toString(),QStringLiteral("잔량 추정 범위 밖"));
    EXPECT_TRUE(initializationHint->isVisible());
    EXPECT_TRUE(initializationHint->property("text").toString().contains(QStringLiteral("3.0~4.25V")));
    EXPECT_FALSE(socGauge->property("available").toBool());
    EXPECT_EQ(voltage->property("value").toString(),QStringLiteral("2.660 V"));
    const auto outsideRect=initializationHint->mapRectToItem(canvas,initializationHint->boundingRect());
    EXPECT_TRUE(outsideRect.top()>=0 && outsideRect.bottom()<tabs->mapRectToItem(canvas,tabs->boundingRect()).top());
    EXPECT_TRUE(window->grabWindow().save("dashboard-physical-soc-out-of-range.png"));
    physical.physical_measurement->voltage_v=3.853;physical.vehicle.voltage_v=3.853;
    physical.physical_measurement->sequence++;physical.physical_measurement->soc_percent=50;
    physical.physical_valid[3]=true;physical.vehicle.soc_percent=50;model.updateSnapshot(physical);flush();
    EXPECT_FALSE(initializationHint->isVisible());EXPECT_TRUE(socGauge->property("available").toBool());
    EXPECT_EQ(socGauge->property("value").toDouble(),50.0);EXPECT_EQ(soh->property("text").toString(),QStringLiteral("--"));
    EXPECT_EQ(socStatus->property("text").toString(),QStringLiteral("배터리 잔량(SOC)"));
    auto* estimateHint=root->findChild<QObject*>("socEstimateHint");
    EXPECT_TRUE(estimateHint != nullptr && estimateHint->property("visible").toBool());
    physical.physical_measurement->observation_gap=true;model.updateSnapshot(physical);flush();
    EXPECT_EQ(socStatus->property("text").toString(),QStringLiteral("배터리 잔량(SOC)"));
    EXPECT_TRUE(estimateHint->property("text").toString().contains(QStringLiteral("측정 공백")));
    EXPECT_TRUE(window->grabWindow().save("dashboard-physical-soc-estimated.png"));
    root->setProperty("demonstration",true);flush();
    auto* connection=root->findChild<QObject*>("connectionStatusLabel");
    EXPECT_TRUE(connection && connection->property("text").toString().contains(QStringLiteral("가상 데이터")));
    root->setProperty("demonstration",false);flush();
}
int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);
    // Use the product's bundled Korean font in layout screenshots as well.
    QString family;
    for(const auto& file:{QStringLiteral("NanumGothic-Regular.ttf"),QStringLiteral("NanumGothic-Bold.ttf")}){
        const auto font=QFontDatabase::addApplicationFont(QFileInfo(QStringLiteral(IVI_QML_FILE)).dir()
            .filePath(QStringLiteral("../fonts/")+file));
        const auto families=QFontDatabase::applicationFontFamilies(font);
        if(families.isEmpty())return 1;
        family=families.first();
    }
    QFont dashboard_font(family);dashboard_font.setWeight(QFont::DemiBold);
    const auto raw_font=QRawFont::fromFont(dashboard_font);
    if(raw_font.weight()<QFont::DemiBold || !raw_font.supportsCharacter(uint(0xAC00)))return 1;
    app.setFont(dashboard_font);
    QTemporaryDir settings;
    QSettings::setDefaultFormat(QSettings::IniFormat);
    QSettings::setPath(QSettings::IniFormat,QSettings::UserScope,settings.path());
    QSettings::setPath(QSettings::NativeFormat,QSettings::UserScope,settings.path());
    return runTestProgram("Qt authentication warning and recovery",run);
}
