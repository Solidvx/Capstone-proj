#include "dashboard_view_model.h"
#include "rejection_record.h"

#include <QSignalSpy>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QTimer>
#include <QJsonArray>
#include <QtTest>

#include <algorithm>
#include <numeric>
#include <thread>
#include <vector>

class DashboardViewModelTest : public QObject {
    Q_OBJECT

    static ivi::VehicleSnapshot protectionSnapshot(const capstone::session_v2::Nonce& instance,
        const capstone::session_v2::Nonce& lineage,const capstone::session_v2::Nonce& incident,
        const capstone::session_v2::Nonce& session,unsigned revision,bool resumed){
        using namespace capstone::session_v2;
        ivi::VehicleSnapshot s;s.session_protocol=true;s.session_state_ready=true;
        s.session_bms_ready=true;s.fail_safe_known=true;s.protection_confirmed=true;s.last_secoc_verified=true;
        s.vehicle.valid=true;s.vehicle.stale=false;s.vehicle.soc_percent=75;s.vehicle.temperature_c=56;
        s.vehicle.fail_safe_state=1;s.vehicle.fail_safe_reason=3;
        DiagnosticMessage p{DiagnosticKind::ProtectionStatus,10,0x302,session,std::vector<std::uint8_t>(56),100,101};
        std::copy(instance.begin(),instance.end(),p.body.begin());std::copy(lineage.begin(),lineage.end(),p.body.begin()+16);
        std::copy(incident.begin(),incident.end(),p.body.begin()+32);p.body[48]=1;p.body[49]=3;p.body[50]=1;p.body[51]=resumed;
        for(unsigned i=0;i<4;++i)p.body[52+i]=static_cast<std::uint8_t>(revision>>(24-8*i));
        s.ecu_protection_status=p;
        DiagnosticMessage node{DiagnosticKind::NodeStatus,9,0x302,session,std::vector<std::uint8_t>(56),90,91};
        std::copy(instance.begin(),instance.end(),node.body.begin());
        node.body[32]=2;node.body[33]=resumed?2:1;node.body[34]=2;node.body[35]=1;node.body[36]=1;node.body[37]=3;
        node.body[52]=node.body[54]=resumed;node.body[53]=1;s.ecu_node_status=node;
        return s;
    }
    static QList<QJsonObject> protectionRecords(const QSignalSpy& spy){
        QList<QJsonObject> records;
        for(const auto& args:spy){const auto row=qvariant_cast<QJsonObject>(args.first());
            if(row.value("category").toString()==QStringLiteral("protection-status"))records.append(row);}
        return records;
    }

private slots:
    void automaticSocInitializationIsDifferentFromUnknownOrLostInput(){
        DashboardViewModel model;ivi::VehicleSnapshot s;
        s.physical_measurement=capstone::session_v2::PhysicalMeasurement{};
        s.physical_measurement->soc_basis=2;s.physical_measurement->sequence=3;
        s.physical_valid={true,true,true,false,false};s.vehicle.valid=true;
        model.updateSnapshot(s);QVERIFY(model.physicalSocInitializing());QVERIFY(!model.socAvailable());
        s.physical_measurement->sequence++;
        s.physical_measurement->soc_percent=0;s.physical_valid[3]=true;s.vehicle.soc_percent=0;
        model.updateSnapshot(s);QVERIFY(!model.physicalSocInitializing());QVERIFY(model.socAvailable());
        QCOMPARE(model.soc(),0.0);QVERIFY(!model.sohAvailable());
        s.physical_valid[0]=s.physical_valid[1]=s.physical_valid[3]=false;
        model.updateSnapshot(s);QVERIFY(!model.physicalSocInitializing());QVERIFY(!model.socAvailable());
        s.physical_measurement->soc_basis=0;s.physical_measurement->soc_percent.reset();
        s.physical_valid[0]=s.physical_valid[1]=true;model.updateSnapshot(s);
        QVERIFY(!model.physicalSocInitializing());
    }
    void outOfModelVoltageDoesNotPromiseSocInitialization(){
        DashboardViewModel model;ivi::VehicleSnapshot s;
        s.physical_measurement=capstone::session_v2::PhysicalMeasurement{};
        s.physical_measurement->soc_basis=2;s.physical_measurement->sequence=3;
        s.physical_valid={true,true,true,false,false};s.vehicle.valid=true;
        for(double voltage:{0.,2.66,4.3}){
            s.physical_measurement->voltage_v=voltage;s.vehicle.voltage_v=voltage;
            model.updateSnapshot(s);
            QVERIFY(model.physicalSocOutsideModel());QVERIFY(!model.physicalSocInitializing());
            QVERIFY(model.voltageAvailable());QVERIFY(!model.socAvailable());
        }
        for(double voltage:{3.,3.7,4.25}){
            s.physical_measurement->voltage_v=voltage;s.vehicle.voltage_v=voltage;
            model.updateSnapshot(s);
            QVERIFY(!model.physicalSocOutsideModel());QVERIFY(model.physicalSocInitializing());
        }
        s.physical_measurement->voltage_v=2.66;s.physical_valid[0]=false;model.updateSnapshot(s);
        QVERIFY(!model.physicalSocOutsideModel());QVERIFY(!model.physicalSocInitializing());
        s.physical_valid[0]=true;s.physical_measurement->soc_basis=0;model.updateSnapshot(s);
        QVERIFY(!model.physicalSocOutsideModel());QVERIFY(!model.physicalSocInitializing());
    }
    void sohHintDistinguishesMissingCapacityFromExpiredMeasurement(){
        DashboardViewModel model;ivi::VehicleSnapshot s;
        s.physical_measurement=capstone::session_v2::PhysicalMeasurement{};
        model.updateSnapshot(s);QCOMPARE(model.sohHint(),QStringLiteral("용량 시험 후 표시됩니다"));
        s.physical_measurement->soh_basis=1;s.physical_measurement->soh_percent=90;
        s.physical_valid[4]=true;model.updateSnapshot(s);
        QCOMPARE(model.sohHint(),QStringLiteral("측정한 용량을 기준으로 계산했습니다"));
        s.physical_valid[4]=false;model.updateSnapshot(s);
        QCOMPARE(model.sohHint(),QStringLiteral("새 용량 정보를 확인하고 있습니다"));
        s.physical_measurement->soh_basis=2;s.physical_measurement->soh_percent=81;
        s.physical_valid[4]=true;model.updateSnapshot(s);
        QVERIFY(model.sohAvailable());QVERIFY(model.sohHint().isEmpty());
        s.physical_measurement.reset();model.updateSnapshot(s);QVERIFY(model.sohHint().isEmpty());
    }
    void physicalSensorNoticesDebounceAndKeepOneIncidentUntilStableRecovery(){
        DashboardViewModel model;QSignalSpy records(&model,&DashboardViewModel::eventRecorded);
        auto count=[&](const QString& category){
            unsigned n=0;for(const auto& args:records)
                if(qvariant_cast<QJsonObject>(args.first()).value("category").toString()==category)++n;
            return n;
        };
        ivi::VehicleSnapshot s;s.physical_measurement=capstone::session_v2::PhysicalMeasurement{};
        s.physical_measurement->sequence=3;s.vehicle.valid=true;s.vehicle.stale=false;
        s.physical_valid={true,true,true,false,false};model.updateSnapshot(s);
        // Reproduce short expiry/recovery cycles: availability changes at once,
        // but these are not separate user-visible sensor failures.
        for(unsigned i=0;i<3;++i){
            s.physical_valid[0]=s.physical_valid[1]=false;model.updateSnapshot(s);
            QVERIFY(!model.voltageAvailable());QVERIFY(!model.popupVisible());
            QTest::qWait(120);
            s.physical_valid[0]=s.physical_valid[1]=true;model.updateSnapshot(s);
            QTest::qWait(120);
        }
        QTest::qWait(2100);QCOMPARE(count("sensor-input-lost"),0u);
        s.physical_valid[0]=s.physical_valid[1]=false;model.updateSnapshot(s);
        QTRY_VERIFY_WITH_TIMEOUT(model.popupVisible(),2500);
        QCOMPARE(count("sensor-input-lost"),1u);
        QVERIFY(model.popupDescription().contains(QStringLiteral("전압·전류")));
        // Neither short recovery nor another loss dismisses/reopens the notice.
        s.physical_valid[0]=s.physical_valid[1]=true;model.updateSnapshot(s);
        QTest::qWait(120);QVERIFY(model.popupVisible());
        s.physical_valid[0]=s.physical_valid[1]=false;model.updateSnapshot(s);
        model.dismissPopup();QTest::qWait(2100);
        QVERIFY(!model.popupVisible());QCOMPARE(count("sensor-input-lost"),1u);
        QCOMPARE(count("sensor-input-recovered"),0u);
        s.physical_valid[0]=s.physical_valid[1]=true;model.updateSnapshot(s);
        s.physical_measurement->sequence++;model.updateSnapshot(s);
        QTRY_COMPARE_WITH_TIMEOUT(count("sensor-input-recovered"),1u,5500);
        QVERIFY(!model.popupVisible()); // recovery never reopens a closed notice
        s.physical_valid[2]=false;model.updateSnapshot(s);
        QTRY_VERIFY_WITH_TIMEOUT(model.popupVisible(),2500);
        QCOMPARE(count("sensor-input-lost"),2u);
        s.physical_valid[2]=true;model.updateSnapshot(s);
        s.physical_measurement->sequence++;model.updateSnapshot(s);
        QTRY_COMPARE_WITH_TIMEOUT(model.popupKind(),QStringLiteral("success"),5500);
        QVERIFY(model.popupVisible()); // unread recovery result stays until closed
        QCOMPARE(count("sensor-input-recovered"),2u);
    }
    void physicalSensorWarmupAndSourceReplacementDoNotFabricateRecovery(){
        DashboardViewModel model;ivi::VehicleSnapshot s;
        s.physical_measurement=capstone::session_v2::PhysicalMeasurement{};
        s.physical_measurement->ina_quality=s.physical_measurement->temperature_quality=1;
        model.updateSnapshot(s);QTest::qWait(2100);QVERIFY(!model.popupVisible());
        // A sensor which never worked must still report a persistent failure.
        s.physical_measurement->ina_quality=3;model.updateSnapshot(s);
        QTRY_VERIFY_WITH_TIMEOUT(model.popupVisible(),2500);
        s.physical_measurement->instance[0]=1;
        s.physical_measurement->ina_quality=1;model.updateSnapshot(s);
        QVERIFY(!model.popupVisible());
        QVERIFY(!model.eventHistory().join(' ').contains(QStringLiteral("회복 확인")));
        // Recovery cannot cover a security warning; total loss also must not
        // emit a second set of legacy BMS connection events.
        s.physical_measurement->ina_quality=3;model.updateSnapshot(s);
        QTRY_VERIFY_WITH_TIMEOUT(model.popupVisible(),2500);
        s.session_protocol=true;s.observed_condition_mask=8;model.updateSnapshot(s);
        const auto security_notice=model.popupTitle();QVERIFY(security_notice.contains(QStringLiteral("Flooding")));
        s.physical_valid={true,true,true,false,false};s.vehicle.valid=true;
        s.physical_measurement->sequence=3;model.updateSnapshot(s);
        s.physical_measurement->sequence=4;model.updateSnapshot(s);
        QTest::qWait(5100);
        QCOMPARE(model.popupTitle(),security_notice);QCOMPARE(model.popupKind(),QStringLiteral("danger"));
        QVERIFY(model.eventHistory().join(' ').contains(QStringLiteral("회복 확인")));
        QVERIFY(!model.eventHistory().join(' ').contains(QStringLiteral("배터리 정보 수신 확인")));
    }
    void physicalUnknownSocAndPartialSensorFailure(){
        DashboardViewModel model;ivi::VehicleSnapshot s;s.physical_measurement=capstone::session_v2::PhysicalMeasurement{};
        s.physical_measurement->sequence=3;s.vehicle.valid=true;s.vehicle.stale=false;
        s.vehicle.voltage_v=3.8531;s.vehicle.current_a=-.3711;s.vehicle.temperature_c=20.125;
        s.physical_valid={true,true,true,false,false};model.updateSnapshot(s);
        QVERIFY(model.physicalMode());QVERIFY(model.measurementsAvailable());QVERIFY(!model.socAvailable());QVERIFY(!model.sohAvailable());
        QVERIFY(model.voltageAvailable());QVERIFY(model.temperatureAvailable());QCOMPARE(model.voltage(),3.8531);
        QCOMPARE(model.socBand(),QStringLiteral("unavailable"));QVERIFY(!model.failSafeKnown());
        QCOMPARE(model.statusTitle(),QStringLiteral("실제 배터리 측정 중"));
        s.physical_valid[2]=false;model.updateSnapshot(s);QVERIFY(model.voltageAvailable());QVERIFY(!model.temperatureAvailable());
        QCOMPARE(model.statusTitle(),QStringLiteral("일부 센서 확인 필요"));
        s.physical_valid.fill(false);s.vehicle.valid=false;s.vehicle.stale=true;model.updateSnapshot(s);
        QVERIFY(!model.measurementsAvailable());QVERIFY(!model.socAvailable());
        QCOMPARE(model.statusTitle(),QStringLiteral("센서·연결 확인 필요"));
    }
    void committedRecordingGapPersistsAcrossNewProtectionIncidents(){
        using namespace capstone::session_v2;
        const auto instance=diagnosticUuid(),lineage=diagnosticUuid(),context=diagnosticUuid();
        DashboardViewModel model;QSignalSpy records(&model,&DashboardViewModel::eventRecorded);
        auto s=protectionSnapshot(instance,lineage,diagnosticUuid(),context,1,false);
        model.updateSnapshot(s);auto durable=protectionRecords(records).last();
        auto link=durable.value("protection_link").toObject();link.insert("gap_possible",true);
        durable.insert("protection_link",link);model.protectionCommitted(durable);
        s=protectionSnapshot(instance,lineage,diagnosticUuid(),context,1,false);
        model.updateSnapshot(s);
        link=protectionRecords(records).last().value("protection_link").toObject();
        QCOMPARE(link.value("status").toString(),QStringLiteral("new-incident"));
        QVERIFY(link.value("gap_possible").toBool());
        QCOMPARE(model.statusTitle(),QStringLiteral("[WARNING] 배터리 온도 높음"));
        DashboardViewModel reopened;QSignalSpy reopened_records(&reopened,&DashboardViewModel::eventRecorded);
        reopened.expectProtectionHistory();reopened.restoreProtectionHistory(durable,false);
        reopened.updateSnapshot(s);
        QVERIFY(protectionRecords(reopened_records).last().value("protection_link").toObject().value("gap_possible").toBool());
        // Malformed commit metadata must not become an anchor or taint a
        // previously clean history merely by carrying a gap flag.
        DashboardViewModel clean;QSignalSpy clean_records(&clean,&DashboardViewModel::eventRecorded);
        clean.updateSnapshot(s);auto invalid=protectionRecords(clean_records).last();
        invalid.insert("ecu_protection",QJsonObject{});invalid.insert("protection_link",link);
        clean.protectionCommitted(invalid);
        s=protectionSnapshot(instance,lineage,diagnosticUuid(),context,1,false);clean.updateSnapshot(s);
        QVERIFY(!protectionRecords(clean_records).last().value("protection_link").toObject().value("gap_possible").toBool());
    }
    void restoredProtectionWaitsForHistoryAndOnlyLinksCommittedRecord(){
        using namespace capstone::session_v2;
        const auto instance=diagnosticUuid(),lineage=diagnosticUuid(),incident=diagnosticUuid(),context=diagnosticUuid();
        DashboardViewModel old;QSignalSpy original(&old,&DashboardViewModel::eventRecorded);
        old.updateSnapshot(protectionSnapshot(instance,lineage,incident,context,1,false));
        auto rows=protectionRecords(original);QCOMPARE(rows.size(),1);const auto previous=rows.first();
        QCOMPARE(previous.value("protection_link").toObject().value("status").toString(),QStringLiteral("unlinked"));
        DashboardViewModel current;QSignalSpy records(&current,&DashboardViewModel::eventRecorded);
        current.expectProtectionHistory();
        auto resumed=protectionSnapshot(diagnosticUuid(),lineage,incident,diagnosticUuid(),1,true);
        current.updateSnapshot(resumed);QCOMPARE(protectionRecords(records).size(),0);
        current.restoreEventHistory({previous.value("display").toString()});
        current.restoreProtectionHistory(previous,false);rows=protectionRecords(records);QCOMPARE(rows.size(),1);
        const auto linked=rows.last();const auto link=linked.value("protection_link").toObject();
        QCOMPARE(link.value("status").toString(),QStringLiteral("resumed"));
        QCOMPARE(link.value("previous_event_id"),previous.value("event_id"));QVERIFY(link.value("gap_possible").toBool());
        QCOMPARE(linked.value("ecu_protection").toObject().value("incident_id"),previous.value("ecu_protection").toObject().value("incident_id"));
        QCOMPARE(linked.value("battery_state").toInt(),1);QCOMPARE(current.soc(),75.0);
        current.protectionCommitted(linked);
        resumed.ecu_protection_status->sequence++;resumed.ecu_protection_status->received_ms++;
        current.updateSnapshot(resumed);QCOMPARE(protectionRecords(records).size(),1); // heartbeat is not a new event
        auto fresh=protectionSnapshot(diagnosticUuid(),diagnosticUuid(),diagnosticUuid(),diagnosticUuid(),1,false);
        current.updateSnapshot(fresh);rows=protectionRecords(records);QCOMPARE(rows.size(),2);
        const auto fresh_link=rows.last().value("protection_link").toObject();
        QCOMPARE(fresh_link.value("status").toString(),QStringLiteral("new-lineage"));
        QVERIFY(fresh_link.value("prior_event_end_unconfirmed").toBool());QVERIFY(!fresh_link.contains("previous_event_id"));
        QCOMPARE(previous.value("ecu_protection").toObject().value("phase").toInt(),1); // old event was not silently closed
    }
    void uncommittedOrMalformedProtectionCannotBecomeAPreviousDurableRecord(){
        using namespace capstone::session_v2;
        const auto lineage=diagnosticUuid(),incident=diagnosticUuid();
        DashboardViewModel model;QSignalSpy records(&model,&DashboardViewModel::eventRecorded);
        auto s=protectionSnapshot(diagnosticUuid(),lineage,incident,diagnosticUuid(),1,false);
        model.updateSnapshot(s);auto first=protectionRecords(records).first();
        s=protectionSnapshot(diagnosticUuid(),lineage,incident,diagnosticUuid(),1,true);
        model.updateSnapshot(s);auto link=protectionRecords(records).last().value("protection_link").toObject();
        QCOMPARE(link.value("status").toString(),QStringLiteral("unlinked"));QVERIFY(!link.contains("previous_event_id"));
        auto details=first.value("ecu_protection").toObject();details.insert("revision","99");first.insert("ecu_protection",details);
        DashboardViewModel invalid;QSignalSpy bad(&invalid,&DashboardViewModel::eventRecorded);invalid.expectProtectionHistory();
        invalid.restoreProtectionHistory(first,false);invalid.updateSnapshot(s);
        link=protectionRecords(bad).last().value("protection_link").toObject();
        QCOMPARE(link.value("status").toString(),QStringLiteral("unlinked"));QVERIFY(link.value("gap_possible").toBool());
    }
    void rollbackPreservesHistoricalHighWaterAndMissingMetadataIsNotRecovery(){
        using namespace capstone::session_v2;
        const auto lineage=diagnosticUuid(),incident=diagnosticUuid();
        DashboardViewModel old;QSignalSpy before(&old,&DashboardViewModel::eventRecorded);
        old.updateSnapshot(protectionSnapshot(diagnosticUuid(),lineage,incident,diagnosticUuid(),7,false));
        const auto previous=protectionRecords(before).last();
        DashboardViewModel model;QSignalSpy records(&model,&DashboardViewModel::eventRecorded);model.expectProtectionHistory();
        model.restoreProtectionHistory(previous,false);
        auto s=protectionSnapshot(diagnosticUuid(),lineage,incident,diagnosticUuid(),3,true);
        model.updateSnapshot(s);auto event=protectionRecords(records).last();
        auto link=event.value("protection_link").toObject();
        QCOMPARE(link.value("status").toString(),QStringLiteral("checkpoint-history-gap"));
        QCOMPARE(link.value("high_water_revision").toString(),QStringLiteral("7"));model.protectionCommitted(event);
        s.ecu_protection_status->body[55]=4;model.updateSnapshot(s);event=protectionRecords(records).last();
        link=event.value("protection_link").toObject();QCOMPARE(link.value("high_water_revision").toString(),QStringLiteral("7"));
        QCOMPARE(link.value("status").toString(),QStringLiteral("checkpoint-history-gap"));model.protectionCommitted(event);
        const auto count=protectionRecords(records).size();s.protection_confirmed=false;model.updateSnapshot(s);
        QCOMPARE(protectionRecords(records).size(),count);
        s.protection_confirmed=true;model.updateSnapshot(s);QCOMPARE(protectionRecords(records).size(),count+1);
        QVERIFY(protectionRecords(records).last().value("protection_link").toObject().value("gap_possible").toBool());
    }
    void processIdentityIsRecordedWithoutGuessingProtectionRecovery(){
        using namespace capstone::session_v2;
        DashboardViewModel model;QSignalSpy recorded(&model,&DashboardViewModel::eventRecorded);
        ivi::VehicleSnapshot s;s.session_protocol=true;s.fail_safe_known=true;
        s.vehicle.fail_safe_state=3;s.vehicle.fail_safe_reason=4;
        const auto instance=diagnosticUuid(),context=diagnosticUuid(),operation=diagnosticUuid();
        DiagnosticMessage node{DiagnosticKind::NodeStatus,1,0x302,context,std::vector<std::uint8_t>(56),10,11};
        std::copy(instance.begin(),instance.end(),node.body.begin());
        node.body[32]=2;node.body[33]=1;node.body[34]=2;
        node.body[35]=3;node.body[36]=1;node.body[37]=4;node.body[53]=1;
        QVERIFY(validDiagnosticBody(0x302,DiagnosticKind::NodeStatus,node.body));
        s.ecu_node_status=node;model.updateSnapshot(s);
        auto process=qvariant_cast<QJsonObject>(recorded.first().at(0)).value("ecu_process").toObject();
        QCOMPARE(process.value("instance_id").toString(),QString::fromLatin1(QByteArray(reinterpret_cast<const char*>(instance.data()),16).toHex()));
        QVERIFY(!process.contains("restart_operation_id"));
        QVERIFY(!process.value("risk_restored").toBool());
        const auto before=recorded.size();
        s.ecu_node_status->sequence++;model.updateSnapshot(s);
        QCOMPARE(recorded.size(),before); // heartbeat cannot flood the journal
        auto& next=*s.ecu_node_status;const auto replacement=diagnosticUuid();
        std::copy(replacement.begin(),replacement.end(),next.body.begin());
        std::copy(operation.begin(),operation.end(),next.body.begin()+16);
        next.body[33]=2;next.body[52]=next.body[54]=1;
        QVERIFY(validDiagnosticBody(0x302,DiagnosticKind::NodeStatus,next.body));
        model.updateSnapshot(s);QCOMPARE(recorded.size(),before+1);
        auto event=qvariant_cast<QJsonObject>(recorded.last().at(0));
        process=event.value("ecu_process").toObject();
        QCOMPARE(process.value("restart_operation_id").toString(),QString::fromLatin1(QByteArray(reinterpret_cast<const char*>(operation.data()),16).toHex()));
        QVERIFY(process.value("calculation_restored").toBool());QVERIFY(process.value("risk_restored").toBool());
        QCOMPARE(event.value("battery_state").toInt(),3);
        QCOMPARE(model.statusTitle(),QStringLiteral("[CRITICAL] 배터리 과열 위험"));
        next.session_id=diagnosticUuid();model.updateSnapshot(s);QCOMPARE(recorded.size(),before+2);
        next.body.clear();model.updateSnapshot(s);QCOMPARE(recorded.size(),before+2);
        DiagnosticMessage plan{DiagnosticKind::RestartPlan,1,0x302,context,std::vector<std::uint8_t>(56),20,21};
        std::copy(instance.begin(),instance.end(),plan.body.begin());
        std::copy(operation.begin(),operation.end(),plan.body.begin()+16);
        plan.body[48]=3;plan.body[49]=2;plan.body[50]=1;plan.body[55]=100;
        QVERIFY(validDiagnosticBody(0x302,DiagnosticKind::RestartPlan,plan.body));
        s.ecu_restart_plan=plan;model.updateSnapshot(s);QCOMPARE(recorded.size(),before+3);
        const auto planEvent=qvariant_cast<QJsonObject>(recorded.last().at(0));
        QVERIFY(!planEvent.contains("ecu_process")); // malformed node cannot supply metadata
        const auto planRecord=planEvent.value("ecu_restart_plan").toObject();
        QVERIFY(!planRecord.contains("protection_incident_id"));
        QCOMPARE(planRecord.value("operation_id").toString(),QString::fromLatin1(QByteArray(reinterpret_cast<const char*>(operation.data()),16).toHex()));
        s.ecu_restart_plan->sequence++;model.updateSnapshot(s);QCOMPARE(recorded.size(),before+3);
    }
    void persistedIncidentLinksKeepSparseAttackTypes(){
        DashboardViewModel model;
        QSignalSpy recorded(&model,&DashboardViewModel::eventRecorded);
        ivi::VehicleSnapshot s;s.fail_safe_known=true;
        capstone::session_v2::Nonce replay{},flood{},refusal{};
        replay[0]=1;flood[0]=2;refusal[0]=3;
        s.security_incident_ids[1]=replay;s.security_incident_ids[3]=flood;
        s.incident_rejection_ids[1]=refusal;
        s.vehicle.fail_safe_state=1;s.vehicle.fail_safe_reason=1;
        model.updateSnapshot(s);
        QVERIFY(!recorded.isEmpty());
        const auto event=qvariant_cast<QJsonObject>(recorded.last().at(0));
        const auto links=event.value("typed_incidents").toArray();
        QCOMPARE(links.size(),2);
        QCOMPARE(links[0].toObject().value("attack_type").toString(),QStringLiteral("replay"));
        QCOMPARE(links[0].toObject().value("incident_id").toString(),QStringLiteral("01000000000000000000000000000000"));
        QCOMPARE(links[0].toObject().value("rejection_id").toString(),QStringLiteral("03000000000000000000000000000000"));
        QCOMPARE(links[1].toObject().value("attack_type").toString(),QStringLiteral("flooding"));
        QVERIFY(!links[1].toObject().contains("rejection_id"));
    }
    void computationRecoveryAndOperatorRequiredHaveDistinctLabels(){
        DashboardViewModel model;ivi::VehicleSnapshot s;s.session_protocol=true;
        s.connection_stage="task-restoring";model.updateSnapshot(s);
        QCOMPARE(model.connectionLabel(),QStringLiteral("계산 작업 복구 중…"));
        s.connection_stage="operator-required";s.fail_safe_known=true;s.vehicle.fail_safe_state=1;s.vehicle.fail_safe_reason=7;
        model.updateSnapshot(s);QCOMPARE(model.connectionLabel(),QStringLiteral("ECU 점검 필요"));
        QVERIFY(model.statusDescription().contains(QStringLiteral("작업 복구에 실패")));
    }
    void thermalWaitingNeverClaimsProcessRestartOrRecoveryWithoutFreshInput(){
        DashboardViewModel model;ivi::VehicleSnapshot s;
        s.session_protocol=true;s.session_bms_ready=true;s.fail_safe_known=true;
        s.vehicle.valid=true;s.vehicle.stale=false;s.vehicle.sensor_state=2;
        s.vehicle.fail_safe_state=3;s.vehicle.fail_safe_reason=4;s.vehicle.temperature_c=65;
        model.updateSnapshot(s);QCOMPARE(model.statusTitle(),QStringLiteral("[CRITICAL] 배터리 과열 위험"));
        s.vehicle.temperature_c=55;model.updateSnapshot(s);
        QCOMPARE(model.statusTitle(),QStringLiteral("[CRITICAL] 배터리 과열 위험"));
        QVERIFY(model.statusDescription().contains(QStringLiteral("5초 연속")));
        QVERIFY(model.failSafeOverlayActive());
        s.vehicle.sensor_state=4;model.updateSnapshot(s);
        QCOMPARE(model.statusTitle(),QStringLiteral("[CRITICAL] 배터리 과열 위험"));
        QVERIFY(model.statusDescription().contains(QStringLiteral("현재 온도를 확인할 수 없어")));
        s.vehicle.sensor_state=2;s.vehicle.fail_safe_state=0;s.vehicle.fail_safe_reason=5;
        s.last_secoc_verified=true;model.updateSnapshot(s);QVERIFY(!model.failSafeOverlayActive());
    }
    void sensorRecoveryDistinguishesMissingAndLastGoodValues(){
        DashboardViewModel model;ivi::VehicleSnapshot snapshot;
        for(unsigned state: {1u,3u,5u}){
            snapshot.vehicle.sensor_state=state;model.updateSnapshot(snapshot);
            QVERIFY(!model.measurementsAvailable());QVERIFY(!model.sensorUsesLastGood());
            QVERIFY(model.sensorStateWarning());
        }
        snapshot.vehicle.sensor_state=4;model.updateSnapshot(snapshot);
        QVERIFY(!model.sensorUsesLastGood());
        snapshot.vehicle.valid=true;snapshot.vehicle.soc_percent=42;
        for(unsigned state: {4u,6u}){
            snapshot.vehicle.sensor_state=state;model.updateSnapshot(snapshot);
            QVERIFY(model.measurementsAvailable());QVERIFY(model.sensorUsesLastGood());
            QVERIFY(model.sensorState().contains(QStringLiteral("마지막 정상값")));
            QCOMPARE(model.soc(),42.0);
        }
        snapshot.vehicle.sensor_state=2;model.updateSnapshot(snapshot);
        QVERIFY(!model.sensorStateWarning());QVERIFY(!model.sensorUsesLastGood());
        QCOMPARE(model.sensorState(),QStringLiteral("정상 측정 중"));
    }
    void freshConfirmedBatteryRecoveryReplacesOldDangerPopup(){
        DashboardViewModel model;ivi::VehicleSnapshot snapshot;
        snapshot.session_protocol=true;snapshot.fail_safe_known=true;snapshot.vehicle.valid=true;snapshot.vehicle.stale=false;
        snapshot.last_secoc_verified=true;snapshot.session_bms_ready=true;snapshot.vehicle.fail_safe_state=2;snapshot.vehicle.fail_safe_reason=2;
        model.updateSnapshot(snapshot);QCOMPARE(model.popupKind(),QStringLiteral("danger"));
        snapshot.vehicle.fail_safe_state=0;snapshot.vehicle.fail_safe_reason=5;snapshot.session_bms_ready=false;snapshot.vehicle.stale=true;
        model.updateSnapshot(snapshot);QCOMPARE(model.popupKind(),QStringLiteral("danger"));
        snapshot.session_bms_ready=true;snapshot.vehicle.stale=false;model.updateSnapshot(snapshot);
        QCOMPARE(model.popupKind(),QStringLiteral("success"));
        QVERIFY(!model.failSafeOverlayActive());
    }
    void newObserverDoesNotRewriteUnknownOldIncidentAsConfirmedEnd(){
        DashboardViewModel model;ivi::VehicleSnapshot snapshot;
        snapshot.session_protocol=true;snapshot.security_observation_ready=true;snapshot.observed_condition_mask=1;
        model.updateSnapshot(snapshot);
        snapshot.unreconciled_incident_mask=1;model.updateSnapshot(snapshot);
        QVERIFY(model.securityDescription().contains(QStringLiteral("이전 감시")));
        snapshot.observed_condition_mask=0;snapshot.reconciled_unknown_mask=1;snapshot.unreconciled_incident_mask=0;
        model.updateSnapshot(snapshot);
        QVERIFY(model.eventHistory().first().contains(QStringLiteral("종료 미확인")));
        QVERIFY(!model.eventHistory().first().contains(QStringLiteral("종료 확인")));
    }
    void incidentRefusalBadgeRequiresCurrentUniqueLink(){
        DashboardViewModel model;ivi::VehicleSnapshot snapshot;
        snapshot.session_protocol=true;snapshot.security_observation_ready=true;snapshot.observed_condition_mask=2;
        model.updateSnapshot(snapshot);
        QVERIFY(!model.incidentTreatments().join(QLatin1Char(' ')).contains(QStringLiteral("수신 거부 확인")));
        snapshot.incident_rejection_ids[1]=capstone::session_v2::diagnosticUuid();model.updateSnapshot(snapshot);
        QVERIFY(model.incidentTreatments().join(QLatin1Char(' ')).contains(QStringLiteral("수신 거부 확인")));
        snapshot.incident_rejection_ids[1].reset();model.updateSnapshot(snapshot);
        QVERIFY(!model.incidentTreatments().join(QLatin1Char(' ')).contains(QStringLiteral("수신 거부 확인")));
    }
    void restoredHistoryAndStorageFailureDoNotClearBatteryProtection(){
        DashboardViewModel model;ivi::VehicleSnapshot snapshot;
        snapshot.vehicle.valid=true;snapshot.fail_safe_known=true;
        snapshot.vehicle.fail_safe_state=3;snapshot.vehicle.fail_safe_reason=4;snapshot.vehicle.temperature_c=65;
        model.updateSnapshot(snapshot);const auto popup=model.popupTitle();
        model.restoreEventHistory({QStringLiteral("이전 실행의 이벤트")});
        QVERIFY(model.eventHistory().contains(QStringLiteral("이전 실행의 이벤트")));
        QVERIFY(model.failSafeOverlayActive());QCOMPARE(model.popupTitle(),popup);
        model.setHistoryStorageStatus(QStringLiteral("이벤트 기록 저장 실패"));
        QVERIFY(model.failSafeOverlayActive());QCOMPARE(model.popupTitle(),popup);
        model.dismissPopup();model.setHistoryStorageStatus(QStringLiteral("기록 저장 중단"));
        QCOMPARE(model.popupTitle(),QStringLiteral("이벤트 기록을 확인해 주세요"));
    }
    void floodingMetricsKeepUnknownDistinctFromZero(){
        DashboardViewModel model;ivi::VehicleSnapshot snapshot;
        snapshot.session_protocol=true;model.updateSnapshot(snapshot);
        QCOMPARE(model.floodingMetrics().size(),5);
        QVERIFY(model.floodingMetrics()[0].contains(QStringLiteral("미측정")));
        QVERIFY(model.floodingMetrics()[4].contains(QStringLiteral("미측정")));
        snapshot.security_observation_ready=true;snapshot.ecu_observed_fps=1234.5;snapshot.ecu_observed_drops=7;
        snapshot.session_bms_ready=true;snapshot.last_good_age_ms=123;
        snapshot.ivi_publication_metrics.authenticated_bms=12;
        snapshot.ivi_publication_metrics.mean_interval_us=100000;
        snapshot.ivi_publication_metrics.max_interval_us=120000;
        model.updateSnapshot(snapshot);
        QVERIFY(model.floodingMetrics()[0].contains(QStringLiteral("1234.5")));
        QVERIFY(model.floodingMetrics()[4].contains(QStringLiteral("7건")));
        QVERIFY(model.floodingMetrics()[4].contains(QStringLiteral("IVI 수신 큐 유실: 미측정")));
        snapshot.ivi_socket_drops=0;model.updateSnapshot(snapshot);
        QVERIFY(model.floodingMetrics()[4].contains(QStringLiteral("IVI 수신 큐 유실: 0건")));
        snapshot.ivi_socket_drops=4;model.updateSnapshot(snapshot);
        QVERIFY(model.floodingMetrics()[4].contains(QStringLiteral("IVI 수신 큐 유실: 4건")));
        QVERIFY(model.floodingMetrics()[4].contains(QStringLiteral("인터페이스 오류: 미측정")));
        snapshot.ivi_socket_drops.reset();model.updateSnapshot(snapshot);
        QVERIFY(model.floodingMetrics()[4].contains(QStringLiteral("IVI 수신 큐 유실: 미측정")));
        QVERIFY(model.floodingMetrics()[1].contains(QStringLiteral("12건")));
        QVERIFY(model.floodingMetrics()[2].contains(QStringLiteral("123 ms")));
        QVERIFY(model.floodingMetrics()[3].contains(QStringLiteral("120.0")));
    }

    void newSameTypeIncidentReopensButRevisionDoesNot(){
        DashboardViewModel model;ivi::VehicleSnapshot snapshot;
        QSignalSpy recorded(&model,&DashboardViewModel::eventRecorded);
        snapshot.session_protocol=true;snapshot.security_observation_ready=true;
        snapshot.observed_condition_mask=8;model.updateSnapshot(snapshot);model.dismissPopup();
        const auto beforeIdentity=recorded.size();
        capstone::session_v2::Nonce first{};first[0]=1;
        snapshot.security_incident_ids[3]=first;model.updateSnapshot(snapshot);
        QVERIFY(!model.popupVisible()); // first identity enriches the existing observation
        QCOMPARE(recorded.size(),beforeIdentity+1);
        const auto identified=qvariant_cast<QJsonObject>(recorded.last().at(0));
        QCOMPARE(identified.value("category").toString(),QStringLiteral("ids-identified"));
        QCOMPARE(identified.value("typed_incidents").toArray().at(0).toObject().value("attack_type").toString(),QStringLiteral("flooding"));
        model.updateSnapshot(snapshot);QVERIFY(!model.popupVisible());
        QCOMPARE(recorded.size(),beforeIdentity+1);
        auto second=first;second[0]=2;snapshot.security_incident_ids[3]=second;
        model.updateSnapshot(snapshot);QVERIFY(model.popupVisible());
        QCOMPARE(model.popupTitle(),QStringLiteral("Flooding"));
        model.dismissPopup();model.updateSnapshot(snapshot);QVERIFY(!model.popupVisible());
    }
    void sessionAttackPopupDismissalAndRecurrence(){
        DashboardViewModel model;ivi::VehicleSnapshot snapshot;
        snapshot.session_protocol=true;snapshot.security_observation_ready=true;
        snapshot.observed_condition_mask=8;model.updateSnapshot(snapshot);
        QVERIFY(model.popupVisible());QCOMPARE(model.popupTitle(),QStringLiteral("Flooding"));
        model.dismissPopup();QVERIFY(!model.popupVisible());
        model.updateSnapshot(snapshot);QVERIFY(!model.popupVisible());
        QCOMPARE(model.securityTitle(),QStringLiteral("Flooding"));
        snapshot.observed_condition_mask=10;model.updateSnapshot(snapshot);
        QVERIFY(model.popupVisible());QCOMPARE(model.popupTitle(),QStringLiteral("Replay / Flooding"));
        model.dismissPopup();snapshot.observed_condition_mask=0;model.updateSnapshot(snapshot);
        QVERIFY(!model.popupVisible());
        snapshot.observed_condition_mask=8;model.updateSnapshot(snapshot);
        QVERIFY(model.popupVisible());
    }
    void securityCardShowsActiveThenBriefConfirmedRecovery(){
        DashboardViewModel model;ivi::VehicleSnapshot snapshot;
        snapshot.session_protocol=true;snapshot.security_observation_ready=true;
        snapshot.observed_condition_mask=2;model.updateSnapshot(snapshot);
        QCOMPARE(model.securityCardState(),QStringLiteral("active"));
        QVERIFY(model.rejectionSummary().contains(QStringLiteral("확인 중")));
        QVERIFY(!model.rejectionSummary().contains(QStringLiteral("거부 기록 없음")));
        model.dismissPopup();
        QCOMPARE(model.securityCardState(),QStringLiteral("active"));
        snapshot.observed_condition_mask=0;model.updateSnapshot(snapshot);
        QCOMPARE(model.securityCardState(),QStringLiteral("recovered"));
        QCOMPARE(model.securityTitle(),QStringLiteral("공격 징후 종료"));
        QVERIFY(!model.popupVisible());
        QTRY_COMPARE_WITH_TIMEOUT(model.securityCardState(),QStringLiteral("normal"),2500);
        snapshot.observed_condition_mask=2;model.updateSnapshot(snapshot);
        snapshot.observed_condition_mask=0;snapshot.security_observation_ready=false;model.updateSnapshot(snapshot);
        QCOMPARE(model.securityCardState(),QStringLiteral("checking"));
    }
    void sameIncidentRedetectionRecordsHistoryWithoutPopup(){
        DashboardViewModel model;ivi::VehicleSnapshot snapshot;
        QSignalSpy recorded(&model,&DashboardViewModel::eventRecorded);
        snapshot.session_protocol=true;snapshot.security_observation_ready=true;
        snapshot.observed_condition_mask=8;
        capstone::session_v2::Nonce incident{};incident[0]=1;
        snapshot.security_incident_ids[3]=incident;
        model.updateSnapshot(snapshot);model.dismissPopup();
        const auto before=recorded.size();
        snapshot.security_recurrence_counts[3]=1;
        model.updateSnapshot(snapshot);
        QVERIFY(!model.popupVisible());
        QCOMPARE(recorded.size(),before+1);
        const auto event=qvariant_cast<QJsonObject>(recorded.last().at(0));
        QCOMPARE(event.value("category").toString(),QStringLiteral("ids-repeat"));
        QVERIFY(event.value("summary").toString().contains(QStringLiteral("Flooding 재탐지")));
        QCOMPARE(event.value("typed_incidents").toArray().at(0).toObject().value("attack_type").toString(),QStringLiteral("flooding"));
        model.updateSnapshot(snapshot);
        QCOMPARE(recorded.size(),before+1);
    }
    void authenticatedObservationNamesAndUnknownCoverage(){
        DashboardViewModel model;ivi::VehicleSnapshot snapshot;
        snapshot.session_protocol=true;snapshot.security_observation_ready=true;
        snapshot.observed_condition_mask=10;
        model.updateSnapshot(snapshot);
        QCOMPARE(model.securityTitle(),QStringLiteral("Replay / Flooding"));
        QVERIFY(model.securityDescription().contains(QStringLiteral("탐지")));
        QVERIFY(!model.securityDescription().contains(QStringLiteral("차단 완료")));
        snapshot.security_observation_ready=false;model.updateSnapshot(snapshot);
        QCOMPARE(model.securityTitle(),QStringLiteral("Replay / Flooding"));
        QVERIFY(model.securityDescription().contains(QStringLiteral("마지막")));
        snapshot.observed_condition_mask=0;model.updateSnapshot(snapshot);
        QCOMPARE(model.securityTitle(),QStringLiteral("보안 감시 확인 중"));
    }

    void olderQueuedSnapshotCannotUndoNewerPublication(){
        DashboardViewModel model;ivi::VehicleSnapshot newer;
        newer.snapshot_revision=20;newer.vehicle.valid=true;newer.vehicle.soc_percent=80;
        newer.vehicle.fail_safe_state=3;newer.vehicle.fail_safe_reason=4;
        model.updateSnapshot(newer);
        auto older=newer;older.snapshot_revision=19;older.vehicle.soc_percent=20;older.vehicle.fail_safe_state=0;older.vehicle.fail_safe_reason=0;
        model.updateSnapshot(older);
        QCOMPARE(model.soc(),80.0);QVERIFY(model.failSafeOverlayActive());
    }
    void authenticatedConnectionIsSeparateFromRiskAndSecurityCoverage(){
        DashboardViewModel model;ivi::VehicleSnapshot snapshot;
        snapshot.session_protocol=true;snapshot.connection_stage="authenticating";
        model.updateSnapshot(snapshot);
        QCOMPARE(model.connectionLabel(),QStringLiteral("연결 확인 중"));
        QCOMPARE(model.securityTitle(),QStringLiteral("보안 감시 확인 중"));
        snapshot.connection_stage="connected";snapshot.vehicle.valid=true;snapshot.vehicle.stale=false;
        snapshot.fail_safe_known=true;snapshot.vehicle.fail_safe_state=3;snapshot.vehicle.fail_safe_reason=4;snapshot.vehicle.temperature_c=65;
        model.updateSnapshot(snapshot);
        QCOMPARE(model.connectionLabel(),QStringLiteral("현재 수신값"));
        QCOMPARE(model.statusTitle(),QStringLiteral("[CRITICAL] 배터리 과열 위험"));
        QVERIFY(model.failSafeKnown());QVERIFY(model.failSafeOverlayActive());
        model.dismissPopup();snapshot.connection_stage="synchronizing";snapshot.vehicle.stale=true;
        model.updateSnapshot(snapshot);
        QCOMPARE(model.connectionLabel(),QStringLiteral("배터리 상태 확인 중"));QVERIFY(model.failSafeOverlayActive());
    }
    void connectionRetriesKeepOneLabelUntilRecoveryOrPersistentFailure(){
        DashboardViewModel model;ivi::VehicleSnapshot s;
        s.session_protocol=true;s.connection_stage="authenticating";
        s.vehicle.valid=true;s.vehicle.stale=true;s.vehicle.fail_safe_state=3;
        s.vehicle.fail_safe_reason=4;s.vehicle.temperature_c=65;s.fail_safe_known=true;
        model.updateSnapshot(s);model.dismissPopup();
        for(unsigned i=0;i<3;++i){
            s.connection_stage="fault";model.updateSnapshot(s);
            QCOMPARE(model.connectionLabel(),QStringLiteral("연결 확인 중"));
            s.connection_stage="authenticating";model.updateSnapshot(s);
            QCOMPARE(model.connectionLabel(),QStringLiteral("연결 확인 중"));
        }
        QVERIFY(model.stale());QVERIFY(!model.secocVerified());
        QVERIFY(model.failSafeOverlayActive());
        QTRY_COMPARE_WITH_TIMEOUT(model.connectionLabel(),QStringLiteral("연결 확인 필요"),11000);
        for(const auto* stage:{"fault","authenticating","waiting","synchronizing","waiting-data"}){
            s.connection_stage=stage;model.updateSnapshot(s);
            QCOMPARE(model.connectionLabel(),QStringLiteral("연결 확인 필요"));
        }
        s.connection_stage="connected";s.vehicle.stale=false;model.updateSnapshot(s);
        QCOMPARE(model.connectionLabel(),QStringLiteral("현재 수신값"));
        QVERIFY(model.failSafeOverlayActive());
        s.connection_stage="fault";s.vehicle.stale=true;model.updateSnapshot(s);
        QCOMPARE(model.connectionLabel(),QStringLiteral("연결 확인 중"));
        s.connection_stage="restart-announced";model.updateSnapshot(s);
        QCOMPARE(model.connectionLabel(),QStringLiteral("ECU 재시작 중…"));
        s.session_protocol=false;s.vehicle.valid=false;model.updateSnapshot(s);
        QCOMPARE(model.connectionLabel(),QStringLiteral("연결 대기"));
    }
    void successfulConnectionCancelsPendingFailureNotice(){
        DashboardViewModel model;ivi::VehicleSnapshot s;
        s.session_protocol=true;s.connection_stage="fault";model.updateSnapshot(s);
        s.connection_stage="connected";s.vehicle.valid=true;s.vehicle.stale=false;
        model.updateSnapshot(s);
        QTest::qWait(10100);
        QCOMPARE(model.connectionLabel(),QStringLiteral("현재 수신값"));
        s.connection_stage="authenticating";s.vehicle.stale=true;model.updateSnapshot(s);
        QCOMPARE(model.connectionLabel(),QStringLiteral("연결 확인 중"));
    }
    void programRecoveryDoesNotClearBatteryProtection(){
        DashboardViewModel model;ivi::VehicleSnapshot snapshot;
        snapshot.session_protocol=true;snapshot.fail_safe_known=true;
        snapshot.vehicle.valid=true;snapshot.vehicle.fail_safe_state=3;snapshot.vehicle.fail_safe_reason=4;snapshot.vehicle.temperature_c=65;
        snapshot.connection_stage="restart-announced";model.updateSnapshot(snapshot);
        QCOMPARE(model.connectionLabel(),QStringLiteral("ECU 재시작 중…"));
        snapshot.connection_stage="restoring";model.updateSnapshot(snapshot);
        QCOMPARE(model.connectionLabel(),QStringLiteral("ECU 연결 복구 중…"));
        snapshot.connection_stage="program-restored";snapshot.vehicle.stale=false;model.updateSnapshot(snapshot);
        QCOMPARE(model.connectionLabel(),QStringLiteral("ECU 프로그램 복구 완료"));
        QCOMPARE(model.statusTitle(),QStringLiteral("[CRITICAL] 배터리 과열 위험"));
        QVERIFY(model.failSafeOverlayActive());
    }
    void actualReplayDecisionShowsDataRejectionButExpiryDoesNotReuseProof(){
        namespace wire=capstone::session_v2;
        DashboardViewModel model;ivi::VehicleSnapshot snapshot;
        snapshot.session_protocol=true;snapshot.secoc_failure_count=1;snapshot.rejection_record_revision=1;
        wire::ReceiveDecision decision{wire::ReceiveReason::Replay,0x100,wire::Payload{},wire::Payload{},true};
        snapshot.local_rejection_record=wire::rejectionRecord(decision,wire::Context{1,{},{}},wire::diagnosticUuid(),wire::diagnosticUuid());
        snapshot.last_rejection_message="reason=COUNTER_REPLAY";
        model.updateSnapshot(snapshot);
        QCOMPARE(model.popupTitle(),QStringLiteral("재전송 데이터를 거부했습니다"));
        QVERIFY(!model.rejectionSummary().contains(QStringLiteral("차단 완료")));
        model.dismissPopup();++snapshot.secoc_failure_count;snapshot.last_rejection_message="reason=AUTH_EXPIRED";
        model.updateSnapshot(snapshot);
        QCOMPARE(model.popupTitle(),QStringLiteral("일부 데이터 확인이 지연됐습니다"));
    }
    void incompleteAuthenticationIsDelayNotSuccessfulAttackBlock(){
        DashboardViewModel model;ivi::VehicleSnapshot snapshot;
        snapshot.session_protocol=true;snapshot.secoc_failure_count=1;
        snapshot.last_message="Authenticated session BMS data published";
        snapshot.last_rejection_message="reason=AUTH_EXPIRED session=1";
        model.updateSnapshot(snapshot);
        QCOMPARE(model.popupTitle(),QStringLiteral("일부 데이터 확인이 지연됐습니다"));
        QCOMPARE(model.popupKind(),QStringLiteral("warning"));
        QVERIFY(!model.rejectionSummary().contains(QStringLiteral("차단 완료")));
    }
    void initialStateHidesMeasurements() {
        DashboardViewModel model;
        QVERIFY(!model.valid());
        QVERIFY(!model.measurementsAvailable());
        QCOMPARE(model.sensorState(), QStringLiteral("UNSUPPORTED_LEGACY_WIRE"));
        QVERIFY(!model.sensorStateWarning());
        QVERIFY(!model.failSafeOverlayActive());
    }

    void mapsStateAndFullScreenWarning() {
        DashboardViewModel model;
        ivi::VehicleSnapshot snapshot;
        snapshot.vehicle.valid = true;
        snapshot.vehicle.stale = true;
        snapshot.vehicle.soc_percent = 12.5;
        snapshot.vehicle.sensor_state = 4;
        snapshot.vehicle.fail_safe_state = 2;
        snapshot.vehicle.fail_safe_reason = 7;
        snapshot.last_good_age_ms = 450;

        model.updateSnapshot(snapshot);
        QVERIFY(model.measurementsAvailable());
        QVERIFY(model.sensorUsesLastGood());
        QCOMPARE(model.lastGoodAgeMs(), qulonglong{450});
        QCOMPARE(model.failSafeState(), QStringLiteral("CRITICAL"));
        QCOMPARE(model.failSafeReason(), QStringLiteral("WATCHDOG_RESTART_FAILED"));
        QVERIFY(model.failSafeOverlayActive());
    }

    void socBandUsesSpecifiedBoundaries() {
        DashboardViewModel model;
        ivi::VehicleSnapshot snapshot;
        snapshot.vehicle.valid = true;

        snapshot.vehicle.soc_percent = 50.0;
        model.updateSnapshot(snapshot);
        QCOMPARE(model.socBand(), QStringLiteral("high"));
        snapshot.vehicle.soc_percent = 49.5;
        model.updateSnapshot(snapshot);
        QCOMPARE(model.socBand(), QStringLiteral("medium"));
        snapshot.vehicle.soc_percent = 20.0;
        model.updateSnapshot(snapshot);
        QCOMPARE(model.socBand(), QStringLiteral("medium"));
        snapshot.vehicle.soc_percent = 19.5;
        model.updateSnapshot(snapshot);
        QCOMPARE(model.socBand(), QStringLiteral("low"));

        snapshot.vehicle.valid = false;
        model.updateSnapshot(snapshot);
        QCOMPARE(model.socBand(), QStringLiteral("unavailable"));
    }

    void acknowledgementCarriesObservedSequence() {
        DashboardViewModel model;
        ivi::VehicleSnapshot snapshot;
        snapshot.security_alert = ivi::SecurityAlert{4, 1.5, 0x100, 1};
        snapshot.security_alert_sequence = 42;
        model.updateSnapshot(snapshot);

        QSignalSpy acknowledgement(
            &model, &DashboardViewModel::securityAlertAcknowledgementRequested);
        model.acknowledgeSecurityAlert();
        QCOMPARE(acknowledgement.count(), 1);
        QCOMPARE(acknowledgement.takeFirst().at(0).toULongLong(), qulonglong{42});
    }

    void popupCloseRetainsRiskSecurityAndHistory() {
        DashboardViewModel model;
        ivi::VehicleSnapshot snapshot;
        snapshot.vehicle.valid = true;
        snapshot.vehicle.fail_safe_state = 2;
        snapshot.vehicle.fail_safe_reason = 2;
        model.updateSnapshot(snapshot);
        QVERIFY(model.popupVisible());
        QVERIFY(model.failSafeKnown());
        QVERIFY(model.failSafeOverlayActive());
        const auto count = model.eventHistory().size();
        model.dismissPopup();
        QVERIFY(!model.popupVisible());
        QVERIFY(model.failSafeOverlayActive());
        QCOMPARE(model.eventHistory().size(), count);
        snapshot.security_alert = ivi::SecurityAlert{2, 1.0, 0x100, 1};
        snapshot.security_alert_sequence = 1;
        model.updateSnapshot(snapshot);
        QCOMPARE(model.securityTitle(), QStringLiteral("Replay"));
        model.dismissPopup();
        snapshot.security_alert_sequence = 2;
        model.updateSnapshot(snapshot);
        QVERIFY(!model.popupVisible()); // repeated reports of the same active type
        snapshot.security_alert = ivi::SecurityAlert{4, 1.0, 0x100, 2};
        snapshot.security_alert_sequence = 3;
        model.updateSnapshot(snapshot);
        QVERIFY(model.securityTitle().contains(QStringLiteral("Replay")));
        QVERIFY(model.securityTitle().contains(QStringLiteral("Flooding")));
        model.dismissPopup();
        snapshot.security_alert.reset();
        model.updateSnapshot(snapshot);
        QVERIFY(model.securityTitle().contains(QStringLiteral("Replay"))); // retain result after alert clear
        snapshot.security_alert = ivi::SecurityAlert{2, 1.0, 0x100, 3};
        snapshot.security_alert_sequence = 4;
        model.updateSnapshot(snapshot);
        QVERIFY(model.popupVisible()); // new service episode
    }

    void actualServiceRejectionIsNotAttackAttribution() {
        DashboardViewModel model;
        const ivi::SecOcKey key{};
        ivi::VehicleDataService service(key);
        service.registerObserver([&](const auto& snapshot) { model.updateSnapshot(snapshot); });
        const ivi::CanPayload bms{150,180,0x10,0x68,0xff,0xec,65,0};
        const auto now = ivi::VehicleDataService::Clock::now();
        service.processFrame(0x100, bms, now);
        service.processFrame(0x102, ivi::CanPayload{}, now);
        QVERIFY(model.rejectionSummary().contains(QStringLiteral("인증값")));
        QVERIFY(model.popupVisible());
        QVERIFY(!model.popupTitle().contains(QStringLiteral("Replay")));
        QVERIFY(!model.measurementsAvailable());
        model.dismissPopup();
        const auto saved = model.rejectionSummary();
        const auto mac = ivi::SecOcVerifier(key).computeTruncatedMac(0x100, 0, bms);
        service.processFrame(0x102, {mac[0],mac[1],mac[2],mac[3],0,0,0,0}, now);
        QCOMPARE(model.soh(), 90.0);
        QCOMPARE(model.rejectionSummary(), saved);
        QVERIFY(!model.popupVisible());
        QVERIFY(!model.failSafeKnown()); // BMS publication does not prove current Fail-safe state
    }

    void boundedHistoryAndDangerPriority() {
        DashboardViewModel model;
        ivi::VehicleSnapshot snapshot;
        snapshot.vehicle.valid=true;
        snapshot.vehicle.fail_safe_state=3;
        snapshot.vehicle.fail_safe_reason=4;
        model.updateSnapshot(snapshot);
        const auto title=model.popupTitle();
        snapshot.security_alert=ivi::SecurityAlert{4,1.0,0,1};
        snapshot.security_alert_sequence=1;
        model.updateSnapshot(snapshot);
        QCOMPARE(model.popupTitle(),title);
        QVERIFY(model.securityTitle().contains(QStringLiteral("Flooding")));
        for(int i=0;i<150;++i){
            snapshot.vehicle.stale=!snapshot.vehicle.stale;
            model.updateSnapshot(snapshot);
        }
        QVERIFY(model.eventHistory().size()<=100);
        QVERIFY(model.recentEvents().size()<=2);
    }

    void workerUpdateIsQueuedToOwnerThread() {
        DashboardViewModel model;
        QSignalSpy changes(&model, &DashboardViewModel::dataChanged);
        ivi::VehicleSnapshot snapshot;
        snapshot.vehicle.valid = true;
        snapshot.vehicle.soc_percent = 88.0;

        std::thread worker([&model, snapshot]() { model.updateSnapshot(snapshot); });
        worker.join();

        QTRY_COMPARE(changes.count(), 1);
        QVERIFY(model.valid());
        QCOMPARE(model.soc(), 88.0);
        QCOMPARE(model.thread(), QThread::currentThread());
    }

    void measurementCarriesT1ThroughT3Once() {
        DashboardViewModel model;
        QSignalSpy measurements(&model, &DashboardViewModel::measurementReady);
        ivi::VehicleSnapshot snapshot;
        snapshot.vehicle.valid = true;
        snapshot.measurement_sequence = 7;
        snapshot.t1_received_ns = 100;
        snapshot.t2_published_ns = 200;

        model.updateSnapshot(snapshot);
        QCOMPARE(measurements.count(), 1);
        const auto values = measurements.takeFirst();
        QCOMPARE(values.at(0).toULongLong(), qulonglong{7});
        QCOMPARE(values.at(1).toULongLong(), qulonglong{100});
        QCOMPARE(values.at(2).toULongLong(), qulonglong{200});
        QVERIFY(values.at(3).toULongLong() >= qulonglong{200});

        model.updateSnapshot(snapshot);
        QCOMPARE(measurements.count(), 0);
    }

    void queuedUpdateLatencyMeetsHostTarget() {
        DashboardViewModel model;
        std::vector<qint64> latencies;
        latencies.reserve(100);

        for (int sample = 0; sample < 100; ++sample) {
            ivi::VehicleSnapshot snapshot;
            snapshot.vehicle.valid = true;
            snapshot.vehicle.soc_percent = static_cast<double>(sample);
            QEventLoop loop;
            QTimer timeout;
            timeout.setSingleShot(true);
            connect(&model, &DashboardViewModel::dataChanged, &loop, &QEventLoop::quit,
                    Qt::SingleShotConnection);
            connect(&timeout, &QTimer::timeout, &loop, &QEventLoop::quit);

            QElapsedTimer timer;
            timer.start();
            timeout.start(1000);
            std::thread worker([&model, snapshot]() { model.updateSnapshot(snapshot); });
            loop.exec();
            worker.join();
            QVERIFY2(timeout.isActive(), "queued ViewModel update timed out");
            latencies.push_back(timer.nsecsElapsed());
        }

        std::sort(latencies.begin(), latencies.end());
        const double average_ms =
            static_cast<double>(std::accumulate(latencies.begin(), latencies.end(), qint64{0})) /
            static_cast<double>(latencies.size()) / 1000000.0;
        const double p99_ms = static_cast<double>(latencies[98]) / 1000000.0;
        qInfo() << "DashboardViewModel T2-T3 host latency: average" << average_ms
                << "ms, p99" << p99_ms << "ms, samples" << latencies.size();
        QVERIFY2(average_ms <= 20.0, "average queued update latency exceeded 20 ms");
        QVERIFY2(p99_ms <= 50.0, "p99 queued update latency exceeded 50 ms");
    }
};

QTEST_GUILESS_MAIN(DashboardViewModelTest)

#include "test_dashboard_view_model.moc"
