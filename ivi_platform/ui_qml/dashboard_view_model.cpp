#include "dashboard_view_model.h"

#include <QMetaObject>
#include <QThread>
#include <QSettings>
#include <QDateTime>
#include <QUuid>
#include <QJsonArray>
#include <QRegularExpression>

#include <chrono>
#include <algorithm>
#include <limits>

namespace {
QJsonObject protectionDetails(const capstone::session_v2::DiagnosticMessage& message){
    using namespace capstone::session_v2;
    if(message.kind!=DiagnosticKind::ProtectionStatus || message.sender_id!=0x302 ||
       !validDiagnosticBody(0x302,message.kind,message.body))return {};
    auto hex=[](const auto& b,unsigned at,unsigned size){return QString::fromLatin1(
        QByteArray(reinterpret_cast<const char*>(b.data()+at),size).toHex());};
    const auto& b=message.body;std::uint32_t revision=0;
    for(unsigned i=52;i<56;++i)revision=(revision<<8)|b[i];
    QJsonObject result{{"body_hex",hex(b,0,56)},{"instance_id",hex(b,0,16)},
        {"lineage_id",hex(b,16,16)},{"state",b[48]},{"reason",b[49]},
        {"phase",b[50]},{"revision",QString::number(revision)},
        {"checkpoint_resumed",bool(b[51]&1)},{"state_confirmed",true},
        {"session_id",hex(message.session_id,0,16)},{"sequence",QString::number(message.sequence)},
        {"received_monotonic_ms",QString::number(message.received_ms)}};
    if(b[50])result.insert("incident_id",hex(b,32,16));
    return result;
}
bool validProtectionRecord(const QJsonObject& record){
    using namespace capstone::session_v2;
    if(record.value("category").toString()!=QStringLiteral("protection-status") ||
       record.value("event_id").toString().isEmpty() || record.value("event_id").toString().size()>128)return false;
    const auto p=record.value("ecu_protection").toObject();
    const QRegularExpression hex32(QStringLiteral("^[0-9a-f]{32}$")),hex112(QStringLiteral("^[0-9a-f]{112}$"));
    if(!hex32.match(p.value("session_id").toString()).hasMatch() ||
       !hex112.match(p.value("body_hex").toString()).hasMatch())return false;
    bool ok=false;const auto sequence=p.value("sequence").toString().toULongLong(&ok);
    if(!ok || sequence>std::numeric_limits<std::uint32_t>::max() || QString::number(sequence)!=p.value("sequence").toString())return false;
    const auto received=p.value("received_monotonic_ms").toString().toULongLong(&ok);
    if(!ok || QString::number(received)!=p.value("received_monotonic_ms").toString())return false;
    const auto raw=QByteArray::fromHex(p.value("body_hex").toString().toLatin1());
    DiagnosticMessage message{DiagnosticKind::ProtectionStatus,static_cast<std::uint32_t>(sequence),0x302,{},
        std::vector<std::uint8_t>(raw.begin(),raw.end()),received,received};
    const auto session=QByteArray::fromHex(p.value("session_id").toString().toLatin1());
    std::copy(session.begin(),session.end(),message.session_id.begin());
    const auto expected=protectionDetails(message);
    if(expected.isEmpty() || expected!=p)return false;
    const auto link=record.value("protection_link").toObject();
    if(link.contains("high_water_revision")){
        const auto high=link.value("high_water_revision").toString().toULongLong(&ok);
        if(!ok || high>std::numeric_limits<std::uint32_t>::max() ||
           QString::number(high)!=link.value("high_water_revision").toString() ||
           high<p.value("revision").toString().toULongLong())return false;
    }
    return true;
}
}

DashboardViewModel::DashboardViewModel(QObject* parent) : QObject(parent) {
    event_source_instance_=QUuid::createUuid().toString(QUuid::WithoutBraces);
    dark_mode_ = QSettings(QStringLiteral("Capstone"), QStringLiteral("IviDashboard"))
                     .value(QStringLiteral("darkMode"), true).toBool();
    // Keep handshake retries readable without changing authentication or data
    // validity. Once reported, a connection issue stays until actual recovery.
    connection_check_timer_.setSingleShot(true);
    connection_check_timer_.setInterval(10000);
    connection_check_timer_.setTimerType(Qt::PreciseTimer);
    connect(&connection_check_timer_,&QTimer::timeout,this,[this]{
        connection_check_needed_=true;
        emit dataChanged();
    });
    // Debounce notices only. Channel validity and '--' display remain immediate.
    sensor_loss_timer_.setSingleShot(true);
    sensor_loss_timer_.setInterval(2000);
    sensor_loss_timer_.setTimerType(Qt::PreciseTimer);
    sensor_recovery_timer_.setSingleShot(true);
    sensor_recovery_timer_.setInterval(5000);
    sensor_recovery_timer_.setTimerType(Qt::PreciseTimer);
    connect(&sensor_loss_timer_,&QTimer::timeout,this,[this]{
        if(!physicalMode() || !sensor_missing_mask_ || sensor_incident_active_)return;
        sensor_incident_active_=true;
        recordEvent(missingSensorNames()+QStringLiteral(" 측정 확인 필요"),QStringLiteral("sensor-input-lost"));
        presentPopup(QStringLiteral("센서를 확인해 주세요"),missingSensorNames()+
            QStringLiteral("의 새 측정값을 2초 이상 확인하지 못했습니다. 연결과 센서 상태를 확인해 주세요."),
            QStringLiteral("warning"),50,PopupDomain::Sensor);
        emit dataChanged();
    });
    connect(&sensor_recovery_timer_,&QTimer::timeout,this,[this]{
        if(!physicalMode() || sensor_missing_mask_ || !sensor_incident_active_ ||
           snapshot_.physical_measurement->sequence<=sensor_recovery_sequence_)return;
        sensor_incident_active_=false;
        recordEvent(QStringLiteral("센서 측정 회복 확인"),QStringLiteral("sensor-input-recovered"));
        // Recovery updates an unread notice; it never reopens a closed one or
        // replaces an unrelated, higher-priority warning.
        if(popup_visible_ && popup_domain_==PopupDomain::Sensor)
            presentPopup(QStringLiteral("센서 측정이 복구됐습니다"),
                QStringLiteral("전압·전류·온도의 새 측정값이 5초 동안 정상적으로 들어왔습니다."),
                QStringLiteral("success"),50,PopupDomain::Sensor);
        emit dataChanged();
    });
}

void DashboardViewModel::updateConnectionNotice(){
    const auto& stage=snapshot_.connection_stage;
    if(!snapshot_.session_protocol || stage=="connected" || stage=="program-restored" ||
       stage=="task-restoring" || stage=="operator-required" ||
       stage=="restart-announced" || stage=="restoring"){
        connection_check_timer_.stop();connection_check_needed_=false;
    }else if(stage=="fault" && !connection_check_needed_ && !connection_check_timer_.isActive()){
        connection_check_timer_.start();
    }
}

QString DashboardViewModel::missingSensorNames() const {
    const QStringList names{QStringLiteral("전압"),QStringLiteral("전류"),QStringLiteral("온도")};
    QStringList missing;
    for(unsigned i=0;i<3;++i)if(sensor_missing_mask_&(1u<<i))missing.append(names[i]);
    return missing.join(QStringLiteral("·"));
}

void DashboardViewModel::updatePhysicalSensorNotice(){
    if(!physicalMode())return;
    sensor_missing_mask_=0;
    const auto& m=*snapshot_.physical_measurement;
    for(unsigned i=0;i<3;++i){
        const unsigned bit=1u<<i;
        if(snapshot_.physical_valid[i])sensor_seen_mask_|=bit;
        const auto quality=i<2?m.ina_quality:m.temperature_quality;
        // Warm-up is not a failure. Explicit failed/recovering quality must
        // still warn even when this channel has never produced a valid value.
        if(!snapshot_.physical_valid[i] && ((sensor_seen_mask_&bit) || (quality>=2&&quality<=6)))
            sensor_missing_mask_|=bit;
    }
    if(sensor_missing_mask_){
        sensor_recovery_timer_.stop();
        if(!sensor_incident_active_ && !sensor_loss_timer_.isActive())sensor_loss_timer_.start();
    }else{
        sensor_loss_timer_.stop();
        const bool all_valid=snapshot_.physical_valid[0]&&snapshot_.physical_valid[1]&&snapshot_.physical_valid[2];
        if(sensor_incident_active_ && all_valid && !sensor_recovery_timer_.isActive()){
            sensor_recovery_sequence_=m.sequence;sensor_recovery_timer_.start();
        }
        if(!all_valid)sensor_recovery_timer_.stop();
    }
}

void DashboardViewModel::setDarkMode(bool value) {
    if (dark_mode_ == value) return;
    dark_mode_ = value;
    QSettings(QStringLiteral("Capstone"), QStringLiteral("IviDashboard"))
        .setValue(QStringLiteral("darkMode"), value);
    emit themeChanged();
}

void DashboardViewModel::setHistoryStorageStatus(const QString& message){
    if(history_storage_status_==message)return;history_storage_status_=message;
    if(message.contains(QStringLiteral("실패"))||message.contains(QStringLiteral("중단"))||message.contains(QStringLiteral("일부")))
        presentPopup(QStringLiteral("이벤트 기록을 확인해 주세요"),message+QStringLiteral(". 배터리 정보와 경고 표시는 계속 동작합니다."),QStringLiteral("warning"),50,PopupDomain::Storage);
    emit dataChanged();
}
void DashboardViewModel::restoreEventHistory(const QStringList& history){
    if(history_loaded_)return;history_loaded_=true;
    events_.append(history);while(events_.size()>100)events_.removeLast();emit dataChanged();
}
void DashboardViewModel::expectProtectionHistory(){protection_history_ready_=false;}
void DashboardViewModel::restoreProtectionHistory(const QJsonObject& record,bool gap_possible){
    if(protection_history_ready_)return;
    committed_protection_record_=validProtectionRecord(record)?record:QJsonObject{};
    protection_history_gap_=gap_possible || (!record.isEmpty()&&committed_protection_record_.isEmpty())||
        committed_protection_record_.value("protection_link").toObject().value("gap_possible").toBool();
    protection_history_ready_=true;recordProtectionUpdate();
}
void DashboardViewModel::protectionCommitted(const QJsonObject& record){
    if(validProtectionRecord(record)){
        committed_protection_record_=record;
        protection_history_gap_|=record.value("previous_gap_possible").toBool()||
            record.contains("records_lost_before")||record.value("protection_link").toObject().value("gap_possible").toBool();
    }
}
QJsonObject DashboardViewModel::protectionLink(const QJsonObject& current)const{
    const auto previous=committed_protection_record_.value("ecu_protection").toObject();
    const auto prior_link=committed_protection_record_.value("protection_link").toObject();
    const auto revision=current.value("revision").toString().toULongLong();
    quint64 high=revision;
    bool gap=protection_history_gap_||protection_observation_gap_;
    QJsonObject result{{"status","unlinked"}};
    if(!previous.isEmpty()){
        const bool same_lineage=current.value("lineage_id")==previous.value("lineage_id");
        const bool same_event=same_lineage&&current.value("incident_id")==previous.value("incident_id");
        const bool same_instance=current.value("instance_id")==previous.value("instance_id");
        if(same_event && (same_instance || current.value("checkpoint_resumed").toBool())){
            const auto previous_revision=previous.value("revision").toString().toULongLong();
            high=std::max({revision,previous_revision,prior_link.value("high_water_revision").toString().toULongLong()});
            const bool changed_meaning=revision==previous_revision &&
                (current.value("state")!=previous.value("state") || current.value("reason")!=previous.value("reason") ||
                 current.value("phase")!=previous.value("phase"));
            const bool rollback=revision<high||changed_meaning;
            gap|=prior_link.value("gap_possible").toBool()||rollback||revision>previous_revision+1;
            result.insert("status",rollback?"checkpoint-history-gap":!same_instance?"resumed":
                current.value("session_id")!=previous.value("session_id")?"reconnected":"updated");
            result.insert("previous_event_id",committed_protection_record_.value("event_id"));
            result.insert("previous_revision",previous.value("revision"));
            // A restored checkpoint cannot prove what occurred before its last durable write.
            gap|=!same_instance;
        }else if(!same_lineage || !same_event){
            result.insert("status",same_lineage?"new-incident":"new-lineage");
            result.insert("prior_record_id",committed_protection_record_.value("event_id"));
            result.insert("prior_event_end_unconfirmed",previous.value("phase").toInt()==1);
        }else gap=true; // same identifiers without verified process restoration
    }
    result.insert("high_water_revision",QString::number(high));result.insert("gap_possible",gap);
    return result;
}
void DashboardViewModel::recordProtectionUpdate(){
    if(!protection_history_ready_)return;
    if(!snapshot_.protection_confirmed || !snapshot_.ecu_protection_status){
        if(protection_was_confirmed_){protection_notice_signature_.clear();protection_observation_gap_=true;}
        protection_was_confirmed_=false;return;
    }
    const auto details=protectionDetails(*snapshot_.ecu_protection_status);
    if(details.isEmpty())return;
    protection_was_confirmed_=true;
    const auto signature=details.value("body_hex").toString()+details.value("session_id").toString();
    if(signature==protection_notice_signature_)return;
    protection_notice_signature_=signature;
    const auto link=protectionLink(details).value("status").toString();
    const auto text=link=="resumed"?QStringLiteral("이전 배터리 보호 기록 연결"):
        link=="checkpoint-history-gap"?QStringLiteral("마지막 저장 시점의 보호 기록 복원 · 일부 구간 확인 필요"):
        details.value("phase").toInt()==2?QStringLiteral("배터리 보호 상태 정상 복귀 확인"):
        details.value("phase").toInt()==1?QStringLiteral("배터리 경고·보호 상태 확인"):QStringLiteral("배터리 보호 상태 확인");
    recordEvent(text,QStringLiteral("protection-status"));
}
void DashboardViewModel::recordEvent(const QString& text,const QString& category) {
    const auto now=QDateTime::currentDateTimeUtc();
    const auto display=now.toLocalTime().toString(QStringLiteral("yyyy-MM-dd HH:mm:ss"))+QStringLiteral("  ")+text;
    events_.prepend(display);while(events_.size()>100)events_.removeLast();
    QJsonArray incidents;
    for(const auto& id:snapshot_.security_incident_ids)if(id)
        incidents.append(QString::fromLatin1(QByteArray(reinterpret_cast<const char*>(id->data()),16).toHex()));
    QJsonObject event{{"schema",1},{"event_id",QUuid::createUuid().toString(QUuid::WithoutBraces)},
        {"source_instance",event_source_instance_},{"origin","ivi-dashboard"},{"category",category},
        {"recorded_utc",now.toString(Qt::ISODateWithMs)},{"display",display},{"summary",text},
        {"session_generation",QString::number(snapshot_.session_generation)},
        {"connection_stage",QString::fromStdString(snapshot_.connection_stage)},
        {"battery_state",snapshot_.vehicle.fail_safe_state},{"battery_reason",snapshot_.vehicle.fail_safe_reason},
        {"observation_ready",snapshot_.security_observation_ready},{"incident_ids",incidents}};
    QJsonArray refusal_ids;
    for(const auto& id:snapshot_.incident_rejection_ids)if(id)refusal_ids.append(QString::fromLatin1(QByteArray(reinterpret_cast<const char*>(id->data()),16).toHex()));
    event.insert("incident_rejection_ids",refusal_ids);
    // Keep the type and incident/rejection association explicit in persisted
    // records. Compact ID arrays alone lose their original optional slots.
    const QStringList types{QStringLiteral("fuzzy"),QStringLiteral("replay"),
                            QStringLiteral("spoofing"),QStringLiteral("flooding")};
    QJsonArray typed_incidents;
    for(unsigned type=0;type<snapshot_.security_incident_ids.size();++type){
        const auto& incident=snapshot_.security_incident_ids[type];
        if(!incident)continue;
        QJsonObject item{{"attack_type",types.at(type)},
            {"incident_id",QString::fromLatin1(QByteArray(reinterpret_cast<const char*>(incident->data()),16).toHex())}};
        const auto& rejection=snapshot_.incident_rejection_ids[type];
        if(rejection)item.insert("rejection_id",QString::fromLatin1(QByteArray(reinterpret_cast<const char*>(rejection->data()),16).toHex()));
        typed_incidents.append(item);
    }
    event.insert("typed_incidents",typed_incidents);
    auto hex=[](const auto& bytes,unsigned at,unsigned size){
        return QString::fromLatin1(QByteArray(reinterpret_cast<const char*>(bytes.data()+at),size).toHex());
    };
    auto present=[](const auto& bytes,unsigned at){
        return std::any_of(bytes.begin()+at,bytes.begin()+at+16,[](auto value){return value!=0;});
    };
    auto envelope=[&](const auto& message){
        return QJsonObject{{"session_id",hex(message.session_id,0,16)},
            {"sequence",QString::number(message.sequence)},
            {"received_monotonic_ms",QString::number(message.received_ms)}};
    };
    using namespace capstone::session_v2;
    if(snapshot_.physical_measurement){
        const auto& m=*snapshot_.physical_measurement;
        event.insert("physical_source",QJsonObject{{"sequence",QString::number(m.sequence)},
            {"configuration_id",hex(m.configuration,0,16)},{"soc_basis",m.soc_basis},{"soh_basis",m.soh_basis},
            {"observation_gap",m.observation_gap},{"physical_accuracy_verified",false}});
    }
    if(snapshot_.ecu_node_status && snapshot_.ecu_node_status->kind==DiagnosticKind::NodeStatus &&
       validDiagnosticBody(0x302,DiagnosticKind::NodeStatus,snapshot_.ecu_node_status->body)){
        const auto& node=*snapshot_.ecu_node_status;const auto& body=node.body;
        auto process=envelope(node);
        process.insert("instance_id",hex(body,0,16));
        if(present(body,16))process.insert("restart_operation_id",hex(body,16,16));
        process.insert("stage",body[32]);process.insert("start_intent",body[33]);
        process.insert("calculation_restored",bool(body[52]));
        process.insert("input_ready",bool(body[53]));process.insert("risk_restored",bool(body[54]));
        event.insert("ecu_process",process);
    }
    if(snapshot_.ecu_restart_plan && snapshot_.ecu_restart_plan->kind==DiagnosticKind::RestartPlan &&
       validDiagnosticBody(0x302,DiagnosticKind::RestartPlan,snapshot_.ecu_restart_plan->body)){
        const auto& message=*snapshot_.ecu_restart_plan;const auto& body=message.body;
        auto plan=envelope(message);
        plan.insert("instance_id",hex(body,0,16));plan.insert("operation_id",hex(body,16,16));
        if(present(body,32))plan.insert("protection_incident_id",hex(body,32,16));
        event.insert("ecu_restart_plan",plan);
    }
    if(snapshot_.local_rejection_record){
        const auto& body=*snapshot_.local_rejection_record;
        event.insert("local_rejection_id",QString::fromLatin1(QByteArray(reinterpret_cast<const char*>(body.data()+16),16).toHex()));
        event.insert("local_rejection_reason",body[32]);
    }
    if(snapshot_.protection_confirmed && snapshot_.ecu_protection_status){
        const auto details=protectionDetails(*snapshot_.ecu_protection_status);
        if(!details.isEmpty()){
            event.insert("ecu_protection",details);
            if(category==QStringLiteral("protection-status"))event.insert("protection_link",protectionLink(details));
        }
    }
    emit eventRecorded(event);
}

void DashboardViewModel::presentPopup(const QString& title, const QString& description,
                                     const QString& kind, int priority,PopupDomain domain) {
    // A lower-priority report cannot cover an already visible battery danger.
    // Its full event still remains in the status cards and history.
    if (popup_visible_ && priority < popup_priority_) return;
    popup_title_ = title; popup_description_ = description; popup_kind_ = kind;
    popup_priority_ = priority; popup_visible_ = true;popup_domain_=domain;
    if(domain==PopupDomain::Battery)popup_battery_state_=snapshot_.vehicle.fail_safe_state;
    emit popupChanged();
}

void DashboardViewModel::dismissPopup() {
    popup_visible_ = false;
    emit popupChanged(); // no service acknowledgement, counter reset or safety change
}

QString DashboardViewModel::statusTitle() const {
    if(physicalMode()){
        if(!snapshot_.physical_measurement->sequence)return QStringLiteral("센서 준비 중");
        if(!measurementsAvailable())return QStringLiteral("센서·연결 확인 필요");
        return voltageAvailable()&&currentAvailable()&&temperatureAvailable() ? QStringLiteral("실제 배터리 측정 중") : QStringLiteral("일부 센서 확인 필요");
    }
    if (snapshot_.vehicle.fail_safe_state == 3) {
        if(snapshot_.vehicle.valid && !snapshot_.vehicle.stale && !sensorStateWarning() && snapshot_.vehicle.temperature_c<=55)
            return QStringLiteral("온도 회복 확인 중");
        return QStringLiteral("과열 보호 중");
    }
    if (snapshot_.vehicle.fail_safe_state == 2) return QStringLiteral("배터리 위험 상태");
    if (snapshot_.vehicle.fail_safe_state == 1) return QStringLiteral("배터리 경고");
    if (sensorStateWarning()) return QStringLiteral("센서 확인 필요");
    if (!valid()) return QStringLiteral("배터리 정보 대기");
    if (stale()) return QStringLiteral("연결 확인 필요");
    if (authenticationError()) return QStringLiteral("데이터 확인 필요");
    return fail_safe_known_ ? QStringLiteral("정상") : QStringLiteral("배터리 정보 수신 중");
}

QString DashboardViewModel::connectionLabel()const{
    if(!snapshot_.session_protocol)return !valid() ? QStringLiteral("연결 대기") : stale() ? QStringLiteral("마지막 확인값") : QStringLiteral("현재 수신값");
    const auto& stage=snapshot_.connection_stage;
    if(stage=="task-restoring")return QStringLiteral("계산 작업 복구 중…");
    if(stage=="operator-required")return QStringLiteral("ECU 점검 필요");
    if(stage=="restart-announced")return QStringLiteral("ECU 재시작 중…");
    if(stage=="restoring")return QStringLiteral("ECU 연결 복구 중…");
    if(stage=="program-restored")return QStringLiteral("ECU 프로그램 복구 완료");
    if(connection_check_needed_)return QStringLiteral("연결 확인 필요");
    if(stage=="authenticating" || stage=="fault")return QStringLiteral("연결 확인 중");
    if(stage=="synchronizing")return QStringLiteral("배터리 상태 확인 중");
    if(stage=="waiting-data")return QStringLiteral("새 배터리 정보 대기");
    if(stage=="connected")return QStringLiteral("현재 수신값");
    return QStringLiteral("연결 대기");
}
QStringList DashboardViewModel::floodingMetrics()const{
    QString rate=QStringLiteral("ECU 관찰 전송률: 미측정");
    if(snapshot_.ecu_metrics && snapshot_.ecu_metrics_fresh){
        const auto& body=snapshot_.ecu_metrics->body;
        auto u32=[&](unsigned at){return (quint32(body[at])<<24)|(quint32(body[at+1])<<16)|(quint32(body[at+2])<<8)|body[at+3];};
        rate=QStringLiteral("ECU 관찰 전송률: %1 프레임/초").arg(double(u32(20))*1000/u32(16),0,'f',1);
    }
    if(snapshot_.security_observation_ready && snapshot_.ecu_observed_fps)
        rate=QStringLiteral("ECU IDS 관찰: %1 프레임/초").arg(*snapshot_.ecu_observed_fps,0,'f',1);
    const auto& metrics=snapshot_.ivi_publication_metrics;
    const auto count=snapshot_.session_protocol ? QString::number(metrics.authenticated_bms)+QStringLiteral("건 (현재 세션)") : QStringLiteral("미측정");
    const auto age=snapshot_.session_bms_ready ? QString::number(snapshot_.last_good_age_ms)+QStringLiteral(" ms 전") : QStringLiteral("수신 대기");
    QString intervals=QStringLiteral("미측정");
    if(metrics.mean_interval_us && metrics.max_interval_us)
        intervals=QStringLiteral("평균 %1 / 최대 %2 ms (현재 세션)").arg(*metrics.mean_interval_us/1000,0,'f',1).arg(double(*metrics.max_interval_us)/1000,0,'f',1);
    return {rate,QStringLiteral("IVI 인증 수신: ")+count,QStringLiteral("마지막 정상 수신: ")+age,
        QStringLiteral("IVI 반영 간격: ")+intervals,QStringLiteral("ECU 수신 큐 유실: ")+(snapshot_.ecu_observed_drops ? QString::number(*snapshot_.ecu_observed_drops)+QStringLiteral("건 (최근 관찰 구간)") : QStringLiteral("미측정"))+QStringLiteral(" · IVI 수신 큐 유실: ")+(snapshot_.ivi_socket_drops ?
            QString::number(*snapshot_.ivi_socket_drops)+QStringLiteral("건 (현재 소켓)") : QStringLiteral("미측정"))+
            QStringLiteral(" · 인터페이스 오류: 미측정")};
}

QStringList DashboardViewModel::incidentTreatments()const{
    QStringList result;
    for(unsigned i=0;i<4;++i)if(snapshot_.observed_condition_mask&(1u<<i)){
        const auto name=QString::fromLatin1(ivi::attackTypeName(i+1));
        result.append(name+(snapshot_.incident_rejection_ids[i] ? QStringLiteral(" · 관련 데이터의 수신 거부 확인") :
            i==3 ? QStringLiteral(" · 통신 상태와 정상 데이터 수신을 확인 중") : QStringLiteral(" · 관련 데이터 처리 결과 확인 중")));
    }
    return result;
}
QString DashboardViewModel::securityTitle()const{
    if(snapshot_.session_protocol && snapshot_.observed_condition_mask){
        QStringList names;
        const QStringList types{QStringLiteral("Fuzzy"),QStringLiteral("Replay"),QStringLiteral("Spoofing"),QStringLiteral("Flooding")};
        for(int i=0;i<4;++i)if(snapshot_.observed_condition_mask&(1u<<i))names.append(types[i]);
        return names.join(QStringLiteral(" / "));
    }
    if(snapshot_.session_protocol && (!snapshot_.security_observation_ready || snapshot_.observed_condition_mask) && active_attack_types_.isEmpty())
        return QStringLiteral("보안 감시 확인 중");
    return security_title_;
}
QString DashboardViewModel::securityDescription()const{
    if(snapshot_.session_protocol && snapshot_.observed_condition_mask){
        if(snapshot_.unreconciled_incident_mask)
            return QStringLiteral("이전 감시에서 탐지된 기록입니다. 새 감시에서 현재 상태를 확인하고 있습니다.");
        if(!snapshot_.security_observation_ready)
            return QStringLiteral("마지막으로 탐지된 공격입니다. 현재 감시 상태를 확인하고 있습니다.");
        return QStringLiteral("공격 징후가 탐지됐습니다. 관련 데이터의 처리 결과를 확인하고 있습니다.");
    }
    if(snapshot_.session_protocol && (!snapshot_.security_observation_ready || snapshot_.observed_condition_mask) && active_attack_types_.isEmpty())
        return QStringLiteral("탐지기의 연결 상태를 확인하고 있습니다.");
    return security_description_;
}

QString DashboardViewModel::sohHint() const {
    if(!physicalMode())return {};
    if(!snapshot_.physical_measurement->soh_basis)return QStringLiteral("용량 시험 후 표시됩니다");
    return sohAvailable() ? QStringLiteral("측정한 용량을 기준으로 계산했습니다") : QStringLiteral("새 용량 정보를 확인하고 있습니다");
}

QString DashboardViewModel::statusDescription() const {
    if(physicalMode())return physicalObservationGap() ?
        QStringLiteral("측정이 끊긴 구간이 있습니다.\n부하를 자동 차단하지 않습니다.") :
        QStringLiteral("실제 센서로 측정하고 있습니다.\n부하를 자동 차단하지 않습니다.");
    switch (snapshot_.vehicle.fail_safe_reason) {
    case 1: if (snapshot_.vehicle.fail_safe_state) return QStringLiteral("배터리 잔량이 부족합니다. 충전이 필요합니다."); break;
    case 2: if (snapshot_.vehicle.fail_safe_state) return QStringLiteral("잔량이 매우 낮습니다. 배터리를 점검해 주세요."); break;
    case 3: case 4: if (snapshot_.vehicle.fail_safe_state == 3) {
        if(!snapshot_.vehicle.valid || snapshot_.vehicle.stale || sensorStateWarning())
            return QStringLiteral("현재 온도를 확인할 수 없어 보호 상태를 유지합니다.");
        if(snapshot_.vehicle.temperature_c<=55)return QStringLiteral("온도가 안정적으로 유지되는지 확인하고 있습니다.");
        return QStringLiteral("온도가 내려가기를 기다리고 있습니다.");
    }
        if (snapshot_.vehicle.fail_safe_state) return QStringLiteral("배터리 온도가 높습니다. 점검이 필요합니다."); break;
    case 7: if (snapshot_.vehicle.fail_safe_state) return QStringLiteral("시스템 작업 복구에 실패했습니다. 점검이 필요합니다."); break;
    }
    if (sensorStateWarning()) return measurementsAvailable()
        ? QStringLiteral("센서를 확인하고 있습니다. 표시된 수치는 마지막 정상 측정값입니다.")
        : QStringLiteral("센서를 확인하고 있습니다. 정상 측정이 시작되면 배터리 정보를 표시합니다.");
    if (!valid()) return QStringLiteral("배터리 정보를 불러오는 중입니다.");
    if (stale()) return QStringLiteral("마지막 확인값입니다. 연결을 확인해 주세요.");
    if (authenticationError()) return QStringLiteral("받은 데이터의 안전성을 확인할 수 없습니다.");
    return QStringLiteral("배터리 정보를 받고 있습니다.");
}

bool DashboardViewModel::valid() const { return snapshot_.vehicle.valid; }
bool DashboardViewModel::stale() const { return snapshot_.vehicle.stale; }
double DashboardViewModel::soc() const { return snapshot_.vehicle.soc_percent; }
QString DashboardViewModel::socBand() const {
    if (!socAvailable()) {
        return QStringLiteral("unavailable");
    }
    if (snapshot_.vehicle.soc_percent < 20.0) {
        return QStringLiteral("low");
    }
    if (snapshot_.vehicle.soc_percent < 50.0) {
        return QStringLiteral("medium");
    }
    return QStringLiteral("high");
}
double DashboardViewModel::soh() const { return snapshot_.vehicle.soh_percent; }
double DashboardViewModel::voltage() const { return snapshot_.vehicle.voltage_v; }
double DashboardViewModel::current() const { return snapshot_.vehicle.current_a; }
double DashboardViewModel::temperature() const { return snapshot_.vehicle.temperature_c; }
bool DashboardViewModel::measurementsAvailable() const {
    if(physicalMode())return snapshot_.physical_valid[0]||snapshot_.physical_valid[1]||snapshot_.physical_valid[2];
    const auto sensor_state = snapshot_.vehicle.sensor_state;
    return snapshot_.vehicle.valid && sensor_state != 1U && sensor_state != 3U &&
           sensor_state != 5U && sensor_state <= 6U;
}
QString DashboardViewModel::sensorState() const {
    if(physicalMode())return voltageAvailable()&&currentAvailable()&&temperatureAvailable() ?
        QStringLiteral("실제 센서 측정 중") : QStringLiteral("센서 준비·상태 확인 중");
    switch(snapshot_.vehicle.sensor_state){
    case 1:return QStringLiteral("센서 준비 중");
    case 2:return QStringLiteral("정상 측정 중");
    case 3:return QStringLiteral("센서 연결 확인 필요");
    case 4:return QStringLiteral("센서 오류 · 마지막 정상값");
    case 5:return QStringLiteral("센서 회복 확인 중");
    case 6:return QStringLiteral("센서 회복 중 · 마지막 정상값");
    default:return QString::fromLatin1(ivi::sensorStateName(snapshot_.vehicle.sensor_state));
    }
}
bool DashboardViewModel::sensorStateWarning() const {
    if(physicalMode())return !voltageAvailable()||!currentAvailable()||!temperatureAvailable();
    return snapshot_.vehicle.sensor_state > 0U && snapshot_.vehicle.sensor_state != 2U;
}
bool DashboardViewModel::sensorUsesLastGood() const {
    if(physicalMode())return false; // invalid physical channels display --
    return snapshot_.vehicle.valid && (snapshot_.vehicle.sensor_state == 4U || snapshot_.vehicle.sensor_state == 6U);
}
qulonglong DashboardViewModel::lastGoodAgeMs() const {
    return static_cast<qulonglong>(snapshot_.last_good_age_ms);
}

QString DashboardViewModel::failSafeState() const {
    return QString::fromLatin1(ivi::failSafeStateName(snapshot_.vehicle.fail_safe_state));
}

QString DashboardViewModel::failSafeReason() const {
    return QString::fromLatin1(ivi::failSafeReasonName(snapshot_.vehicle.fail_safe_reason));
}
bool DashboardViewModel::failSafeOverlayActive() const {
    if(physicalMode())return false;
    return snapshot_.vehicle.fail_safe_state >= 2U;
}

bool DashboardViewModel::authenticationError() const {
    return snapshot_.consecutive_secoc_failure_count >= 10U;
}
bool DashboardViewModel::secocVerified() const { return snapshot_.last_secoc_verified; }
unsigned int DashboardViewModel::secocFailureCount() const {
    return snapshot_.secoc_failure_count;
}
bool DashboardViewModel::securityAlertActive() const {
    return snapshot_.security_alert.has_value();
}
QString DashboardViewModel::attackType() const {
    return snapshot_.security_alert.has_value()
               ? QString::fromLatin1(ivi::attackTypeName(snapshot_.security_alert->attack_type))
               : QStringLiteral("None");
}
double DashboardViewModel::anomalyScore() const {
    return snapshot_.security_alert.has_value() ? snapshot_.security_alert->anomaly_score : 0.0;
}
QString DashboardViewModel::lastMessage() const {
    return QString::fromStdString(snapshot_.last_message);
}
QStringList DashboardViewModel::logs() const {
    QStringList output;
    for (const auto& line : snapshot_.logs) {
        output.push_back(QString::fromStdString(line));
    }
    return output;
}

void DashboardViewModel::updateSnapshot(const ivi::VehicleSnapshot& snapshot) {
    if (QThread::currentThread() != thread()) {
        QMetaObject::invokeMethod(
            this, [this, snapshot]() { updateSnapshot(snapshot); }, Qt::QueuedConnection);
        return;
    }
    // Observer callbacks are outside the Service mutex and Qt queues worker
    // delivery. A delayed older snapshot must not undo a newer GUI update.
    if(snapshot.snapshot_revision && snapshot_.snapshot_revision && snapshot.snapshot_revision<=snapshot_.snapshot_revision)return;
    const auto previous = snapshot_;
    snapshot_ = snapshot;
    updateConnectionNotice();
    const bool same_sensor_source=snapshot.physical_measurement && previous.physical_measurement &&
        snapshot.physical_measurement->instance==previous.physical_measurement->instance &&
        snapshot.physical_measurement->configuration==previous.physical_measurement->configuration &&
        snapshot.session_generation==previous.session_generation;
    if(!same_sensor_source){
        sensor_loss_timer_.stop();sensor_recovery_timer_.stop();
        sensor_seen_mask_=sensor_missing_mask_=0;sensor_incident_active_=false;
        if(popup_visible_&&popup_domain_==PopupDomain::Sensor)dismissPopup();
    }
    recordProtectionUpdate();
    const auto valid_node=[](const auto& node){
        using namespace capstone::session_v2;
        return node && node->kind==DiagnosticKind::NodeStatus &&
               validDiagnosticBody(0x302,DiagnosticKind::NodeStatus,node->body);
    };
    if(valid_node(snapshot.ecu_node_status) &&
       (!valid_node(previous.ecu_node_status) ||
        snapshot.ecu_node_status->session_id!=previous.ecu_node_status->session_id ||
        !std::equal(snapshot.ecu_node_status->body.begin(),snapshot.ecu_node_status->body.begin()+32,
                    previous.ecu_node_status->body.begin())))
        recordEvent(QStringLiteral("ECU 실행 정보 확인"),QStringLiteral("ecu-process-identified"));
    const auto valid_plan=[](const auto& plan){
        using namespace capstone::session_v2;
        return plan && plan->kind==DiagnosticKind::RestartPlan &&
               validDiagnosticBody(0x302,DiagnosticKind::RestartPlan,plan->body);
    };
    if(valid_plan(snapshot.ecu_restart_plan) &&
       (!valid_plan(previous.ecu_restart_plan) ||
        snapshot.ecu_restart_plan->session_id!=previous.ecu_restart_plan->session_id ||
        !std::equal(snapshot.ecu_restart_plan->body.begin(),snapshot.ecu_restart_plan->body.begin()+32,
                    previous.ecu_restart_plan->body.begin())))
        recordEvent(QStringLiteral("ECU 재시작 예고 수신"),QStringLiteral("ecu-restart-planned"));
    if(snapshot.physical_measurement)fail_safe_known_=false;
    else if(snapshot.fail_safe_known)fail_safe_known_=true;
    updatePhysicalSensorNotice();
    for(unsigned i=0;i<4;++i)if(snapshot.incident_rejection_ids[i] && snapshot.incident_rejection_ids[i]!=previous.incident_rejection_ids[i]){
        const auto text=QString::fromLatin1(ivi::attackTypeName(i+1))+QStringLiteral(" · 관련 데이터의 수신 거부 확인");
        recordEvent(text,QStringLiteral("incident-data-refusal"));
        presentPopup(text,QStringLiteral("확인된 위험 데이터가 화면에 반영되지 않도록 처리했습니다. 정상 데이터는 계속 확인합니다."),QStringLiteral("success"),70,PopupDomain::Security);
    }
    const bool new_fail_safe = !physicalMode() && (previous.vehicle.fail_safe_state != snapshot.vehicle.fail_safe_state ||
        previous.vehicle.fail_safe_reason != snapshot.vehicle.fail_safe_reason ||
        (!fail_safe_known_ && snapshot.last_message == "Authenticated Fail-safe event published"));
    const bool fresh_risk=snapshot.fail_safe_known&&snapshot.last_secoc_verified&&snapshot.vehicle.valid&&!snapshot.vehicle.stale&&
        (!snapshot.session_protocol||snapshot.session_bms_ready);
    if(popup_visible_&&popup_domain_==PopupDomain::Battery&&fresh_risk&&snapshot.vehicle.fail_safe_state<popup_battery_state_){
        dismissPopup();
        if(!new_fail_safe)presentPopup(statusTitle(),statusDescription(),snapshot.vehicle.fail_safe_state ? QStringLiteral("warning") : QStringLiteral("success"),60,PopupDomain::Battery);
    }
    if (new_fail_safe) {
        fail_safe_known_ = true;
        recordEvent(statusTitle() + QStringLiteral(" · ") + statusDescription(),QStringLiteral("battery-state"));
        presentPopup(statusTitle(), statusDescription(), snapshot.vehicle.fail_safe_state >= 2 ?
            QStringLiteral("danger") : snapshot.vehicle.fail_safe_state == 1 ?
            QStringLiteral("warning") : QStringLiteral("success"),
            snapshot.vehicle.fail_safe_state >= 2 ? 100 : 60,PopupDomain::Battery);
    }
    if(snapshot.session_protocol){
        unsigned added=snapshot.observed_condition_mask & ~previous.observed_condition_mask;
        for(unsigned type=0;type<4;++type){
            if((snapshot.observed_condition_mask&(1u<<type)) &&
               previous.security_incident_ids[type] && snapshot.security_incident_ids[type] &&
               previous.security_incident_ids[type]!=snapshot.security_incident_ids[type])added|=1u<<type;
        }
        const unsigned ended=previous.observed_condition_mask & ~snapshot.observed_condition_mask;
        if(added){
            for(int type=1;type<=4;++type)if(added&(1u<<(type-1)))
                recordEvent(QString::fromLatin1(ivi::attackTypeName(type))+QStringLiteral(" 탐지 보고"),QStringLiteral("ids-start"));
            presentPopup(securityTitle(),securityDescription(),QStringLiteral("danger"),70,PopupDomain::Security);
        }
        for(unsigned type=0;type<4;++type){
            const unsigned bit=1u<<type;
            if((snapshot.observed_condition_mask&bit) && !(added&bit) &&
               !previous.security_incident_ids[type] && snapshot.security_incident_ids[type])
                recordEvent(QString::fromLatin1(ivi::attackTypeName(type+1))+QStringLiteral(" · 탐지 기록 식별 확인"),QStringLiteral("ids-identified"));
        }
        if(ended){
            if(!snapshot.observed_condition_mask&&popup_visible_&&popup_domain_==PopupDomain::Security&&popup_kind_==QStringLiteral("danger"))dismissPopup();
            for(int type=1;type<=4;++type)if(ended&(1u<<(type-1)))
                if(snapshot.reconciled_unknown_mask&(1u<<(type-1)))
                    recordEvent(QString::fromLatin1(ivi::attackTypeName(type))+QStringLiteral(" · 이전 기록은 감시 공백으로 종료 미확인, 새 감시에서 정상 수신 확인"),QStringLiteral("ids-reconciled"));
                else recordEvent(QString::fromLatin1(ivi::attackTypeName(type))+QStringLiteral(" · 정상 관찰 후 종료 확인"),QStringLiteral("ids-end"));
        }
        if(previous.security_observation_ready && !snapshot.security_observation_ready)
            recordEvent(QStringLiteral("보안 감시 상태 확인 필요"),QStringLiteral("ids-unavailable"));
    }
    if (!snapshot.security_alert) active_attack_types_.clear();
    if (snapshot.security_alert && snapshot.security_alert_sequence != previous.security_alert_sequence) {
        const int code = snapshot.security_alert->attack_type;
        const auto name = QString::fromLatin1(ivi::attackTypeName(code));
        // Same-type repeated reports stay in the current episode; avoid a modal per CAN frame.
        if (!active_attack_types_.contains(code)) {
            active_attack_types_.insert(code);
            QStringList names, details;
            const QStringList descriptions{
                QStringLiteral("비정상 데이터를 전송하는 징후가 보고되었습니다."),
                QStringLiteral("이전 데이터를 다시 전송하는 징후가 보고되었습니다."),
                QStringLiteral("배터리 데이터를 위조하려는 징후가 보고되었습니다."),
                QStringLiteral("과도한 데이터 전송으로 통신이 방해받을 수 있습니다.")};
            for (int type = 1; type <= 4; ++type) if (active_attack_types_.contains(type)) {
                names.append(QString::fromLatin1(ivi::attackTypeName(type)));
                details.append(names.last() + QStringLiteral(": ") + descriptions.at(type-1));
            }
            security_title_ = names.join(QStringLiteral(" · "));
            security_description_ = details.join(QStringLiteral("\n"));
            recordEvent(name + QStringLiteral(" 탐지 보고"),QStringLiteral("ids-legacy-report"));
            presentPopup(security_title_, security_description_, QStringLiteral("danger"), 70,PopupDomain::Security);
        }
    }
    if (snapshot.secoc_failure_count > previous.secoc_failure_count) {
        const auto message = QString::fromStdString(snapshot.last_rejection_message.empty() ? snapshot.last_message : snapshot.last_rejection_message);
        const bool expired=message.contains(QStringLiteral("reason=ORIGINAL_EXPIRED")) || message.contains(QStringLiteral("reason=AUTH_EXPIRED"));
        const bool session_failure=message.contains(QStringLiteral("reason=PROTECTED_QUEUE_FULL")) ||
            message.contains(QStringLiteral("reason=AUTHENTICATED_CONFLICT")) || message.contains(QStringLiteral("reason=TIME_REGRESSION"));
        const bool replay_rejected=snapshot.local_rejection_record && snapshot.rejection_record_revision>previous.rejection_record_revision &&
            capstone::session_v2::validDiagnosticBody(0x303,capstone::session_v2::DiagnosticKind::Rejection,*snapshot.local_rejection_record) &&
            (*snapshot.local_rejection_record)[32]==7 && (*snapshot.local_rejection_record)[33]==1 && (*snapshot.local_rejection_record)[36]==2;
        QString reason;
        if(replay_rejected)reason=QStringLiteral("이미 처리한 재전송 데이터를 확인해 화면 반영을 거부했습니다.");
        else if(expired)reason=QStringLiteral("메시지 확인에 필요한 정보가 제시간에 도착하지 않았습니다.");
        else if(session_failure)reason=QStringLiteral("받은 정보를 다시 확인하기 위해 연결을 갱신합니다.");
        else if (message.contains(QStringLiteral("reason=MAC_FAIL"))) reason = QStringLiteral("메시지 인증값이 올바르지 않습니다.");
        else if (message.contains(QStringLiteral("reason=COUNTER_"))) reason = QStringLiteral("메시지 순서를 확인할 수 없습니다.");
        else if (message.contains(QStringLiteral("reason=AUTH_ORPHAN"))) reason = QStringLiteral("대응하는 원본 메시지가 없습니다.");
        else if (message.contains(QStringLiteral("reason=AUTH_TIMEOUT"))) reason = QStringLiteral("메시지 확인 시간이 초과되었습니다.");
        else reason = QStringLiteral("수신 데이터 검증에 실패했습니다.");
        rejection_summary_ = reason + QStringLiteral(" 마지막 정상값을 유지합니다.");
        if (reason != last_rejection_) {
            last_rejection_ = reason;
            recordEvent((expired ? QStringLiteral("수신 확인 지연 · ") : session_failure ? QStringLiteral("연결 재확인 · ") : QStringLiteral("수신 검증 거부 · ")) + reason,QStringLiteral("verification-result"));
            presentPopup(replay_rejected ? QStringLiteral("재전송 데이터를 거부했습니다") : expired ? QStringLiteral("일부 데이터 확인이 지연됐습니다") : session_failure ? QStringLiteral("연결을 다시 확인하고 있습니다") : QStringLiteral("수신 데이터를 거부했습니다"), rejection_summary_ +
                (replay_rejected ? QStringLiteral(" 정상 데이터는 계속 확인합니다.") : QStringLiteral(" 특정 공격의 차단 여부와는 별개인 검증 결과입니다.")), expired||session_failure ? QStringLiteral("warning") : QStringLiteral("success"), 70);
        }
    }
    // Physical channels use the incident/debounce policy above, including
    // total sensor loss. Do not also generate legacy BMS connection notices.
    if (!snapshot.physical_measurement && snapshot.vehicle.valid &&
        (!previous.vehicle.valid || snapshot.vehicle.stale != previous.vehicle.stale)) {
        const auto text = snapshot.vehicle.stale ? QStringLiteral("새 배터리 정보 수신 중단") : QStringLiteral("배터리 정보 수신 확인");
        recordEvent(text,QStringLiteral("connection-state"));
        if (snapshot.vehicle.stale) presentPopup(QStringLiteral("연결을 확인해 주세요"),
            QStringLiteral("새 배터리 정보를 받지 못하고 있습니다. 마지막 확인값을 표시합니다."), QStringLiteral("warning"), 40);
    }
    emit dataChanged();
    if (snapshot.measurement_sequence != 0U &&
        snapshot.measurement_sequence != last_measurement_sequence_) {
        last_measurement_sequence_ = snapshot.measurement_sequence;
        const auto now = std::chrono::steady_clock::now();
        const auto t3_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
                               now.time_since_epoch())
                               .count();
        emit measurementReady(static_cast<qulonglong>(snapshot.measurement_sequence),
                              static_cast<qulonglong>(snapshot.t1_received_ns),
                              static_cast<qulonglong>(snapshot.t2_published_ns),
                              static_cast<qulonglong>(t3_ns));
    }
}

void DashboardViewModel::acknowledgeSecurityAlert() {
    if (snapshot_.security_alert.has_value()) {
        emit securityAlertAcknowledgementRequested(
            static_cast<qulonglong>(snapshot_.security_alert_sequence));
    }
}
