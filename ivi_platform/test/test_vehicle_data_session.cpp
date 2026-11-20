#include "vehicle_data_service.h"
#include "rejection_record.h"
#include "test_support.h"
#include <deque>
#include <algorithm>

namespace {
namespace wire=capstone::session_v2;
using Clock=ivi::VehicleDataService::Clock;
wire::ExchangeLimits limits(){return {20,200,800,60,500,50,64,512,{60,5,100,4,8,4,256},{1000,100,4,64}};}
ivi::SecOcKey key(){ivi::SecOcKey out{};for(unsigned i=0;i<32;++i)out[i]=i;return out;}
Clock::time_point at(std::uint64_t ms,std::uint64_t remainder=0){return Clock::time_point(std::chrono::nanoseconds(ms*1000000+remainder));}
struct Rig{
    ivi::VehicleDataService service;
    wire::Exchange ecu{wire::Endpoint::Ecu,key(),limits()};
    std::deque<std::pair<bool,wire::Frame>> pending;
    std::uint64_t now=0;
    unsigned notifications=0;
    std::vector<wire::DiagnosticMessage> reports;
    Rig(bool reporting=false){if(reporting)service.configureRejectionReports(4,2,1000);EXPECT_TRUE(service.enableSession(key(),limits(),at(0)));
        service.registerObserver([&](const auto&){++notifications;});}
    void enqueue(bool to_ecu,const std::vector<wire::Frame>& frames){for(const auto& frame:frames)pending.push_back({to_ecu,frame});}
    void pump(){unsigned steps=0;while(!pending.empty()){
        EXPECT_TRUE(++steps<2000);const auto item=pending.front();pending.pop_front();++now;
        if(item.first){
            enqueue(false,ecu.receive(item.second,now));
            const auto& diagnostic=ecu.lastDiagnosticResult();
            if(diagnostic.code==wire::DiagnosticResultCode::Message && diagnostic.message && diagnostic.message->kind==wire::DiagnosticKind::Rejection)
                reports.push_back(*diagnostic.message);
        }
        else enqueue(true,service.processSessionFrame(item.second,at(now,123456),at(now,456789)).outgoing);
    }}
    void advance(unsigned ms){now+=ms;enqueue(false,ecu.poll(now));enqueue(true,service.pollSession(at(now,456789)).outgoing);pump();}
    void settle(){for(unsigned i=0;i<100;++i){pump();if(ecu.dataOpen()&&service.latest().fail_safe_known)return;advance(10);}
        throw std::runtime_error("service test handshake did not open");}
    void open(){enqueue(false,ecu.start(0));settle();}
    std::vector<wire::Frame> bms(unsigned soc=150){
        return ecu.publishData(0x100,wire::Payload{static_cast<std::uint8_t>(soc),180,0x10,0x68,0xff,0xec,65,0},++now);
    }
    void send(const std::vector<wire::Frame>& frames){enqueue(false,frames);pump();advance(5);}
};
void physicalMeasurementTests(){
    const auto instance=wire::diagnosticUuid();
    auto node=[&]{std::vector<std::uint8_t> b(56,0);std::copy(instance.begin(),instance.end(),b.begin());
        b[32]=2;b[33]=1;b[34]=2;b[35]=0xff;b[53]=1;return b;};
    wire::PhysicalMeasurement m;m.instance=instance;m.configuration[0]=1;m.nominal_capacity_mah=2550;m.max_interval_ms=3000;
    m.sequence=3;m.voltage_v=3.85;m.current_a=-.3711;m.temperature_c=20.125;
    m.ina_quality=m.temperature_quality=2;m.ina_age_ms=800;m.temperature_age_ms=0;
    auto send=[](Rig& r,const wire::PhysicalMeasurement& value){
        r.send(r.ecu.makeDiagnostic(wire::DiagnosticKind::PhysicalMeasurement,wire::encodePhysicalMeasurement(value))->frames);
    };
    Rig rig;rig.open();
    send(rig,m);EXPECT_TRUE(!rig.service.latest().physical_measurement); // no identity before NodeStatus
    rig.send(rig.ecu.makeDiagnostic(wire::DiagnosticKind::NodeStatus,node())->frames);
    send(rig,m);auto s=rig.service.latest();EXPECT_TRUE(s.physical_measurement.has_value());
    EXPECT_TRUE(s.physical_valid[0]&&s.physical_valid[1]&&s.physical_valid[2]);
    EXPECT_TRUE(!s.physical_valid[3]&&!s.physical_valid[4]);EXPECT_TRUE(!s.fail_safe_known);
    EXPECT_TRUE(std::abs(s.vehicle.current_a+.3711)<1e-9);EXPECT_TRUE(s.connection_stage=="connected");
    const auto generation=s.session_generation;
    rig.advance(1000);s=rig.service.latest();EXPECT_EQ(s.session_generation,generation);EXPECT_TRUE(s.physical_valid[0]);
    auto stale=m;stale.sequence=2;send(rig,stale);EXPECT_EQ(rig.service.latest().physical_measurement->sequence,3u);
    auto mixed=m;mixed.configuration[0]=2;mixed.sequence=4;send(rig,mixed);
    EXPECT_EQ(rig.service.latest().physical_measurement->configuration[0],1u);
    auto same=m;same.ina_age_ms=900;same.temperature_age_ms=100;send(rig,same);
    auto regressed=m;send(rig,regressed);EXPECT_EQ(rig.service.latest().physical_measurement->ina_age_ms,900u);
    m.sequence=4;m.temperature_c.reset();m.temperature_quality=4;send(rig,m);s=rig.service.latest();
    EXPECT_TRUE(s.physical_valid[0]&&!s.physical_valid[2]);
    auto old_valid=m;old_valid.temperature_c=20.125;old_valid.temperature_quality=2;send(rig,old_valid);
    EXPECT_TRUE(!rig.service.latest().physical_valid[2]); // same sample cannot revive a failed channel
    m.sequence=5;m.soc_basis=1;m.soc_percent=0;m.soh_basis=1;m.soh_percent=90;
    // A basis change requires a new instance/config, so reject it here.
    send(rig,m);EXPECT_TRUE(!rig.service.latest().physical_valid[3]);
    rig.send(rig.ecu.makeDiagnostic(wire::DiagnosticKind::NodeStatus,node())->frames);
    rig.advance(2200);s=rig.service.latest();EXPECT_TRUE(!s.physical_valid[0]&&!s.physical_valid[2]);
    // An authenticated foreign-instance message cannot revive stale measurements.
    m.instance=wire::diagnosticUuid();send(rig,m);EXPECT_TRUE(!rig.service.latest().physical_valid[0]);
    // A valid sensor report near its age limit can expire before the next
    // report arrives. This is data freshness, not proof of a broken sensor.
    Rig timing;timing.open();
    timing.send(timing.ecu.makeDiagnostic(wire::DiagnosticKind::NodeStatus,node())->frames);
    m.instance=instance;m.configuration[0]=1;m.sequence=3;m.soc_basis=m.soh_basis=0;
    m.soc_percent.reset();m.soh_percent.reset();m.temperature_c=20.125;m.temperature_quality=2;
    m.ina_age_ms=2900;m.temperature_age_ms=2100;
    send(timing,m);EXPECT_TRUE(timing.service.latest().physical_valid[0]);
    timing.advance(101);auto expired=timing.service.latest();
    EXPECT_FALSE(expired.physical_valid[0]);EXPECT_TRUE(expired.physical_valid[2]);
    EXPECT_EQ(expired.physical_measurement->ina_quality,2u);
    m.sequence++;m.ina_age_ms=800;m.temperature_age_ms=0;send(timing,m);
    EXPECT_TRUE(timing.service.latest().physical_valid[0]);
    // With a fresh sample each second the same 3s bound covers the observed
    // conversion/report phase offset without extending any stale-data limit.
    for(unsigned i=0;i<8;++i){
        timing.send(timing.ecu.makeDiagnostic(wire::DiagnosticKind::NodeStatus,node())->frames);
        m.sequence++;m.ina_age_ms=1500;m.temperature_age_ms=700;send(timing,m);
        timing.advance(1000);EXPECT_TRUE(timing.service.latest().physical_valid[0]);
        EXPECT_TRUE(timing.service.latest().physical_valid[2]);
    }
    Rig automatic;automatic.open();
    automatic.send(automatic.ecu.makeDiagnostic(wire::DiagnosticKind::NodeStatus,node())->frames);
    m.sequence=3;m.soc_basis=2;m.soc_percent.reset();send(automatic,m);
    EXPECT_FALSE(automatic.service.latest().physical_valid[3]);
    m.sequence++;m.soc_percent=0;send(automatic,m);
    EXPECT_TRUE(automatic.service.latest().physical_valid[3]);
    EXPECT_EQ(automatic.service.latest().vehicle.soc_percent,0.0);
    // A late/manual-basis report cannot change the model within this lineage.
    m.sequence++;m.soc_basis=1;m.soc_percent=80;send(automatic,m);
    EXPECT_EQ(automatic.service.latest().physical_measurement->soc_basis,2u);
    EXPECT_EQ(automatic.service.latest().vehicle.soc_percent,0.0);
}
void protectionLinkTests(){
    const auto instance=wire::diagnosticUuid(),lineage=wire::diagnosticUuid(),incident=wire::diagnosticUuid();
    auto node=[&](unsigned risk=0,unsigned reason=0,bool resume=false){
        std::vector<std::uint8_t> b(56,0);std::copy(instance.begin(),instance.end(),b.begin());
        b[32]=2;b[33]=resume?2:1;b[34]=2;b[35]=risk;b[36]=reason!=0;b[37]=reason;b[53]=1;
        b[52]=b[54]=resume;return b;
    };
    auto protection=[&](unsigned risk=0,unsigned reason=0,bool resume=false,unsigned revision=0){
        std::vector<std::uint8_t> b(56,0);std::copy(instance.begin(),instance.end(),b.begin());
        std::copy(lineage.begin(),lineage.end(),b.begin()+16);
        if(revision)std::copy(incident.begin(),incident.end(),b.begin()+32);
        b[48]=risk;b[49]=reason;b[50]=revision?(risk?1:2):0;b[51]=resume;
        for(unsigned i=0;i<4;++i)b[52+i]=static_cast<std::uint8_t>(revision>>(24-8*i));return b;
    };
    auto send=[](Rig& rig,wire::DiagnosticKind kind,const auto& body){
        const auto packet=rig.ecu.makeDiagnostic(kind,body);EXPECT_TRUE(packet.has_value());rig.send(packet->frames);
    };
    {
        Rig rig;rig.open();rig.send(rig.bms());EXPECT_TRUE(rig.service.latest().session_state_ready);
        send(rig,wire::DiagnosticKind::ProtectionStatus,protection());
        EXPECT_FALSE(rig.service.latest().protection_confirmed);
        send(rig,wire::DiagnosticKind::NodeStatus,node());EXPECT_TRUE(rig.service.latest().protection_confirmed);
        // A one-second metadata heartbeat must remain valid between reports;
        // the300ms BMS deadline is a different contract.
        for(unsigned i=0;i<10;++i){
            rig.send(rig.bms());rig.advance(90);EXPECT_TRUE(rig.service.latest().protection_confirmed);
        }
        send(rig,wire::DiagnosticKind::NodeStatus,node());
        send(rig,wire::DiagnosticKind::ProtectionStatus,protection());
        auto wrong=node();const auto other=wire::diagnosticUuid();std::copy(other.begin(),other.end(),wrong.begin());
        send(rig,wire::DiagnosticKind::NodeStatus,wrong);EXPECT_FALSE(rig.service.latest().protection_confirmed);
        send(rig,wire::DiagnosticKind::NodeStatus,node());EXPECT_TRUE(rig.service.latest().protection_confirmed);
        auto late_node=rig.ecu.makeDiagnostic(wire::DiagnosticKind::NodeStatus,wrong);
        send(rig,wire::DiagnosticKind::NodeStatus,node());rig.send(late_node->frames);
        EXPECT_TRUE(rig.service.latest().protection_confirmed);
        const auto before=rig.service.latest().session_generation;
        for(unsigned i=0;i<33;++i){rig.send(rig.bms());rig.advance(100);}
        EXPECT_EQ(rig.service.latest().session_generation,before);
        EXPECT_FALSE(rig.service.latest().protection_confirmed); // BMS is live, metadata has expired
        send(rig,wire::DiagnosticKind::NodeStatus,node());EXPECT_FALSE(rig.service.latest().protection_confirmed);
        send(rig,wire::DiagnosticKind::ProtectionStatus,protection());EXPECT_TRUE(rig.service.latest().protection_confirmed);
    }
    {
        Rig rig;rig.open();rig.send(rig.bms());
        send(rig,wire::DiagnosticKind::ProtectionStatus,protection(0,0,true));
        send(rig,wire::DiagnosticKind::NodeStatus,node());EXPECT_FALSE(rig.service.latest().protection_confirmed);
        send(rig,wire::DiagnosticKind::NodeStatus,node(0,0,true));EXPECT_TRUE(rig.service.latest().protection_confirmed);
    }
    {
        Rig rig;rig.open();rig.send(rig.bms());
        send(rig,wire::DiagnosticKind::NodeStatus,node());
        auto old=rig.ecu.makeDiagnostic(wire::DiagnosticKind::ProtectionStatus,protection());
        rig.send(old->frames);EXPECT_TRUE(rig.service.latest().protection_confirmed);
        rig.send(rig.ecu.setCurrentState(wire::Payload{1,1,3,0,0,0,0,0},++rig.now));
        rig.send(rig.ecu.publishData(0x101,wire::Payload{0,1,3,150,96,0,0,0},++rig.now));
        EXPECT_FALSE(rig.service.latest().protection_confirmed); // Node+diagnostic alone cannot override STATE
        send(rig,wire::DiagnosticKind::NodeStatus,node(1,3));
        send(rig,wire::DiagnosticKind::ProtectionStatus,protection(1,3,false,1));
        EXPECT_TRUE(rig.service.latest().protection_confirmed);
        send(rig,wire::DiagnosticKind::ProtectionStatus,protection(1,3,false,2));
        auto late=rig.ecu.makeDiagnostic(wire::DiagnosticKind::ProtectionStatus,protection(1,3,false,2));
        send(rig,wire::DiagnosticKind::ProtectionStatus,protection(1,3,false,1));
        EXPECT_FALSE(rig.service.latest().protection_confirmed);
        rig.send(late->frames);EXPECT_FALSE(rig.service.latest().protection_confirmed); // late valid frame cannot erase conflict
        send(rig,wire::DiagnosticKind::ProtectionStatus,protection(1,3,false,2));
        EXPECT_TRUE(rig.service.latest().protection_confirmed);
        send(rig,wire::DiagnosticKind::ProtectionStatus,protection(1,7,false,2));
        EXPECT_FALSE(rig.service.latest().protection_confirmed); // same revision changed its meaning
        send(rig,wire::DiagnosticKind::ProtectionStatus,protection(1,3,false,3));
        EXPECT_TRUE(rig.service.latest().protection_confirmed);
        rig.advance(3001);rig.settle();
        EXPECT_FALSE(rig.service.latest().protection_confirmed);
        EXPECT_FALSE(rig.service.latest().ecu_protection_status.has_value());
        rig.send(old->frames);EXPECT_FALSE(rig.service.latest().ecu_protection_status.has_value());
        send(rig,wire::DiagnosticKind::NodeStatus,node(1,3));
        send(rig,wire::DiagnosticKind::ProtectionStatus,protection(1,3,false,3));
        EXPECT_TRUE(rig.service.latest().protection_confirmed);
    }
}
void tests(){
    physicalMeasurementTests();
    protectionLinkTests();
    {
        Rig rig;rig.open();rig.send(rig.bms());
        const auto generation=rig.service.latest().session_generation;
        std::vector<std::uint8_t> body(56,0);const auto id=wire::diagnosticUuid();
        std::copy(id.begin(),id.end(),body.begin());body[33]=1;body[34]=2;body[53]=1;
        for(unsigned phase: {3u,5u}){
            body[32]=phase;
            for(unsigned repeat=0;repeat<4;++repeat){
                rig.send(rig.ecu.makeDiagnostic(wire::DiagnosticKind::NodeStatus,body)->frames);
                rig.advance(800);
                EXPECT_EQ(rig.service.latest().session_generation,generation);
                EXPECT_EQ(rig.service.latest().connection_stage,std::string(phase==3 ? "task-restoring" : "operator-required"));
                EXPECT_TRUE(rig.service.latest().vehicle.stale);
            }
        }
    }

    for(unsigned next: {0u,1u,2u}){
        Rig rig;rig.open();rig.send(rig.bms());
        rig.send(rig.ecu.publishData(0x101,wire::Payload{1,3,4,160,105,0,0,0},++rig.now));
        EXPECT_EQ(rig.service.latest().vehicle.fail_safe_state,3u);
        const auto reason=static_cast<std::uint8_t>(next==0 ? 5 : next);
        rig.send(rig.ecu.publishData(0x101,wire::Payload{3,static_cast<std::uint8_t>(next),reason,160,95,0,0,0},++rig.now));
        EXPECT_EQ(rig.service.latest().vehicle.fail_safe_state,next);
        EXPECT_EQ(rig.service.latest().vehicle.fail_safe_reason,reason);
    }

    {
        // Authenticated sensor outage keeps the session, not stale BMS freshness.
        Rig rig;rig.open();rig.send(rig.bms());
        const auto generation=rig.service.latest().session_generation;
        const auto soc=rig.service.latest().vehicle.soc_percent;
        auto status=[&](unsigned quality){
            std::vector<std::uint8_t> body(56,0);
            const auto id=wire::diagnosticUuid();std::copy(id.begin(),id.end(),body.begin());
            body[32]=2;body[33]=1;body[34]=quality;body[53]=quality==2;
            rig.send(rig.ecu.makeDiagnostic(wire::DiagnosticKind::NodeStatus,body)->frames);
        };
        status(4);
        EXPECT_TRUE(rig.service.latest().vehicle.stale);
        for(unsigned i=0;i<5;++i){rig.advance(800);status(4);}
        EXPECT_EQ(rig.service.latest().session_generation,generation);
        EXPECT_EQ(rig.service.latest().vehicle.soc_percent,soc);
        status(6);EXPECT_TRUE(rig.service.latest().vehicle.stale);
        // New valid BMS is needed: status alone cannot revive old measurements.
        status(2);EXPECT_TRUE(rig.service.latest().vehicle.stale);
        rig.send(rig.bms(120));
        EXPECT_EQ(rig.service.latest().vehicle.sensor_state,2u);
        EXPECT_FALSE(rig.service.latest().vehicle.stale);
        EXPECT_EQ(rig.service.latest().vehicle.soc_percent,60.0);
        status(4);rig.advance(3100);
        EXPECT_TRUE(rig.service.latest().session_generation!=generation ||
                    rig.service.latest().connection_stage=="authenticating");
    }

    {
        Rig rig;rig.open();rig.send(rig.bms());
        std::vector<std::uint8_t> body(52);body[6]=0x40;body[8]=0x80;
        body[16]=1;body[23]=1;body[34]=3;body[35]=0xe8;body[39]=20;
        body[46]=3;body[47]=0xe8;body[48]=1;body[50]=4;
        rig.send(rig.ecu.makeDiagnostic(wire::DiagnosticKind::Observation,body)->frames);
        EXPECT_EQ(rig.service.latest().observed_condition_mask,1u);
        rig.enqueue(false,rig.ecu.start(++rig.now));rig.settle();
        body[0]=1;body[48]=0;body[23]=1;
        rig.send(rig.ecu.makeDiagnostic(wire::DiagnosticKind::Observation,body)->frames);
        EXPECT_EQ(rig.service.latest().observed_condition_mask,1u);
        for(unsigned tick=2;tick<=7;++tick){
            for(unsigned step=0;step<10;++step){rig.send(rig.bms());rig.advance(90);}
            body[23]=tick;
            rig.send(rig.ecu.makeDiagnostic(wire::DiagnosticKind::Observation,body)->frames);
            if(tick<6)EXPECT_EQ(rig.service.latest().observed_condition_mask,1u);
        }
        EXPECT_EQ(rig.service.latest().observed_condition_mask,0u);
        EXPECT_EQ(rig.service.latest().reconciled_unknown_mask,1u);
    }

    {
        wire::IncidentRejectionLink link;
        const auto instance=wire::diagnosticUuid(),incident_id=wire::diagnosticUuid();
        wire::Context context{1,{}, {}};const auto session=wire::contextId(context);
        wire::ReceiveDecision decision{wire::ReceiveReason::Replay,0x100,wire::Payload{},wire::Payload{},true};
        const auto record=*wire::rejectionRecord(decision,context,instance,wire::diagnosticUuid());
        std::vector<std::uint8_t> incident(instance.begin(),instance.end());incident.insert(incident.end(),incident_id.begin(),incident_id.end());
        incident.resize(104,0);incident[32]=2;incident[33]=1;incident[35]=4;
        incident[39]=incident[43]=incident[47]=incident[51]=1;incident[56]=1;incident[59]=4;
        std::copy(record.begin()+36,record.end(),incident.begin()+60);
        EXPECT_TRUE(wire::validDiagnosticBody(0x302,wire::DiagnosticKind::IncidentStatus,incident));
        link.rejected(record,session,0);link.incident(incident,session,100);
        EXPECT_TRUE(link.matches(100)[1].has_value());
        link.rejected(record,session,110);EXPECT_TRUE(link.matches(110)[1].has_value()); // retransmission of same result UUID
        wire::IncidentRejectionLink conflicting;
        conflicting.rejected(record,session,100);conflicting.incident(incident,session,100);
        EXPECT_TRUE(conflicting.matches(100)[1].has_value());
        auto changed_reference=record;changed_reference[64]^=1;
        EXPECT_TRUE(wire::validDiagnosticBody(0x303,wire::DiagnosticKind::Rejection,changed_reference));
        conflicting.rejected(changed_reference,session,110);
        EXPECT_FALSE(conflicting.matches(110)[1].has_value());
        conflicting.rejected(record,session,120);conflicting.incident(incident,session,120);
        EXPECT_FALSE(conflicting.matches(120)[1].has_value()); // conflicting UUID keeps the bounded uncertainty guard.
        const auto second=*wire::rejectionRecord(decision,context,instance,wire::diagnosticUuid());
        link.rejected(second,session,120);EXPECT_FALSE(link.matches(120)[1].has_value());
        link.gap();link.incident(incident,session,130);EXPECT_FALSE(link.matches(130)[1].has_value());
        link.rejected(record,session,140);EXPECT_TRUE(link.matches(140)[1].has_value());
        EXPECT_FALSE(link.matches(3140)[1].has_value());
        auto foreign=session;foreign[0]^=1;link.rejected(record,foreign,3200);link.incident(incident,session,3200);
        EXPECT_FALSE(link.matches(3200)[1].has_value());
    }

    {
        const auto instance=wire::diagnosticUuid(),record_id=wire::diagnosticUuid();
        wire::ReceiveDecision expired{wire::ReceiveReason::OriginalExpired,0x100,wire::Payload{},std::nullopt,false};
        const auto body=wire::rejectionRecord(expired,std::nullopt,instance,record_id);
        EXPECT_TRUE(body.has_value());EXPECT_EQ((*body)[32],4u);EXPECT_EQ((*body)[33],0u);
        EXPECT_EQ((*body)[34],4u);EXPECT_EQ((*body)[36],1u);
        wire::ReceiveDecision incomplete{wire::ReceiveReason::Replay,0x100,wire::Payload{},std::nullopt,true};
        EXPECT_FALSE(wire::rejectionRecord(incomplete,std::nullopt,instance,record_id).has_value());
        ivi::VehicleDataService service;
        bool refused=false;try{service.configureRejectionReports(0,2,1000);}catch(const std::invalid_argument&){refused=true;}
        EXPECT_TRUE(refused);
    }

    {
        Rig rig(true);rig.open();const auto pair=rig.bms();rig.send(pair);
        const auto sequence=rig.service.latest().measurement_sequence;
        rig.send(pair);
        for(unsigned i=0;i<20 && rig.reports.empty();++i)rig.advance(5);
        EXPECT_EQ(rig.service.latest().measurement_sequence,sequence);
        EXPECT_TRUE(!rig.reports.empty());
        const auto& body=rig.reports.back().body;
        EXPECT_EQ(body[32],7u);EXPECT_EQ(body[33],1u);EXPECT_EQ(body[34],1u);EXPECT_EQ(body[36],2u);
        EXPECT_TRUE(wire::validDiagnosticBody(0x303,wire::DiagnosticKind::Rejection,body));
        EXPECT_TRUE(rig.service.latest().local_rejection_record.has_value());
    }

    {
        ivi::PublicationMeter meter;
        meter.observe(1000000000);
        EXPECT_EQ(meter.value().authenticated_bms,1u);
        EXPECT_FALSE(meter.value().mean_interval_us.has_value());
        meter.observe(1100000000);meter.observe(1300000000);
        EXPECT_NEAR(*meter.value().mean_interval_us,150000.0,0.001);
        EXPECT_EQ(*meter.value().max_interval_us,200000u);
        bool denied=false;try{meter.observe(1200000000);}catch(const std::invalid_argument&){denied=true;}
        EXPECT_TRUE(denied);EXPECT_EQ(meter.value().authenticated_bms,3u);
        meter.reset();EXPECT_EQ(meter.value().authenticated_bms,0u);
        EXPECT_FALSE(meter.value().max_interval_us.has_value());
    }
    {
        Rig observation;
        observation.open();observation.send(observation.bms());
        std::vector<std::uint8_t> body(52);body[6]=0x40;body[8]=0x80;
        body[16]=1;body[23]=2;body[34]=3;body[35]=0xe8;body[39]=20;
        body[46]=3;body[47]=0xe8;body[48]=1;body[50]=3;
        auto packet=observation.ecu.makeDiagnostic(wire::DiagnosticKind::Observation,body);
        EXPECT_TRUE(packet.has_value());observation.send(packet->frames);
        EXPECT_TRUE(observation.service.latest().security_observation_ready);
        EXPECT_NEAR(*observation.service.latest().ecu_observed_fps,20.0,0.001);
        EXPECT_EQ(*observation.service.latest().ecu_observed_drops,0u);
        EXPECT_EQ(observation.service.latest().observed_condition_mask,1u);
        std::vector<std::uint8_t> incident(104);
        std::copy_n(body.begin(),16,incident.begin());incident[22]=0x40;incident[24]=0x80;
        incident[32]=1;incident[33]=1;incident[35]=3;incident[39]=1;incident[43]=2;
        incident[46]=3;incident[47]=0xe8;incident[51]=20;incident[56]=incident[57]=0xff;
        packet=observation.ecu.makeDiagnostic(wire::DiagnosticKind::IncidentStatus,incident);
        observation.send(packet->frames);
        EXPECT_TRUE(observation.service.latest().incident_semantic_accepted);
        // A fresh envelope containing the same old incident revision is not
        // another semantic acceptance or a new latency endpoint.
        packet=observation.ecu.makeDiagnostic(wire::DiagnosticKind::IncidentStatus,incident);
        observation.send(packet->frames);
        EXPECT_FALSE(observation.service.latest().incident_semantic_accepted);
        auto quiet=body;quiet[23]=3;quiet[48]=0;quiet[46]=0x13;quiet[47]=0x88;
        packet=observation.ecu.makeDiagnostic(wire::DiagnosticKind::Observation,quiet);
        observation.send(packet->frames);
        incident[33]=2;incident[39]=2;incident[43]=3;incident[54]=0x13;incident[55]=0x88;
        packet=observation.ecu.makeDiagnostic(wire::DiagnosticKind::IncidentStatus,incident);
        observation.send(packet->frames);
        EXPECT_EQ(observation.service.latest().observed_condition_mask,1u);
        body[23]=1;body[16]=2;body[17]=1;body[46]=body[47]=0;
        packet=observation.ecu.makeDiagnostic(wire::DiagnosticKind::Observation,body);
        observation.send(packet->frames);
        EXPECT_TRUE(observation.service.latest().security_observation_ready);
        for(unsigned tick=4;tick<=9;++tick){
            for(unsigned step=0;step<10;++step){observation.send(observation.bms());observation.advance(90);}
            quiet[23]=static_cast<std::uint8_t>(tick);
            packet=observation.ecu.makeDiagnostic(wire::DiagnosticKind::Observation,quiet);
            EXPECT_TRUE(packet.has_value());observation.send(packet->frames);
        }
        EXPECT_EQ(observation.service.latest().observed_condition_mask,0u);
        observation.advance(3001);
        EXPECT_FALSE(observation.service.latest().security_observation_ready);
        EXPECT_FALSE(observation.service.latest().ecu_observed_fps.has_value());
        EXPECT_FALSE(observation.service.latest().ecu_observed_drops.has_value());
    }
    {
        Rig measured;measured.open();measured.send(measured.bms());
        std::vector<std::uint8_t> metrics(52,0xff);
        std::fill(metrics.begin(),metrics.begin()+24,0);metrics[6]=0x40;metrics[8]=0x80;
        metrics[18]=3;metrics[19]=0xe8;metrics[23]=20;
        metrics[48]=metrics[49]=metrics[50]=0;metrics[51]=1;
        auto packet=measured.ecu.makeDiagnostic(wire::DiagnosticKind::Metrics,metrics);
        EXPECT_TRUE(packet.has_value());measured.send(packet->frames);
        EXPECT_TRUE(measured.service.latest().ecu_metrics_fresh);
        EXPECT_EQ(measured.service.latest().ecu_metrics->sender_id,0x302u);
        EXPECT_EQ(measured.service.latest().ecu_metrics->body[24],0xffu);
        measured.advance(3001);
        EXPECT_FALSE(measured.service.latest().ecu_metrics_fresh);
    }
    Rig rig;
    EXPECT_FALSE(rig.service.enableSession(key(),limits(),at(0)));
    EXPECT_EQ(rig.service.processFrame(0x100,{150,200,0,0,0,0,65,0},at(0)),ivi::ProcessResult::kIgnored);
    rig.open();
    auto snapshot=rig.service.latest();
    EXPECT_TRUE(snapshot.session_protocol&&snapshot.fail_safe_known&&!snapshot.vehicle.valid);
    EXPECT_EQ(snapshot.measurement_sequence,0u);EXPECT_EQ(snapshot.session_generation,1u);
    EXPECT_EQ(snapshot.connection_stage,std::string("waiting-data"));
    const auto pair=rig.bms();rig.send(pair);snapshot=rig.service.latest();
    EXPECT_TRUE(snapshot.vehicle.valid&&!snapshot.vehicle.stale&&snapshot.session_bms_ready);
    EXPECT_EQ(snapshot.connection_stage,std::string("connected"));EXPECT_NEAR(snapshot.vehicle.soh_percent,90,0);
    EXPECT_EQ(snapshot.measurement_sequence,1u);
    EXPECT_EQ(snapshot.ivi_publication_metrics.authenticated_bms,1u);
    EXPECT_EQ(snapshot.t1_received_ns%1000000,123456u);
    EXPECT_TRUE(snapshot.t2_published_ns>snapshot.t1_received_ns);
    EXPECT_TRUE(snapshot.authenticated_bms.has_value()&&snapshot.authenticated_bms_context.has_value());
    EXPECT_TRUE(snapshot.authenticated_bms->payload==pair[0].data);
    EXPECT_TRUE(snapshot.authenticated_bms->authentication==pair[1].data);
    EXPECT_TRUE(snapshot.authenticated_bms->auth_received_ns<=snapshot.t2_published_ns);
    const auto original_counter=snapshot.authenticated_bms->counter;
    const auto first_ns=snapshot.t1_received_ns;
    rig.send(pair);snapshot=rig.service.latest();
    EXPECT_EQ(snapshot.measurement_sequence,1u);EXPECT_EQ(snapshot.t1_received_ns,first_ns);
    EXPECT_EQ(snapshot.authenticated_bms->counter,original_counter);
    EXPECT_TRUE(snapshot.secoc_failure_count>0);
    bool denied=false;try{rig.service.setSecOcKey(key());}catch(const std::logic_error&){denied=true;}EXPECT_TRUE(denied);

    rig.send(rig.ecu.publishData(0x101,{1,3,4,150,101,0,0,0},++rig.now));
    EXPECT_EQ(rig.service.latest().vehicle.fail_safe_state,3u);
    rig.ecu.setCurrentState({3,1,4,0,0,0,0,0},++rig.now);
    const auto good_sequence=rig.service.latest().measurement_sequence;
    rig.advance(301);rig.service.refreshTime(at(rig.now));
    snapshot=rig.service.latest();
    EXPECT_TRUE(snapshot.vehicle.stale);EXPECT_EQ(snapshot.vehicle.fail_safe_state,3u);
    EXPECT_EQ(snapshot.measurement_sequence,good_sequence);
    EXPECT_TRUE(snapshot.connection_stage=="authenticating" || snapshot.connection_stage=="synchronizing");
    rig.settle();rig.advance(10);snapshot=rig.service.latest();
    EXPECT_EQ(snapshot.session_generation,2u);EXPECT_EQ(snapshot.vehicle.fail_safe_state,3u);
    EXPECT_TRUE(snapshot.vehicle.stale&&!snapshot.session_bms_ready);
    EXPECT_TRUE(!snapshot.authenticated_bms&& !snapshot.authenticated_bms_context);
    rig.send(pair);EXPECT_EQ(rig.service.latest().measurement_sequence,good_sequence);
    rig.send(rig.bms(140));snapshot=rig.service.latest();
    EXPECT_TRUE(!snapshot.vehicle.stale&&snapshot.session_bms_ready);EXPECT_EQ(snapshot.vehicle.fail_safe_state,3u);
    EXPECT_EQ(snapshot.measurement_sequence,good_sequence+1);
    EXPECT_TRUE(rig.notifications>0);
}
}
int main(){return runTestProgram("vehicle_data_session",tests);}
