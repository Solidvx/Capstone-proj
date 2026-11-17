#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQuickWindow>
#include <QTimer>
#include <QUrl>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QRegularExpression>
#include <QFontDatabase>
#include <QRawFont>

#include <chrono>
#include <atomic>
#include <csignal>
#include <iostream>
#include <map>
#include <mutex>
#include <string>
#include <fstream>
#include <memory>
#include <openssl/crypto.h>

#include "dashboard_view_model.h"
#include "event_journal.h"
#include "shutdown_notifier.h"
#include "latency_recorder.h"
#include "socketcan_receiver.h"
#include "vehicle_data_service.h"
#include "can_session_config.h"
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
    bool windowed = false;
    std::string observation_jsonl;
    std::string ready_file;
    std::string run_id = "development";
    std::string protocol="session-v2";
    std::string session_policy;
    QString event_policy;
    unsigned rejection_capacity=0,rejection_budget=0,rejection_expiry=0;
    std::string screenshot_path;
    int screenshot_after_ms=1500;
};

Arguments parseArguments(int argc, char** argv) {
    Arguments result;
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--windowed") {
            result.windowed = true;
        } else if (argument == "--interface" && index + 1 < argc) {
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
        } else if((argument=="--rejection-queue" || argument=="--rejection-frame-budget" || argument=="--rejection-expiry-ms") && index+1<argc){
            const std::string text=argv[++index];
            if(text.empty() || text.find_first_not_of("0123456789")!=std::string::npos)throw std::invalid_argument("invalid rejection policy number");
            const auto value=std::stoull(text);
            if(!value || value>2147483647)throw std::invalid_argument("rejection policy outside supported range");
            if(argument=="--rejection-queue")result.rejection_capacity=value;
            else if(argument=="--rejection-frame-budget")result.rejection_budget=value;
            else result.rejection_expiry=value;
        } else if(argument=="--event-policy"){
            if(index+1==argc)throw std::invalid_argument("event policy requires a file");
            result.event_policy=QString::fromLocal8Bit(argv[++index]);
        } else if(argument=="--protocol" && index+1<argc){
            result.protocol=argv[++index];
        } else if(argument=="--session-policy" && index+1<argc){
            result.session_policy=argv[++index];
        } else if(argument=="--rejection-queue" || argument=="--rejection-frame-budget" || argument=="--rejection-expiry-ms"){
            throw std::invalid_argument("rejection policy requires a value");
        } else if(argument=="--protocol" || argument=="--session-policy"){
            throw std::invalid_argument("protocol/session-policy requires a value");
        } else if(argument=="--screenshot" && index+1<argc){
            result.screenshot_path=argv[++index];
        } else if(argument=="--screenshot-after-ms" && index+1<argc){
            result.screenshot_after_ms=std::stoi(argv[++index]);
        } else if(argument=="--screenshot" || argument=="--screenshot-after-ms"){
            throw std::invalid_argument("screenshot option requires a value");
        }
    }
    return result;
}

volatile std::sig_atomic_t stop_requested = 0;
void requestExit(int) { stop_requested = 1; }

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

int runDashboard(int argc, char* argv[]) {
    QGuiApplication application(argc, argv);
    for(int i=1;i<argc;++i)if(std::string(argv[i])=="--font-license"){
        QFile license(QStringLiteral(":/ivi-fonts/OFL.txt"));
        if(!license.open(QIODevice::ReadOnly))return 2;
        std::cout<<license.readAll().constData();return 0;
    }
    QString font_family;
    for(const auto& file:{QStringLiteral("NanumGothic-Regular.ttf"),QStringLiteral("NanumGothic-Bold.ttf")}){
        const int font_id=QFontDatabase::addApplicationFont(QStringLiteral(":/ivi-fonts/")+file);
        const auto families=QFontDatabase::applicationFontFamilies(font_id);
        if(font_id<0 || families.isEmpty() || (!font_family.isEmpty() && !families.contains(font_family))){
            std::cerr<<"Bundled Korean font is unavailable\n";return 2;
        }
        font_family=families.constFirst();
    }
    QFont dashboard_font(font_family);
    dashboard_font.setWeight(QFont::DemiBold);
    const auto raw_font=QRawFont::fromFont(dashboard_font);
    if(!raw_font.supportsCharacter(uint(0xAC00)) || raw_font.weight()<QFont::DemiBold){
        std::cerr<<"Bundled font lacks bold Korean glyphs\n";return 2;
    }
    application.setFont(dashboard_font);
    const auto arguments = parseArguments(argc, argv);
    if(arguments.protocol!="session-v2" && arguments.protocol!="legacy-v1"){
        std::cerr<<"--protocol must be session-v2 or explicit legacy-v1\n";return 2;
    }
    if(!arguments.screenshot_path.empty() && (QFile::exists(QString::fromStdString(arguments.screenshot_path)) ||
       arguments.screenshot_after_ms<100 || arguments.screenshot_after_ms>60000)){
        std::cerr<<"Screenshot requires a new path and100..60000ms delay\n";return 2;
    }
    QString boot_id;
    if(!arguments.observation_jsonl.empty()){
        QFile clock_file(QStringLiteral("/proc/sys/kernel/random/boot_id"));
        if(clock_file.open(QIODevice::ReadOnly))boot_id=QString::fromLatin1(clock_file.readAll()).trimmed();
    }
    if (!arguments.latency_csv.empty()) {
        const QRegularExpression run_pattern(QStringLiteral("^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$"));
        QFile boot_file(QStringLiteral("/proc/sys/kernel/random/boot_id"));
        if (arguments.run_id == "development" ||
            !run_pattern.match(QString::fromStdString(arguments.run_id)).hasMatch() ||
            !boot_file.open(QIODevice::ReadOnly)) {
            std::cerr << "Latency recording requires explicit --run-id and readable Linux boot_id\n";
            return 2;
        }
        boot_id = QString::fromLatin1(boot_file.readAll()).trimmed();
        const QRegularExpression boot_pattern(QStringLiteral(
            "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"));
        if (!boot_pattern.match(boot_id).hasMatch()) {
            std::cerr << "Invalid Linux boot_id; latency recording refused\n";
            return 2;
        }
    }

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
    const bool session_mode=!demo_mode && !arguments.experiment_secoc_off && arguments.protocol=="session-v2";
    if(session_mode){
        if(arguments.session_policy.empty()||arguments.key_path.empty()){
            std::cerr<<"session-v2 requires --session-policy and --secoc-key\n";return 2;
        }
        auto limits=capstone::session_v2::loadExchangeLimits(arguments.session_policy);
        ivi::SecOcKey key{};
        struct Erase{ivi::SecOcKey& key;~Erase(){OPENSSL_cleanse(key.data(),key.size());}} erase{key};
        std::ifstream file(arguments.key_path,std::ios::binary);
        file.read(reinterpret_cast<char*>(key.data()),key.size());
        if(file.gcount()!=static_cast<std::streamsize>(key.size())||file.peek()!=std::char_traits<char>::eof()){
            std::cerr<<"session-v2 requires exactly32 key bytes\n";return 2;
        }
        if(arguments.rejection_capacity || arguments.rejection_budget || arguments.rejection_expiry){
            service.configureRejectionReports(arguments.rejection_capacity,arguments.rejection_budget,arguments.rejection_expiry);
        }
        if(!service.enableSession(key,limits)){std::cerr<<"Session initialization refused\n";return 2;}
    }else if(!arguments.session_policy.empty() && !demo_mode){
        std::cerr<<"Session policy requires protected session-v2\n";return 2;
    }
    if(!session_mode && (arguments.rejection_capacity || arguments.rejection_budget || arguments.rejection_expiry))
        throw std::invalid_argument("rejection reports require protected session-v2");
    if (!session_mode && !demo_mode && !arguments.experiment_secoc_off &&
        (arguments.key_path.empty() || !service.loadSecOcKey(arguments.key_path))) {
        std::cerr << "A valid 32-byte SecOC key is required via --secoc-key\n";
        return 2;
    }

    DashboardViewModel view_model;
    std::unique_ptr<EventJournal> event_journal;
    // Declared after the worker owner so early returns notify before its join.
    ShutdownNotifier shutdown_notifier;
    QObject::connect(&application,&QCoreApplication::aboutToQuit,&application,
                     [&shutdown_notifier]{shutdown_notifier.notify();});
    if(!arguments.event_policy.isEmpty()){
        event_journal=std::make_unique<EventJournal>(EventJournal::loadPolicy(arguments.event_policy));
        view_model.expectProtectionHistory();
        QObject::connect(event_journal.get(),&EventJournal::historyLoaded,&view_model,&DashboardViewModel::restoreEventHistory,Qt::QueuedConnection);
        QObject::connect(event_journal.get(),&EventJournal::protectionHistoryLoaded,&view_model,&DashboardViewModel::restoreProtectionHistory,Qt::QueuedConnection);
        QObject::connect(event_journal.get(),&EventJournal::protectionCommitted,&view_model,&DashboardViewModel::protectionCommitted,Qt::QueuedConnection);
        QObject::connect(event_journal.get(),&EventJournal::storageStatus,&view_model,&DashboardViewModel::setHistoryStorageStatus,Qt::QueuedConnection);
        QObject::connect(&view_model,&DashboardViewModel::eventRecorded,event_journal.get(),[&](const QJsonObject& event){
            if(!event_journal->submit(event))view_model.setHistoryStorageStatus(QStringLiteral("일부 이벤트를 저장하지 못했습니다 · 현재 화면은 유지됩니다"));
        });
        view_model.setHistoryStorageStatus(QStringLiteral("이전 이벤트 기록을 확인하고 있습니다"));
        event_journal->start();
    }
    const auto observer_id = service.registerObserver(
        [&view_model](const ivi::VehicleSnapshot& snapshot) { view_model.updateSnapshot(snapshot); });
    if(session_mode)view_model.updateSnapshot(service.latest());
    QObject::connect(
        &view_model,
        &DashboardViewModel::securityAlertAcknowledgementRequested,
        [&service](qulonglong sequence) {
            service.acknowledgeSecurityAlert(static_cast<std::uint64_t>(sequence));
        });

    ivi::SocketCanReceiver receiver;
    std::atomic<bool> session_runtime_failed{false};
    auto send_session=[&](const std::vector<capstone::session_v2::Frame>& frames){
        for(const auto& frame:frames)if(!receiver.sendControl(frame.id,frame.data)){
            std::cerr<<"IVI control TX backpressure/failure; bounded session retry remains active\n";break;
        }
    };
#ifdef IVI_EXPERIMENT_BUILD
    UnprotectedTestReceiver unprotected_receiver;
#endif
    std::map<std::uint32_t, ivi::CanPayload> observation_pending;
    std::mutex observation_mutex;
    struct ReceiverStopGuard {
        ivi::SocketCanReceiver& receiver;
        ~ReceiverStopGuard(){receiver.stop();}
    } receiver_stop_guard{receiver}; // stop callbacks before their captured locals die
    std::uint64_t recorded_session_measurement=0,recorded_diagnostic=0,recorded_rejection=0;
    auto record_session_publication=[&](const ivi::VehicleSnapshot& snapshot){
        if(session_mode && observations.isOpen() && snapshot.local_rejection_record && snapshot.rejection_record_revision>recorded_rejection){
            recorded_rejection=snapshot.rejection_record_revision;
            const auto& body=*snapshot.local_rejection_record;
            const QJsonObject row{{"result","LOCAL_REJECTION_RECORD"},
                {"run_id",QString::fromStdString(arguments.run_id)},
                {"clock_id",boot_id},
                {"recorded_monotonic_ns",QString::number(std::chrono::duration_cast<std::chrono::nanoseconds>(
                    ivi::VehicleDataService::Clock::now().time_since_epoch()).count())},
                {"body_hex",QString::fromLatin1(QByteArray(reinterpret_cast<const char*>(body.data()),static_cast<int>(body.size())).toHex())},
                {"report_delivery","unconfirmed"}};
            observations.write(QJsonDocument(row).toJson(QJsonDocument::Compact)+'\n');observations.flush();
        }
        if(session_mode && observations.isOpen() && snapshot.authenticated_diagnostic && snapshot.diagnostic_revision>recorded_diagnostic){
            recorded_diagnostic=snapshot.diagnostic_revision;
            const auto& diagnostic=*snapshot.authenticated_diagnostic;
            const QJsonObject row{{"result","AUTHENTICATED_DIAGNOSTIC"},
                {"run_id",QString::fromStdString(arguments.run_id)},
                {"clock_id",boot_id},
                {"kind",static_cast<int>(diagnostic.kind)},
                {"session_id",QString::fromLatin1(QByteArray(reinterpret_cast<const char*>(diagnostic.session_id.data()),16).toHex())},
                {"sequence",QString::number(diagnostic.sequence)},
                {"received_monotonic_ms",QString::number(diagnostic.received_ms)},
                {"verified_monotonic_ms",QString::number(diagnostic.verified_ms)},
                {"incident_semantic_accepted",snapshot.incident_semantic_accepted},
                {"semantic_verified_monotonic_ns",QString::number(snapshot.incident_semantic_verified_ns)},
                {"body_hex",QString::fromLatin1(QByteArray(reinterpret_cast<const char*>(diagnostic.body.data()),static_cast<int>(diagnostic.body.size())).toHex())},
                {"observation_ready",snapshot.security_observation_ready},
                {"condition_mask",static_cast<int>(snapshot.observed_condition_mask)}};
            observations.write(QJsonDocument(row).toJson(QJsonDocument::Compact)+'\n');observations.flush();
        }
        if(!session_mode||!observations.isOpen()||snapshot.measurement_sequence<=recorded_session_measurement)return;
        recorded_session_measurement=snapshot.measurement_sequence;
        const QJsonObject publication{{"result","SESSION_PUBLICATION"},
            {"run_id",QString::fromStdString(arguments.run_id)},
            {"clock_id",boot_id},
            {"bms_context_id",snapshot.authenticated_bms_context ? QString::fromLatin1(QByteArray(
                reinterpret_cast<const char*>(snapshot.authenticated_bms_context->data()),16).toHex()) : QString{}},
            {"bms_raw_hex",snapshot.authenticated_bms ? QString::fromLatin1(QByteArray(
                reinterpret_cast<const char*>(snapshot.authenticated_bms->payload.data()),8).toHex()) : QString{}},
            {"bms_auth_hex",snapshot.authenticated_bms ? QString::fromLatin1(QByteArray(
                reinterpret_cast<const char*>(snapshot.authenticated_bms->authentication.data()),8).toHex()) : QString{}},
            {"bms_auth_received_ns",snapshot.authenticated_bms ? QString::number(snapshot.authenticated_bms->auth_received_ns) : QString{}},
            {"measurement_sequence",QString::number(snapshot.measurement_sequence)},
            {"session_generation",QString::number(snapshot.session_generation)},
            {"session_id",snapshot.protection_confirmed && snapshot.ecu_protection_status ?
                QString::fromLatin1(QByteArray(reinterpret_cast<const char*>(snapshot.ecu_protection_status->session_id.data()),16).toHex()) : QString{}},
            {"secoc_verified",snapshot.last_secoc_verified},
            {"state_confirmed",snapshot.session_state_ready},
            {"protection_confirmed",snapshot.protection_confirmed},
            {"battery_state",snapshot.vehicle.fail_safe_state},
            {"battery_reason",snapshot.vehicle.fail_safe_reason},
            {"t1_received_ns",QString::number(snapshot.t1_received_ns)},
            {"t2_published_ns",QString::number(snapshot.t2_published_ns)},
            {"valid",snapshot.vehicle.valid},{"stale",snapshot.vehicle.stale},
            {"soc",snapshot.vehicle.soc_percent},{"soh",snapshot.vehicle.soh_percent}};
        observations.write(QJsonDocument(publication).toJson(QJsonDocument::Compact)+'\n');
        observations.flush();
    };
    if(session_mode && observations.isOpen()){
        QObject::connect(&view_model,&DashboardViewModel::measurementReady,&application,
            [&](qulonglong sequence,qulonglong t1,qulonglong t2,qulonglong t3){
                const QJsonObject row{{"result","VIEW_MODEL_PUBLICATION"},
                    {"measurement_sequence",QString::number(sequence)},
                    {"t1_received_ns",QString::number(t1)},{"t2_published_ns",QString::number(t2)},
                    {"t3_view_model_ns",QString::number(t3)},
                    {"soc",view_model.soc()},{"soh",view_model.soh()},
                    {"connection",view_model.connectionLabel()},
                    {"security",view_model.securityTitle()},
                    {"security_description",view_model.securityDescription()},
                    {"incident_treatments",QJsonArray::fromStringList(view_model.incidentTreatments())},
                    {"rejection_summary",view_model.rejectionSummary()},
                    {"popup_title",view_model.popupTitle()},
                    {"flooding_metrics",QJsonArray::fromStringList(view_model.floodingMetrics())}};
                QMetaObject::invokeMethod(&application,[&,row]{
                    std::lock_guard<std::mutex> lock(observation_mutex);
                    observations.write(QJsonDocument(row).toJson(QJsonDocument::Compact)+'\n');observations.flush();
                },Qt::QueuedConnection);
            });
    }
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
                if(session_mode){
                    try{
                        const auto update=service.processSessionFrame({can_id,payload},received_at);
                        send_session(update.outgoing);result=update.result;
                    }catch(const std::exception& error){
                        session_runtime_failed=true;std::cerr<<"IVI session stopped: "<<error.what()<<'\n';
                        QMetaObject::invokeMethod(&application,&QCoreApplication::quit,Qt::QueuedConnection);
                    }
                }else result = service.processFrame(can_id, payload, received_at);
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
                if (!session_mode && (can_id == ivi::kCanIdBmsStatus || can_id == ivi::kCanIdBmsFailSafe) &&
                    (result == ivi::ProcessResult::kPendingAuthentication || result == ivi::ProcessResult::kPublished))
                    observation_pending[can_id] = payload;
                const auto original_id = can_id == ivi::kCanIdBmsSecOc ? ivi::kCanIdBmsStatus :
                    can_id == ivi::kCanIdFailSafeSecOc ? ivi::kCanIdBmsFailSafe : can_id;
                if (!session_mode && observation_pending.count(original_id)) {
                    const auto& original = observation_pending.at(original_id);
                    row["source_data"] = QString::fromLatin1(QByteArray(reinterpret_cast<const char*>(original.data()), 8).toHex());
                }
                observations.write(QJsonDocument(row).toJson(QJsonDocument::Compact) + '\n');
                record_session_publication(snapshot);
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
        QObject::connect(&stale_timer, &QTimer::timeout, [&service,&receiver]() {
            const auto drops=receiver.socketDrops();
            service.updateSocketDrops(receiver.dropMeasurementAvailable() ?
                std::optional<std::uint64_t>(drops) : std::nullopt);
            service.refreshTime();
        });
        stale_timer.start(50);
        // The 100ms pending deadline needs a finer tick than the 50ms stale refresh.
        QObject::connect(&pending_timer, &QTimer::timeout, [&]() {
            std::lock_guard<std::mutex> observation_lock(observation_mutex);
            const auto before = service.latest().pending_timeout_count;
            const auto now = ivi::SocketCanReceiver::Clock::now();
            if(session_mode){
                try{send_session(service.pollSession(now).outgoing);}
                catch(const std::exception& error){session_runtime_failed=true;std::cerr<<"IVI session timer stopped: "<<error.what()<<'\n';application.quit();}
                record_session_publication(service.latest());
            }else{
                service.pollTimeouts(now);
                record_timeouts(before, service.latest(), now);
            }
        });
        pending_timer.setTimerType(Qt::PreciseTimer);
        pending_timer.start(session_mode ? 2 : 10);
    }

    // Atomics outlive the window and all of its render-thread signal handlers.
    std::atomic<qulonglong> latest_measurement{0}, synced_measurement{0}, frame_number{0};
    LatencyRecorder latency_recorder(QString::fromStdString(arguments.latency_csv),
                                    QString::fromStdString(arguments.run_id), boot_id,
                                    arguments.latency_samples);
    if (!arguments.latency_csv.empty() && !latency_recorder.enabled()) {
        std::cerr << "Failed to open latency CSV: " << arguments.latency_csv << '\n';
        receiver.stop();
        return 5;
    }

    QQmlApplicationEngine engine;
    engine.setInitialProperties({{"vehicleModel", QVariant::fromValue(&view_model)},
                                 {"demonstration",demo_mode}});
    engine.load(QUrl(QStringLiteral(
        "qrc:/qt/qml/IviDashboard/ui_qml/qml/Main.qml")));
    if (engine.rootObjects().isEmpty()) {
        receiver.stop();
        return 4;
    }
    if (!demo_mode && !arguments.windowed) {
        if (auto* dashboard_window = qobject_cast<QQuickWindow*>(engine.rootObjects().constFirst()))
            dashboard_window->showFullScreen();
    }
    if (!demo_mode) {
        const QJsonObject ready{{"result", "READY"}, {"run_id", QString::fromStdString(arguments.run_id)},
                               {"secoc_on", !arguments.experiment_secoc_off},
                               {"display_platform",QGuiApplication::platformName()}};
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

    if(auto* window=qobject_cast<QQuickWindow*>(engine.rootObjects().constFirst())){
        auto presented=std::make_shared<std::atomic<bool>>(false);
        QObject::connect(window,&QQuickWindow::frameSwapped,window,[&,presented]{
            if(presented->exchange(true))return;
            const auto stamp=std::chrono::duration_cast<std::chrono::nanoseconds>(
                std::chrono::steady_clock::now().time_since_epoch()).count();
            QMetaObject::invokeMethod(&application,[&,stamp]{
                const QJsonObject row{{"result","WINDOW_PRESENTED"},{"run_id",QString::fromStdString(arguments.run_id)},
                    {"display_platform",QGuiApplication::platformName()},{"timestamp_ns",QString::number(stamp)}};
                std::cout<<QJsonDocument(row).toJson(QJsonDocument::Compact).constData()<<std::endl;
            },Qt::QueuedConnection);
        },Qt::DirectConnection);
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
                         [&latency_recorder, &latest_measurement, window](qulonglong sequence,
                                                     qulonglong t1,
                                                     qulonglong t2,
                                                     qulonglong t3) {
                             latency_recorder.queue(sequence, t1, t2, t3);
                             latest_measurement.store(sequence);
                             window->update();
        });
        QObject::connect(window, &QQuickWindow::beforeSynchronizing, window, [&]() {
            // Qt blocks the GUI during scene synchronization. Capture the model
            // version represented by this frame, not a later queued GUI update.
            synced_measurement.store(latest_measurement.load());
        }, Qt::DirectConnection);
        QObject::connect(window, &QQuickWindow::frameSwapped, window, [&, window]() {
            // Timestamp on the emitting thread, before GUI queueing delay.
            const auto t4 = static_cast<qulonglong>(std::chrono::duration_cast<std::chrono::nanoseconds>(
                std::chrono::steady_clock::now().time_since_epoch()).count());
            const auto sample = synced_measurement.load();
            const auto frame = ++frame_number;
            QMetaObject::invokeMethod(window, [&, window, sample, frame, t4]() {
                const bool done = latency_recorder.frameSwapped(sample, frame, t4, window->isExposed());
                if (!latency_recorder.healthy()) application.exit(5);
                else if (done) QTimer::singleShot(0, &application, &QCoreApplication::quit);
            }, Qt::QueuedConnection);
        }, Qt::DirectConnection);
    }

    std::signal(SIGINT, requestExit);
    std::signal(SIGTERM, requestExit);
    QTimer exit_timer;
    QObject::connect(&exit_timer, &QTimer::timeout, &application, [&]() {
        if (stop_requested) application.quit();
    });
    exit_timer.start(20);

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
    if(!arguments.screenshot_path.empty()){
        QTimer::singleShot(arguments.screenshot_after_ms,[&application,&engine,arguments]{
            auto* window=qobject_cast<QQuickWindow*>(engine.rootObjects().constFirst());
            const auto path=QString::fromStdString(arguments.screenshot_path);
            if(!window || QFile::exists(path) || !window->grabWindow().save(path)){
                std::cerr<<"Actual dashboard screenshot failed\n";application.exit(5);
            }
        });
    }

    if (arguments.demo_exit_ms > 0) {
        QTimer::singleShot(arguments.demo_exit_ms, &application, &QCoreApplication::quit);
    }

    const int result = application.exec();
    shutdown_notifier.notify();
    latency_recorder.finish();
    pending_timer.stop();
    stale_timer.stop();
    receiver.stop();
    service.unregisterObserver(observer_id);
    if(event_journal && observations.isOpen()){
        const QJsonObject row{{"result","EVENT_HISTORY_SNAPSHOT"},{"events",QJsonArray::fromStringList(view_model.eventHistory())},
            {"storage_status",view_model.historyStorageStatus()}};
        observations.write(QJsonDocument(row).toJson(QJsonDocument::Compact)+'\n');observations.flush();
    }
    if(session_runtime_failed)return 7;
    if (!latency_recorder.healthy()) return 5;
    if (result == 0 && latency_recorder.enabled() && arguments.latency_samples > 0 &&
        latency_recorder.completed() < arguments.latency_samples) {
        std::cerr << "Latency target incomplete: " << latency_recorder.completed()
                  << '/' << arguments.latency_samples << '\n';
        return 6;
    }
    return result;
}

int main(int argc,char** argv){
    try{return runDashboard(argc,argv);}
    catch(const std::exception& error){std::cerr<<"IVI startup stopped: "<<error.what()<<'\n';return 2;}
}
