#include "ads1115_acquirer.h"
#include "can_cdd.h"
#include "can_receive_recovery.h"
#include "bms_middleware.h"
#include "bms_calculation_task.h"
#include "ekf_soc_estimator.h"
#include "failsafe_sm.h"
#include "hardware_sample_feed.h"
#include "linux_i2c_transport.h"
#include "secoc_module.h"
#include "sensor_simulator.h"
#include "input_lineage.h"
#include "soh_estimator.h"
#include "soh_capacity_scenario.h"
#include "watchdog_manager.h"
#include "can_session_config.h"
#include "ids_diagnostic_socket.h"
#include "ids_diagnostic_bridge.h"
#include "ids_peer_diagnostic.h"
#include "protection_publisher.h"
#include "checkpoint_store.h"
#include "checkpoint_writer.h"
#include "can_restart_notice.h"
#include "physical_sensor_runtime.h"
#include "physical_measurement.h"
#include "diagnostic_tx_queue.h"
#ifdef ECU_SENDER_CONTROL_FIXTURE
#include "test/ecu_sender_gate.h"
#endif
#include <filesystem>
#include <iomanip>
#include <sstream>
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>
#include <limits>

#include <atomic>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <csignal>
#include <exception>
#include <iostream>
#include <memory>
#include <string>
#include <thread>
#include <deque>
#include <fstream>
#include <mutex>
#include <functional>
#include <openssl/crypto.h>

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

int runMain(int argc, char** argv, BmsCalculationTask::Calculation calculation = calculateBms) {
    std::string interface_name = "vcan0";
    std::string sensor_mode = "constant";
    std::string profile_path = "adaptive_ecu/data/battery_profile.csv";
    std::string key_path = "/etc/secoc/key.bin";
    std::string i2c_device = "/dev/i2c-1";
    std::string physical_config_path;
    bool secoc_enabled = true;
    std::string soh_profile_path;
    std::string protocol="session-v2",session_policy_path;
    std::string ids_socket_path;
    unsigned ids_pid=0,ids_budget=0,ids_expiry=0;
    std::string checkpoint_path,start_intent;
    int supervisor_fd=-1,ids_context_fd=-1,ids_peer_fd=-1,tx_trace_fd=-1;
#ifdef ECU_SENDER_CONTROL_FIXTURE
    int test_sender_fd=-1;
#endif
    unsigned checkpoint_period=0,checkpoint_flush=0,checkpoint_max_age=0,restart_wait=0,restart_retry=0,restart_attempts=0;
    struct CheckpointLock {
        int fd=-1;
        ~CheckpointLock(){if(fd>=0)::close(fd);}
    } checkpoint_lock;
    auto positive=[](const std::string& text){
        if(text.empty() || text.find_first_not_of("0123456789")!=std::string::npos)
            throw std::invalid_argument("positive numeric option required");
        const auto value=std::stoull(text);
        if(!value || value>static_cast<unsigned>(std::numeric_limits<int>::max()))
            throw std::invalid_argument("numeric option outside supported range");
        return static_cast<unsigned>(value);
    };

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if(arg=="--help"){
            std::cout<<"adaptive_ecu --interface CAN --sensor-mode constant|profile_csv|random_walk|ads1115|physical\n"
                <<"  --physical-config FILE (physical mode, session-v2 only; explicit sensor/model settings)\n"
                <<"  --secoc on --protocol session-v2 --session-policy FILE --key FILE\n"
                <<"  --protocol legacy-v1 selects explicit historical experiments; --secoc off is explicit only\n"
                <<"  --ids-socket PATH --ids-pid PID --ids-frame-budget N --ids-expiry-ms N (Linux, same UID)\n"
                <<"  --profile CSV --soh-profile CSV --i2c-device PATH\n"
                <<"  --checkpoint PATH --start-intent fresh|resume --checkpoint-max-age-ms N\n"
                <<"  --checkpoint-period-ms N --checkpoint-flush-ms N\n"
                <<"  --supervisor-fd N (inherited nonblocking pipe, process health only)\n"
                <<"  --ids-context-fd N (public active context to inherited local pipe)\n"
                <<"  --ids-peer-fd N (authenticated IVI diagnostics to inherited local pipe)\n"
                <<"  --tx-trace-fd N (opt-in private nonblocking CAN syscall trace pipe; no delivery claim)\n"
                <<"  --restart-wait-ms N --restart-retry-ms N --restart-notice-attempts N\n";return 0;
        }
        if (i + 1 == argc) {
            std::cerr << arg << " requires a value\n";return 2;
        }
        if (arg == "--interface") {
            interface_name = argv[++i];
        } else if (arg == "--sensor-mode") {
            sensor_mode = argv[++i];
        } else if (arg == "--profile") {
            profile_path = argv[++i];
        } else if (arg == "--secoc") {
            const std::string selected=argv[++i];
            if(selected!="on" && selected!="off"){
                std::cerr<<"--secoc must be on or explicit off\n";return 2;
            }
            secoc_enabled = selected=="on";
        } else if (arg == "--key") {
            key_path = argv[++i];
        } else if (arg == "--i2c-device") {
            i2c_device = argv[++i];
        } else if(arg=="--physical-config"){
            if(!physical_config_path.empty())throw std::invalid_argument("physical config selected twice");
            physical_config_path=argv[++i];
        } else if (arg == "--soh-profile") {
            soh_profile_path = argv[++i];
            if (soh_profile_path.empty()) {
                std::cerr << "--soh-profile requires a non-empty CSV path\n";
                return 2;
            }
#ifdef ECU_SENDER_CONTROL_FIXTURE
        } else if(arg=="--test-sender-control-fd"){
            test_sender_fd=static_cast<int>(positive(argv[++i]));
#endif
        } else if(arg=="--ids-context-fd"){
            ids_context_fd=static_cast<int>(positive(argv[++i]));
        } else if(arg=="--ids-peer-fd"){
            ids_peer_fd=static_cast<int>(positive(argv[++i]));
        } else if(arg=="--supervisor-fd"){
            supervisor_fd=static_cast<int>(positive(argv[++i]));
        } else if(arg=="--checkpoint"){
            checkpoint_path=argv[++i];
        } else if(arg=="--start-intent"){
            start_intent=argv[++i];
        } else if(arg=="--checkpoint-period-ms"){
            checkpoint_period=positive(argv[++i]);
        } else if(arg=="--checkpoint-flush-ms"){
            checkpoint_flush=positive(argv[++i]);
        } else if(arg=="--checkpoint-max-age-ms"){
            checkpoint_max_age=positive(argv[++i]);
        } else if(arg=="--restart-wait-ms"){
            restart_wait=positive(argv[++i]);
        } else if(arg=="--restart-retry-ms"){
            restart_retry=positive(argv[++i]);
        } else if(arg=="--restart-notice-attempts"){
            restart_attempts=positive(argv[++i]);
        } else if(arg=="--ids-socket"){
            ids_socket_path=argv[++i];
        } else if(arg=="--ids-pid"){
            ids_pid=positive(argv[++i]);
        } else if(arg=="--ids-frame-budget"){
            ids_budget=positive(argv[++i]);
        } else if(arg=="--ids-expiry-ms"){
            ids_expiry=positive(argv[++i]);
        } else if(arg=="--protocol"){
            protocol=argv[++i];
        } else if(arg=="--session-policy"){
            session_policy_path=argv[++i];
        } else if(arg=="--tx-trace-fd"){
            if(tx_trace_fd>=0)throw std::invalid_argument("TX trace descriptor must be selected once");
            tx_trace_fd=static_cast<int>(positive(argv[++i]));
        } else {
            std::cerr<<"Unsupported option: "<<arg<<'\n';return 2;
        }
    }

    namespace session=capstone::session_v2;
    if(tx_trace_fd>=0){
        CanTxTrace::validateFd(tx_trace_fd);
        if(tx_trace_fd==supervisor_fd || tx_trace_fd==ids_context_fd || tx_trace_fd==ids_peer_fd)
            throw std::invalid_argument("TX trace requires a distinct inherited pipe");
    }
#ifdef ECU_SENDER_CONTROL_FIXTURE
    if(interface_name.rfind("vcan",0)!=0 || interface_name.find('/')!=std::string::npos ||
       !std::filesystem::is_directory("/sys/devices/virtual/net/"+interface_name) ||
       test_sender_fd==supervisor_fd || test_sender_fd==ids_context_fd || test_sender_fd==ids_peer_fd || test_sender_fd==tx_trace_fd)
        throw std::invalid_argument("test sender control requires virtual CAN and distinct inherited pipe");
    TestSenderGate test_sender_gate(test_sender_fd,[](bool paused,const char* reason,std::uint64_t at){
        std::cout<<"{\"result\":\"TEST_SENDER_GATE\",\"paused\":"<<(paused?"true":"false")
                 <<",\"reason\":\""<<reason<<"\",\"monotonic_ms\":"<<at<<"}"<<std::endl;
    });
#endif
    if(protocol!="session-v2" && protocol!="legacy-v1"){
        std::cerr<<"--protocol must be session-v2 or explicit legacy-v1\n";return 2;
    }
    const bool recovery_requested=!checkpoint_path.empty() || !start_intent.empty() || checkpoint_max_age || checkpoint_period || checkpoint_flush ||
        restart_wait || restart_retry || restart_attempts;
    if(recovery_requested && (checkpoint_path.empty() || (start_intent!="fresh" && start_intent!="resume") ||
       !checkpoint_max_age || !checkpoint_period || !checkpoint_flush || checkpoint_period>checkpoint_max_age || !restart_wait || !restart_retry || !restart_attempts || restart_attempts>32 ||
       !secoc_enabled || protocol!="session-v2"))
        throw std::invalid_argument("recovery requires checkpoint, explicit intent/age/restart limits and session-v2");
    if(supervisor_fd>=0){
        struct stat info{};const int flags=::fcntl(supervisor_fd,F_GETFL);
        if(!recovery_requested || supervisor_fd<3 || ::fstat(supervisor_fd,&info)!=0 || !S_ISFIFO(info.st_mode) ||
           flags<0 || !(flags&O_NONBLOCK) || (flags&O_ACCMODE)!=O_WRONLY)
            throw std::invalid_argument("supervisor fd requires recovery and inherited nonblocking write pipe");
        std::signal(SIGPIPE,SIG_IGN);
    }
    if(ids_context_fd>=0){
        struct stat info{};const int flags=::fcntl(ids_context_fd,F_GETFL);
        if(!secoc_enabled || protocol!="session-v2" || ids_context_fd<3 || ids_context_fd==supervisor_fd ||
           ::fstat(ids_context_fd,&info)!=0 || !S_ISFIFO(info.st_mode) || flags<0 ||
           !(flags&O_NONBLOCK) || (flags&O_ACCMODE)!=O_WRONLY)
            throw std::invalid_argument("IDS context requires distinct inherited nonblocking write pipe and session-v2");
        std::signal(SIGPIPE,SIG_IGN);
    }
    std::unique_ptr<session::PeerDiagnosticWriter> peer_diagnostics;
    if(ids_peer_fd>=0){
        if(ids_context_fd<3 || ids_peer_fd==ids_context_fd || ids_peer_fd==supervisor_fd)
            throw std::invalid_argument("IDS peer pipe requires a distinct valid session context pipe");
        peer_diagnostics=std::make_unique<session::PeerDiagnosticWriter>(ids_peer_fd);
    }
    const bool ids_requested=!ids_socket_path.empty() || ids_pid || ids_budget || ids_expiry;
    if(ids_requested && (ids_socket_path.empty() || !ids_pid || !ids_budget || ids_budget>36 || !ids_expiry ||
                          !secoc_enabled || protocol!="session-v2")){
        std::cerr<<"IDS forwarding requires all four IDS options and authenticated session-v2\n";return 2;
    }
#ifndef __linux__
    if(ids_requested){std::cerr<<"IDS socket forwarding requires Linux\n";return 2;}
#endif
    std::optional<session::ExchangeLimits> session_limits;
    session::Key session_key{};
    struct KeyErase {
        session::Key& key;
        ~KeyErase(){OPENSSL_cleanse(key.data(),key.size());}
    } erase_key{session_key};
    if(secoc_enabled && protocol=="session-v2"){
        if(session_policy_path.empty()){
            std::cerr<<"session-v2 requires --session-policy; select explicit tested limits (no implicit timing defaults)\n";return 2;
        }
        session_limits=session::loadExchangeLimits(session_policy_path);
        std::ifstream key_input(key_path,std::ios::binary);
        key_input.read(reinterpret_cast<char*>(session_key.data()),session_key.size());
        if(key_input.gcount()!=static_cast<std::streamsize>(session_key.size()) || key_input.peek()!=std::char_traits<char>::eof()){
            std::cerr<<"session-v2 requires exactly32 key bytes\n";return 2;
        }
    }else if(!session_policy_path.empty()){
        std::cerr<<"--session-policy requires --secoc on with session-v2\n";return 2;
    }

    SohCapacityScenario soh_scenario;
    try {
        if (!soh_profile_path.empty()) soh_scenario = SohCapacityScenario::fromFile(soh_profile_path);
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 2; // reject bad scenario before opening CAN or starting workers
    }

    const auto mode = SensorSimulator::parseMode(sensor_mode);
    if (!mode) {
        std::cerr << "Unsupported sensor mode: " << sensor_mode
                  << " (constant|profile_csv|random_walk|ads1115|physical)\n";
        return 2;
    }
    std::optional<PhysicalRuntimeConfig> physical_config;
    std::unique_ptr<PhysicalSampleFeed> physical_feed;
    std::unique_ptr<PhysicalSensorProcess> physical_process;
    if(*mode==SensorSimulator::Mode::PHYSICAL_HARDWARE){
        if(physical_config_path.empty()||!session_limits||recovery_requested||!soh_profile_path.empty())
            throw std::invalid_argument("physical mode requires explicit config and session-v2; legacy/virtual SOH/checkpoint recovery are unsupported");
        physical_config_path=std::filesystem::absolute(physical_config_path).string();
        physical_config=loadPhysicalRuntimeConfig(physical_config_path);
        physical_feed=std::make_unique<PhysicalSampleFeed>(*physical_config);
#ifndef __linux__
        throw std::invalid_argument("physical mode requires Linux");
#endif
    }else if(!physical_config_path.empty())throw std::invalid_argument("physical config requires physical sensor mode");
    // Pin/validate the actual CSV bytes before any CAN or worker side effects.
    SensorSimulator sensor(*mode,profile_path);
    sensor.exportState();

    std::signal(SIGINT, handleSignal);
    std::signal(SIGTERM, handleSignal);

    struct QueuedFrame {CanFrame frame;std::uint64_t captured_ms;};
    std::deque<QueuedFrame> session_rx;
    std::mutex session_rx_mutex;
    std::atomic<unsigned> session_rx_dropped{0};
    SocketCanCdd driver; // destroyed before its callback queue/mutex
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

    EkfSocEstimator soc_estimator;
    SohEstimator soh_estimator;
    FailSafeStateMachine failsafe;
    SecOcModule secoc;
    double restored_soh_elapsed=0;
    std::string input_identity,soh_identity;
    std::uint32_t checkpoint_age=0xffffffffu;
    std::optional<ProtectionHistory::Snapshot> restored_protection;
    if(recovery_requested){
        const auto directory=std::filesystem::path(checkpoint_path).parent_path();
        struct stat directory_info{};
        if(directory.empty() || ::lstat(directory.c_str(),&directory_info)!=0 || !S_ISDIR(directory_info.st_mode) ||
           directory_info.st_uid!=::geteuid() || (directory_info.st_mode&0077))
            throw std::runtime_error("checkpoint requires an existing private owned directory");
        checkpoint_lock.fd=::open((checkpoint_path+".lock").c_str(),O_CREAT|O_RDWR|O_NOFOLLOW|O_CLOEXEC,0600);
        struct stat lock_info{};
        if(checkpoint_lock.fd<0 || ::fstat(checkpoint_lock.fd,&lock_info)!=0 || !S_ISREG(lock_info.st_mode) ||
           lock_info.st_uid!=::geteuid() || (lock_info.st_mode&0077) || ::flock(checkpoint_lock.fd,LOCK_EX|LOCK_NB)!=0)
            throw std::runtime_error("checkpoint already owned or lock rejected");
        input_identity=sensor.profileInput() ? sensor.profileInput()->recovery_identity :
            inputSha256("sensor-v1:"+sensor_mode+":"+(*mode==SensorSimulator::Mode::ADS1115_HARDWARE ? i2c_device : ""));
        soh_identity=soh_scenario.inputFingerprint() ? soh_scenario.inputFingerprint()->recovery_identity :
            inputSha256("soh-v1:50Ah:");
        if(start_intent=="resume"){
            const auto age=std::filesystem::file_time_type::clock::now()-std::filesystem::last_write_time(checkpoint_path);
            const auto age_ms=std::chrono::duration_cast<std::chrono::milliseconds>(age).count();
            if(age_ms<0 || static_cast<std::uint64_t>(age_ms)>checkpoint_max_age)
                throw std::runtime_error("checkpoint age rejected; explicit fresh start required");
            const auto saved=loadCheckpoint(checkpoint_path);
            if(!restoreCheckpoint(saved,input_identity,soh_identity,soc_estimator,soh_estimator,failsafe,sensor,restored_soh_elapsed))
                throw std::runtime_error("checkpoint restore rejected; no fresh fallback");
            restored_protection=saved.protection;
            checkpoint_age=static_cast<std::uint32_t>(age_ms);
            std::cout<<"Recovery: calculation and protection restored; battery state="<<static_cast<unsigned>(failsafe.state())<<'\n';
        }
    }
    // Thermal protection keeps the process alive; only process faults require recovery.
    auto new_uuid=[](){auto id=session::freshNonce();id[6]=(id[6]&15)|0x40;id[8]=(id[8]&63)|0x80;return id;};
    session::Nonce instance=new_uuid(),restart_operation{};
    ProtectionHistory protection(new_uuid,failsafe.exportState(),restored_protection);
    if(recovery_requested && start_intent=="resume" && !restored_protection)
        std::cerr<<"Protection continuity unknown: restored calculation has no saved event identity\n";
    if(tx_trace_fd>=0){
        std::signal(SIGPIPE,SIG_IGN); // A disconnected trace consumer cannot kill the battery process.
        driver.enableTxTrace(tx_trace_fd,instance);
    }
    std::ostringstream input_instance;
    input_instance<<std::hex<<std::setfill('0');
    for (auto byte:instance) input_instance<<std::setw(2)<<static_cast<unsigned>(byte);
    std::string physical_clock_id;
    if(physical_config){std::ifstream clock("/proc/sys/kernel/random/boot_id");clock>>physical_clock_id;}
    if(physical_config){
        std::cout<<"{\"result\":\"ECU_PHYSICAL_LINEAGE\",\"model_config_sha256\":\""<<physical_config->meter.model_calibration_id
                 <<"\",\"nominal_capacity_ah\":"<<physical_config->meter.nominal_capacity_ah
                 <<",\"soc_model\":\""<<(physical_config->meter.automatic_soc?PhysicalSocEkf::kModel:
                    physical_config->meter.initial_soc?"explicit-coulomb":"unknown")<<'"'
                 <<",\"physical_accuracy_verified\":false}"<<std::endl;
    }else std::cout<<inputLineageJson(input_instance.str(),recovery_requested?start_intent:"standalone",
        *mode,sensor,sensor.exportState(),soh_scenario,restored_soh_elapsed,
        *mode==SensorSimulator::Mode::ADS1115_HARDWARE?inputSha256(i2c_device):"")<<std::endl;
    const auto process_started=monotonicMs();
    std::uint64_t status_sent=0,status_generation=0;
    std::unique_ptr<CheckpointWriter> checkpoint_writer;
    if(recovery_requested)checkpoint_writer=std::make_unique<CheckpointWriter>([&](const RecoveryCheckpoint& state){
        saveCheckpointAtomic(checkpoint_path,state);
    });
    std::uint64_t checkpoint_submitted_at=0;
    auto save_state=[&](double elapsed){
        checkpoint_submitted_at=monotonicMs();
        auto state=captureCheckpoint(soc_estimator,soh_estimator,failsafe,sensor,elapsed,input_identity,soh_identity);
        state.version=2;state.protection=protection.snapshot();
        return checkpoint_writer->submit(std::move(state));
    };

    if (secoc_enabled && protocol=="legacy-v1" && !secoc.loadKey(key_path)) {
        std::cerr << "SecOC key load failed: " << key_path << '\n';
        return 1;
    }

    auto delivery=[](uint32_t id, CanPublishResult result) {
            if (result != CanPublishResult::Sent && result!=CanPublishResult::AwaitingSession) {
                std::cerr << "CAN publication failed: original_id=" << id
                          << " stage=" << (result == CanPublishResult::OriginalSendFailed
                                              ? "original" : "authentication") << '\n';
            }
        };
    std::unique_ptr<session::Exchange> exchange;
    std::unique_ptr<session::ProtectionPublisher> protection_publisher;
    std::uint64_t protection_reported_drops=0,protection_reported_failures=0;
#ifdef __linux__
    std::unique_ptr<session::IdsDiagnosticSocket> ids_socket;
    std::unique_ptr<session::IdsDiagnosticBridge> ids_bridge;
    if(ids_requested){
        ids_socket=std::make_unique<session::IdsDiagnosticSocket>(ids_socket_path,geteuid(),static_cast<pid_t>(ids_pid));
        ids_bridge=std::make_unique<session::IdsDiagnosticBridge>(4,ids_budget,ids_expiry);
    }
    std::uint64_t ids_reported_drops=0,ids_reported_rejections=0;
#endif
    auto send_frames=[&](const std::vector<session::Frame>& frames){
        for(const auto& frame:frames){
            CanFrame output{frame.id,frame.dlc,frame.data};
            if(!driver.send(output)){
                std::cerr<<"session-v2 CAN send failed id="<<frame.id<<"; no counter rollback\n";return false;
            }
        }
        return true;
    };
    std::uint64_t context_sent_at=0,context_generation=0,context_boundary_ns=0;
    bool context_open=false,context_announced=false;
    auto announce_context=[&]{
        if(ids_context_fd<0 || !exchange)return;
        const auto now=monotonicMs();
        const bool changed=!context_announced || context_generation!=exchange->generation() || context_open!=exchange->dataOpen();
        if(!changed && now-context_sent_at<1000)return;
        if(changed){
            context_boundary_ns=static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
                std::chrono::steady_clock::now().time_since_epoch()).count());
            context_generation=exchange->generation();context_open=exchange->dataOpen();
        }
        std::vector<std::uint8_t> packet{'C','S','C','1',static_cast<std::uint8_t>(context_open),0,0,0};
        for(const auto value:{context_generation,context_boundary_ns,static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count())})
            for(int shift=56;shift>=0;shift-=8)packet.push_back(static_cast<std::uint8_t>(value>>shift));
        const auto ctx=exchange->activeContext();
        packet.push_back(ctx ? static_cast<std::uint8_t>(ctx->transfer_id>>8) : 0);
        packet.push_back(ctx ? static_cast<std::uint8_t>(ctx->transfer_id) : 0);
        if(ctx){packet.insert(packet.end(),ctx->nonce_b.begin(),ctx->nonce_b.end());packet.insert(packet.end(),ctx->nonce_a.begin(),ctx->nonce_a.end());}
        else packet.resize(66,0);
        const auto count=::write(ids_context_fd,packet.data(),packet.size());
        if(count==static_cast<ssize_t>(packet.size())){context_announced=true;context_sent_at=now;}
        else if(errno!=EINTR){
            ::close(ids_context_fd);
            std::cerr<<"IDS context pipe disabled; observation cannot claim current session\n";
            ids_context_fd=-1;
        }
    };
    std::unique_ptr<BmsMiddleware> middleware;
    std::unique_ptr<session::DiagnosticTxQueue> physical_tx;
    if(physical_config)physical_tx=std::make_unique<session::DiagnosticTxQueue>(1,6,session_limits->diagnostic.assembly_ms);
    std::function<void()> pump_session=[]{ };
    if(session_limits){
        exchange=std::make_unique<session::Exchange>(session::Endpoint::Ecu,session_key,*session_limits);
        // Share the existing NodeStatus cadence. Queue expiry is selected by
        // the explicit diagnostic policy; these are not Pi performance claims.
        protection_publisher=std::make_unique<session::ProtectionPublisher>(1000,session_limits->diagnostic.assembly_ms);
        OPENSSL_cleanse(session_key.data(),session_key.size());
        middleware=std::make_unique<BmsMiddleware>([&](const CanFrame& original){
            const auto frames=exchange->publishData(static_cast<std::uint16_t>(original.id),original.data,monotonicMs());
            if(frames.empty())return CanPublishResult::AwaitingSession;
            if(frames.size()!=2){send_frames(frames);return CanPublishResult::AwaitingSession;}
            if(!send_frames({frames[0]}))return CanPublishResult::OriginalSendFailed;
            if(!send_frames({frames[1]}))return CanPublishResult::AuthenticationSendFailed;
            return CanPublishResult::Sent;
        },delivery);
        driver.registerCallback([&](const CanFrame& frame){
#ifdef ECU_RX_FAULT_FIXTURE
            // Compiled only into the Linux test fixture, never the product.
            if(frame.id==0x123u)throw std::runtime_error("fixture receive callback failed");
#endif
            const auto id=frame.id&0x7ffu;
            if(id!=0x301 && id!=0x303)return;
            const auto at=monotonicMs();
            std::lock_guard<std::mutex> lock(session_rx_mutex);
            if(session_rx.size()>=256){++session_rx_dropped;return;}
            session_rx.push_back({frame,at});
        });
        pump_session=[&]{
            std::deque<QueuedFrame> received;
            {std::lock_guard<std::mutex> lock(session_rx_mutex);received.swap(session_rx);}
            for(const auto& queued:received){
                const auto& frame=queued.frame;
                session::Frame input{frame.id&0x7ffu,frame.data,frame.dlc,
                    bool(frame.id&0x80000000u),bool(frame.id&0x40000000u),bool(frame.id&0x20000000u)};
                send_frames(exchange->receive(input,monotonicMs(),queued.captured_ms));
                const auto& report=exchange->lastDiagnosticResult();
                if(report.code==session::DiagnosticResultCode::Message && report.message && report.message->kind==session::DiagnosticKind::Rejection){
                    const auto& body=report.message->body;
                    std::cout<<"IVI_REJECTION reason="<<unsigned(body[32])<<" mac_verified="<<unsigned(body[33])
                        <<" treatment="<<unsigned(body[34])<<" reference_kind="<<unsigned(body[36]);
                    std::ostringstream record_id;record_id<<std::hex<<std::setfill('0');
                    for(unsigned i=16;i<32;++i)record_id<<std::setw(2)<<unsigned(body[i]);
                    std::cout<<" record_id="<<record_id.str()<<std::endl;
                    if(peer_diagnostics){
                        announce_context();
                        const auto published_ns=static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
                            std::chrono::steady_clock::now().time_since_epoch()).count());
                        peer_diagnostics->forward(*report.message,exchange->generation(),published_ns);
                    }
                }
            }
            send_frames(exchange->poll(monotonicMs()));
#ifdef __linux__
            if(ids_socket){
                try{
                    if(auto submitted=ids_socket->receive())ids_bridge->submit(*exchange,*submitted,monotonicMs());
                    ids_bridge->pump(*exchange,monotonicMs(),[&](const session::Frame& frame){
                        return driver.send(CanFrame{frame.id,frame.dlc,frame.data});
                    });
                    const auto drops=ids_bridge->dropped()+ids_bridge->unavailable();
                    const auto rejected=ids_bridge->rejected()+ids_socket->rejected();
                    if(drops!=ids_reported_drops || rejected!=ids_reported_rejections){
                        std::cerr<<"IDS diagnostic forwarding dropped="<<drops<<" rejected="<<rejected<<'\n';
                        ids_reported_drops=drops;ids_reported_rejections=rejected;
                    }
                }catch(const std::runtime_error& error){
                    std::cerr<<"IDS diagnostic forwarding disabled: "<<error.what()<<'\n';
                    ids_socket.reset();ids_bridge.reset();
                }
            }
#endif
            protection_publisher->pump(*exchange,monotonicMs(),[&](const session::Frame& frame){
                return driver.send(CanFrame{frame.id,frame.dlc,frame.data});
            });
            if(physical_tx&&exchange->dataOpen()&&exchange->activeContext())
                physical_tx->pump(session::contextId(*exchange->activeContext()),monotonicMs(),[&](const session::Frame& frame){
                    return driver.send(CanFrame{frame.id,frame.dlc,frame.data});
                });
            if(protection_publisher->dropped()!=protection_reported_drops ||
               protection_publisher->failures()!=protection_reported_failures){
                protection_reported_drops=protection_publisher->dropped();
                protection_reported_failures=protection_publisher->failures();
                std::cerr<<"Protection diagnostics dropped="<<protection_reported_drops
                         <<" failures="<<protection_reported_failures<<"; battery monitoring continues\n";
            }
            announce_context();
            const auto lost=session_rx_dropped.exchange(0);
            if(lost)std::cerr<<"session-v2 receive owner queue dropped="<<lost<<"; incomplete messages await bounded recovery\n";
        };
        const auto initial_risk=failsafe.exportState();
        send_frames(exchange->setCurrentState(session::Payload{static_cast<std::uint8_t>(initial_risk.state),
            static_cast<std::uint8_t>(initial_risk.reason!=FailSafeStateMachine::REASON_NONE),
            static_cast<std::uint8_t>(initial_risk.reason),0,0,0,0,0},monotonicMs()));
        driver.startReceive();send_frames(exchange->start(monotonicMs()));
    }else middleware=std::make_unique<BmsMiddleware>(driver,secoc,secoc_enabled,delivery);
    auto wait_cycle=[&](std::chrono::steady_clock::time_point until){
        if(!exchange){std::this_thread::sleep_until(until);return;}
        while(running && std::chrono::steady_clock::now()<until){
            pump_session();
            std::this_thread::sleep_until(std::min(until,std::chrono::steady_clock::now()+std::chrono::milliseconds(2)));
        }
    };
    failsafe.setEventCallback([&](const FailSafeEvent& event) {
        const auto continuity_failed=protection.failed();
        protection.observe(failsafe.exportState());
        if(protection.failed() && !continuity_failed)
            std::cerr<<"Protection continuity unavailable; battery monitoring continues without event identity\n";
        if(exchange){
            const auto snapshot=failsafe.exportState();
            send_frames(exchange->setCurrentState(session::Payload{static_cast<std::uint8_t>(snapshot.state),
                static_cast<std::uint8_t>(snapshot.reason!=FailSafeStateMachine::REASON_NONE),static_cast<std::uint8_t>(snapshot.reason),0,0,0,0,0},monotonicMs()));
        }
        middleware->publishFailSafe(event);
        std::cout << "Fail-safe transition: " << static_cast<int>(event.prev_state)
                  << " -> " << static_cast<int>(event.new_state)
                  << " reason=0x" << std::hex << static_cast<int>(event.reason)
                  << std::dec << '\n';
    });

    // Product recovery uses independent computation and owner/CAN loops.
    // Explicit checkpoint age policy also bounds the last committed in-memory state.
    std::unique_ptr<BmsCalculationTask> calculation_task;
    std::unique_ptr<TaskRecovery> calculation_recovery;
    bool calculation_inflight=false,calculation_operator=false;
    std::unique_ptr<CanReceiveRecovery> receive_recovery;
    bool receive_operator=false;
    if(exchange)receive_recovery=std::make_unique<CanReceiveRecovery>(driver,monotonicMs());
    std::uint64_t calculation_started=0,calculation_checked=monotonicMs();
    SensorData last_calculation_sample{};
    double last_committed_soh_elapsed=restored_soh_elapsed;
    if(recovery_requested){
        sensor.exportState(); // preload/validate profile before the worker owns copies
        calculation_task=std::make_unique<BmsCalculationTask>(std::move(calculation));
        calculation_task->checkpointCommitted(monotonicMs());
        calculation_recovery=std::make_unique<TaskRecovery>(*calculation_task,
            TaskRecovery::Limits{1000,3000,checkpoint_max_age});
        if(!calculation_task->startFromSnapshot(0))throw std::runtime_error("BMS worker startup failed");
    }
    auto poll_receive=[&](){
        if(!receive_recovery || receive_operator)return;
        const auto event=receive_recovery->poll(monotonicMs());
        if(event==TaskRecovery::Event::None)return;
        std::cerr<<"CAN_RX_RECOVERY event="<<static_cast<unsigned>(event)
                 <<" attempts="<<receive_recovery->attempts()<<" failures="<<receive_recovery->failures()
                 <<" generation="<<receive_recovery->generation()<<" monotonic_ms="<<monotonicMs()
                 <<" frames="<<driver.receiveHealth().frames<<'\n';
        if(event==TaskRecovery::Event::Exhausted){
            std::cerr<<"ERR_WATCHDOG_MAX_RESTART task=can-rx attempts="<<receive_recovery->attempts()
                     <<" failures="<<receive_recovery->failures()<<'\n';
            if(!physical_feed)failsafe.watchdogRestartsFailed(soc_estimator.soc()*100.0f,last_calculation_sample.temperature_c);
            receive_operator=true;
            if(checkpoint_writer)save_state(last_committed_soh_elapsed);
        }else if(event==TaskRecovery::Event::StopDeadline || event==TaskRecovery::Event::InvalidSnapshot ||
                 event==TaskRecovery::Event::ClockError)receive_operator=true;
    };
    auto poll_calculation=[&](){
        poll_receive();
        if(!calculation_task || calculation_operator)return;
        const auto now=monotonicMs();
        if(now-calculation_checked>=1000){
            calculation_checked=now;
            if(calculation_inflight && now-calculation_started>=3000 &&
               calculation_recovery->state()==TaskRecovery::State::Idle){
                calculation_recovery->notifyTimeout(now);
                failsafe.inputUnavailable();
                std::cerr<<"BMS_RECOVERY timeout; stopping old task sampled_ms="<<calculation_started
                         <<" monotonic_ms="<<now<<'\n';
            }
        }
        const auto event=calculation_recovery->poll(now);
        if(event==TaskRecovery::Event::None)return;
        std::cerr<<"BMS_RECOVERY event="<<static_cast<unsigned>(event)
                 <<" attempts="<<calculation_recovery->attempts()
                 <<" failures="<<calculation_recovery->consecutiveFailures()
                 <<" generation="<<calculation_recovery->generation()<<" monotonic_ms="<<now<<'\n';
        if(event==TaskRecovery::Event::Started)calculation_inflight=false;
        if(event==TaskRecovery::Event::Exhausted){
            std::cerr<<"ERR_WATCHDOG_MAX_RESTART task=bms-calculation attempts="<<calculation_recovery->attempts()
                     <<" failures="<<calculation_recovery->consecutiveFailures()<<'\n';
            failsafe.watchdogRestartsFailed(soc_estimator.soc()*100.0f,last_calculation_sample.temperature_c);
            calculation_operator=true;
            save_state(last_committed_soh_elapsed);
        }else if(event==TaskRecovery::Event::StopDeadline || event==TaskRecovery::Event::InvalidSnapshot ||
                 event==TaskRecovery::Event::ClockError){
            calculation_operator=true; // never spawn duplicate or request whole-process restart
        }
    };
    WatchdogManager watchdog(1000, 3000);
    watchdog.start([](std::uint32_t count) {
        std::cerr << "Watchdog timeout count=" << count << '\n';
    });

    std::cout << "adaptive_ecu on " << interface_name
              << " sensor=" << sensor_mode
              << " secoc=" << (secoc_enabled ? "on" : "off") << '\n';
    std::cout<<"security protocol="<<(secoc_enabled ? protocol : "explicit-secoc-off")<<'\n';
    if (adc_worker) {
        std::cout << "ADS1115: A0 real -> pack 30..42V virtual; current "
                  << SensorSimulator::kHardwareCurrentA << "A and temperature "
                  << static_cast<int>(SensorSimulator::kHardwareTemperatureC)
                  << "C virtual. BMS TX paused until 3 new valid conversions.\n";
        adc_worker->start();
    }
    if(physical_config){
#ifdef __linux__
        const auto executable=std::filesystem::read_symlink("/proc/self/exe").parent_path()/"physical_battery_worker";
        physical_process=std::make_unique<PhysicalSensorProcess>(executable.string(),physical_config_path,physical_config->fingerprint);
#endif
        std::cout<<"Physical: INA219 voltage/current + DS18B20 temperature; no virtual BMS values. "
                    "SOC uses the explicitly selected prior/reference model; reference accuracy is unverified. SOH needs an independent capacity test. "
                    "Physical protection thresholds/cutoff and checkpoint recovery are not enabled.\n";
    }

    auto flush_state=[&](std::uint64_t sequence){
        const auto started=monotonicMs();
        while(true){
            const auto status=checkpoint_writer->status();
            if(status.committed>=sequence)return;
            if(status.failed>=sequence || monotonicMs()-started>=checkpoint_flush)
                throw std::runtime_error("checkpoint durable save failed or timed out; restart cancelled");
            watchdog.kick();pump_session();
            std::this_thread::sleep_for(std::chrono::milliseconds(2));
        }
    };
    std::uint64_t observed_commit=0,last_commit_at=monotonicMs();
    auto completed_cycle=[&](bool input_ready){
        if(supervisor_fd<0)return;
        const auto status=checkpoint_writer->status();
        if(status.committed!=observed_commit){observed_commit=status.committed;last_commit_at=monotonicMs();}
        std::uint8_t health=1|(input_ready ? 8 : 0);
        if(status.storageFailed())health|=2;
        if(status.requested>status.committed && monotonicMs()-last_commit_at>=checkpoint_max_age)health|=4;
        const auto sent=::write(supervisor_fd,&health,1);
        // Full pipe is observed as a timeout by the manager, never a blocking
        // send in the ECU loop. Other failures mean the owner disappeared.
        if(sent!=1 && errno!=EAGAIN && errno!=EWOULDBLOCK && errno!=EINTR)
            throw std::runtime_error("supervisor health pipe unavailable");
    };
    std::uint8_t last_status_quality=0,last_status_stage=0;
    auto publish_sensor_status=[&](){
        if(protection_publisher&&!physical_feed)
            protection_publisher->offer(*exchange,protection.body(instance),monotonicMs());
        auto input_quality=adc_worker ? adc_feed.quality() : SensorQuality::Valid;
        if(physical_feed){
            const auto v=physical_feed->values(monotonicMs());
            input_quality=(v.ina_quality==SensorQuality::Valid&&v.temperature_quality==SensorQuality::Valid) ?
                SensorQuality::Valid : v.ina_quality!=SensorQuality::Valid ? v.ina_quality : v.temperature_quality;
        }
        const auto quality=static_cast<std::uint8_t>(input_quality);
        const std::uint8_t stage=calculation_operator || receive_operator ? 5 :
            calculation_recovery && calculation_recovery->state()!=TaskRecovery::State::Idle ? 3 : 2;
        if(exchange && exchange->dataOpen() &&
           (last_status_stage!=stage || last_status_quality!=quality || status_generation!=exchange->generation() || monotonicMs()-status_sent>=1000)){
            std::vector<std::uint8_t> status(instance.begin(),instance.end());
            status.insert(status.end(),restart_operation.begin(),restart_operation.end());status.resize(56,0);
            status[32]=stage;status[33]=start_intent=="resume" ? 2 : 1;
            status[34]=quality;const auto risk=failsafe.exportState();
            status[35]=static_cast<std::uint8_t>(risk.state);status[36]=risk.reason!=FailSafeStateMachine::REASON_NONE;
            status[37]=static_cast<std::uint8_t>(risk.reason);
            if(physical_feed){status[35]=0xff;status[36]=status[37]=0;}
            if(checkpoint_writer){
                const auto storage=checkpoint_writer->status();
                status[38]=storage.storageFailed() ? 3 : storage.committed<storage.requested ? 1 : 0;
            }
            const auto uptime=monotonicMs()-process_started;
            for(unsigned i=0;i<8;++i)status[40+i]=static_cast<std::uint8_t>(uptime>>(56-8*i));
            for(unsigned i=0;i<4;++i)status[48+i]=static_cast<std::uint8_t>(checkpoint_age>>(24-8*i));
            status[52]=status[54]=start_intent=="resume";status[53]=quality==2;
            if(auto packet=exchange->makeDiagnostic(session::DiagnosticKind::NodeStatus,status)){
                send_frames(packet->frames);
                status_sent=monotonicMs();status_generation=exchange->generation();last_status_quality=quality;last_status_stage=stage;
            }
        }
    };
    auto reported_quality = adc_feed.quality();
    const auto soh_started = std::chrono::steady_clock::now();
    if(!physical_feed)std::cout << "SOH virtual capacity: initial=" << soh_estimator.initialCapacityAh()
              << "Ah source=" << (soh_profile_path.empty() ? "constant-full-health" : soh_profile_path)
              << " steps=" << soh_scenario.size() << '\n';
    std::uint64_t physical_sent_at=0,physical_generation=0,physical_logged_sequence=0;
    bool physical_process_failed=false;
    while (running) {
        const auto cycle_start = std::chrono::steady_clock::now();
#ifdef ECU_SENDER_CONTROL_FIXTURE
        const bool test_sender_paused=test_sender_gate.paused(monotonicMs());
#endif
        watchdog.kick();
        pump_session();

        if(physical_feed){
            for(const auto& sample:physical_process->poll())physical_feed->accept(sample,monotonicMs());
            if(physical_process->failed()){
                physical_feed->unavailable();
                if(!physical_process_failed){
                    physical_process_failed=true;
                    if(!physical_process->stop())throw std::runtime_error("physical reader unreclaimed; replacement prohibited");
                    std::cerr<<"Physical reader stopped; invalid sensor state is reported, no simulated fallback\n";
                }
            }
            const auto now=monotonicMs();const auto values=physical_feed->values(now);
            publish_sensor_status();
            if(exchange->dataOpen()&&
               (physical_generation!=exchange->generation()||now-physical_sent_at>=1000)){
                session::PhysicalMeasurement measurement;measurement.instance=instance;
                std::copy_n(physical_config->fingerprint.begin(),16,measurement.configuration.begin());
                measurement.sequence=values.sequence;measurement.voltage_v=values.voltage_v;measurement.current_a=values.current_a;
                measurement.temperature_c=values.temperature_c;measurement.soc_percent=values.soc_percent;measurement.soh_percent=values.soh_percent;
                measurement.ina_age_ms=values.ina_age_ms;measurement.temperature_age_ms=values.temperature_age_ms;
                measurement.ina_quality=static_cast<std::uint8_t>(values.ina_quality);
                measurement.temperature_quality=static_cast<std::uint8_t>(values.temperature_quality);
                measurement.soc_basis=physical_feed->socBasis();
                measurement.soh_basis=physical_config->measured_capacity_ah.has_value();
                measurement.observation_gap=physical_feed->meterState().observation_gap;
                measurement.nominal_capacity_mah=static_cast<std::uint32_t>(std::llround(physical_config->meter.nominal_capacity_ah*1000));
                measurement.max_interval_ms=physical_config->meter.max_interval_ms;
                if(physical_tx->pending()==0){
                    if(auto packet=exchange->makeDiagnostic(session::DiagnosticKind::PhysicalMeasurement,session::encodePhysicalMeasurement(measurement)))
                        physical_tx->offer(std::move(*packet),now);
                    physical_sent_at=now;physical_generation=exchange->generation();
                }
            }
            if(values.sequence!=physical_logged_sequence){
                physical_logged_sequence=values.sequence;
                const auto& state=physical_feed->meterState();
                std::cout<<std::setprecision(12)<<"{\"result\":\"PHYSICAL_SAMPLE\",\"sequence\":"<<values.sequence
                         <<",\"process_instance_id\":\""<<input_instance.str()<<'"'
                         <<",\"clock_id\":\""<<physical_clock_id<<'"'
                         <<",\"model_config_sha256\":\""<<physical_config->meter.model_calibration_id<<'"'
                         <<",\"sample_monotonic_ms\":";
                if(values.ina_age_ms!=0xffffffffu&&now>=values.ina_age_ms)std::cout<<now-values.ina_age_ms;else std::cout<<"null";
                std::cout
                         <<",\"voltage_v\":"<<(values.voltage_v?std::to_string(*values.voltage_v):"null")
                         <<",\"current_a\":"<<(values.current_a?std::to_string(*values.current_a):"null")
                         <<",\"temperature_c\":"<<(values.temperature_c?std::to_string(*values.temperature_c):"null")
                         <<",\"soc_estimate_percent\":"<<(values.soc_percent?std::to_string(*values.soc_percent):"null")
                         <<",\"soc_basis\":"<<physical_feed->socBasis()
                         <<",\"soc_update\":\""<<physical_feed->socUpdate()<<'"'
                         <<",\"soc_covariance\":";
                if(const auto covariance=physical_feed->socCovariance())std::cout<<*covariance;else std::cout<<"null";
                std::cout
                         <<",\"soh_estimate_percent\":"<<(values.soh_percent?std::to_string(*values.soh_percent):"null")
                         <<",\"ina_quality\":"<<unsigned(values.ina_quality)<<",\"temperature_quality\":"<<unsigned(values.temperature_quality)
                         <<",\"charged_ah\":"<<state.charged_ah<<",\"discharged_ah\":"<<state.discharged_ah
                         <<",\"signed_energy_wh\":"<<state.signed_energy_wh<<",\"observation_gap\":"<<(state.observation_gap?"true":"false")
                         <<",\"physical_accuracy_verified\":false}"<<std::endl;
            }
            poll_receive();completed_cycle(values.voltage_v.has_value()&&values.temperature_c.has_value());
            wait_cycle(cycle_start+std::chrono::milliseconds(100));continue;
        }

        if (adc_worker) {
            const auto snapshot = adc_worker->snapshot();
            const auto now_ms = monotonicMs();
            const auto pack_voltage = adc_feed.cycle(snapshot, now_ms);
            if (adc_feed.quality() != reported_quality) {
                reported_quality = adc_feed.quality();
                std::cout << "ADS1115 quality: " << qualityName(reported_quality)
                          << (pack_voltage ? "" : " (BMS TX paused)");
                if (reported_quality == SensorQuality::ErrorWithValue ||
                    reported_quality == SensorQuality::ErrorWithoutValue) {
                    if (adc_feed.errorCause() == HardwareSampleFeed::ErrorCause::Stale) {
                        std::cout << " reason=stale";
                        if (snapshot.last_valid_sequence > 0) {
                            std::cout << " age=" << (now_ms - snapshot.last_valid_ms) << "ms";
                        }
                    } else {
                        std::cout << ' ' << describeAdcError(snapshot);
                    }
                }
                std::cout << '\n';
            }
            if (!pack_voltage) {
                // ADS-1: no estimate, Fail-safe evaluation or frame from an invalid or
                // stale input. ADS-3: the estimator resumes from its last state.
                failsafe.inputUnavailable();
                if(calculation_recovery && !calculation_inflight)calculation_recovery->awaitingInput(monotonicMs());
                poll_calculation();
                publish_sensor_status();
                completed_cycle(false);
                wait_cycle(cycle_start + std::chrono::milliseconds(100));
                continue;
            }
            sensor.setHardwareVoltage(*pack_voltage);
        }

        poll_calculation();
        const double soh_elapsed = restored_soh_elapsed + std::chrono::duration<double>(cycle_start - soh_started).count();
        const float capacity = soh_scenario.capacityAt(soh_elapsed);
        SensorData sample;float soc_percent=0,soh_percent=0;
        if(calculation_task){
            const auto state=calculation_recovery->state();
            if(!calculation_operator && !calculation_inflight &&
               (state==TaskRecovery::State::Idle || state==TaskRecovery::State::AwaitingHeartbeat)){
                calculation_started=monotonicMs();
                calculation_inflight=calculation_task->submit(
                    BmsCalculation{sensor,soc_estimator,soh_estimator,capacity,calculation_started});
            }
            std::optional<BmsCalculation> result;
            while(running && !calculation_operator && std::chrono::steady_clock::now()<cycle_start+std::chrono::milliseconds(100)){
                pump_session();poll_calculation();
                result=calculation_task->takeCompleted();
                if(result)break;
                if(!calculation_inflight)break;
                std::this_thread::sleep_for(std::chrono::milliseconds(2));
            }
            if(result)calculation_inflight=false;
            const auto now=monotonicMs();
            bool input_fresh=result && now>=result->sampled_at_ms &&
                now-result->sampled_at_ms<=HardwareSampleFeed::kFreshnessMs;
            if(input_fresh && adc_worker){
                const auto current=adc_worker->snapshot();
                input_fresh=current.last_valid_sequence>current.last_error_sequence &&
                    now>=current.last_valid_ms && now-current.last_valid_ms<=HardwareSampleFeed::kFreshnessMs;
            }
            if(!input_fresh){
                failsafe.inputUnavailable();publish_sensor_status();completed_cycle(false);
                wait_cycle(cycle_start+std::chrono::milliseconds(100));continue;
            }
            sensor=std::move(result->sensor);soc_estimator=std::move(result->ekf);soh_estimator=std::move(result->soh);
            sample=result->sample;soc_percent=result->soc_percent;soh_percent=result->soh_percent;
            calculation_task->checkpointCommitted(now);
        }else{
            sample=sensor.next();
            soc_percent=soc_estimator.update(.1f,sample.current_a,sample.voltage_v)*100.0f;
            soh_estimator.recordCycle(capacity);soh_percent=soh_estimator.soh()*100.0f;
        }
        last_calculation_sample=sample;
        last_committed_soh_elapsed=soh_elapsed;

        failsafe.evaluate(soc_percent, sample.temperature_c, monotonicMs());
        if(recovery_requested && monotonicMs()-checkpoint_submitted_at>=checkpoint_period)
            save_state(soh_elapsed);
        publish_sensor_status();

#ifdef ECU_SENDER_CONTROL_FIXTURE
        if(!test_sender_paused)
#endif
        middleware->publishBms({
            soc_percent,
            soh_percent,
            sample.voltage_v,
            sample.current_a,
            sample.temperature_c,
        });

        completed_cycle(true);
        wait_cycle(cycle_start + std::chrono::milliseconds(100));
    }

    if(calculation_task)calculation_task->requestStop();
    if(recovery_requested)
        flush_state(save_state(restored_soh_elapsed+std::chrono::duration<double>(std::chrono::steady_clock::now()-soh_started).count()));
    if (adc_worker) adc_worker->stop();
    if(physical_process&&!physical_process->stop())throw std::runtime_error("physical reader not reclaimed; no replacement permitted");
    watchdog.stop();
    driver.close();
    std::cout << "adaptive_ecu stopped\n";
    return 0;
}

#ifndef ECU_TASK_FAULT_FIXTURE
int main(int argc,char** argv){
    try{return runMain(argc,argv);}
    catch(const std::exception& error){std::cerr<<"adaptive_ecu stopped: "<<error.what()<<'\n';return 2;}
}

#endif
