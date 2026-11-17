#include "vehicle_data_service.h"
#include "rejection_record.h"

#include <openssl/crypto.h>
#include <algorithm>
#include <limits>
#include <stdexcept>

namespace ivi {
namespace {
namespace wire=capstone::session_v2;
// Existing1s NodeStatus cadence uses a3s report age, distinct from the300ms
// measurement-staleness deadline. ProtectionStatus shares that report cadence.
constexpr std::uint64_t kNodeReportFreshMs=3000;
std::uint64_t millis(VehicleDataService::Clock::time_point time){
    const auto value=std::chrono::duration_cast<std::chrono::milliseconds>(time.time_since_epoch()).count();
    if(value<0)throw std::invalid_argument("negative session clock");return static_cast<std::uint64_t>(value);
}
const char* rejection(wire::ReceiveReason reason){
    using R=wire::ReceiveReason;
    switch(reason){
    case R::Replay:return "COUNTER_REPLAY";case R::Ahead:return "COUNTER_WINDOW";
    case R::Semantic:return "INVALID_PAYLOAD";case R::OriginalExpired:return "ORIGINAL_EXPIRED";
    case R::AuthExpired:return "AUTH_EXPIRED";case R::GeneralFull:return "GENERAL_QUEUE_FULL";
    case R::ProtectedFull:return "PROTECTED_QUEUE_FULL";case R::Conflict:return "AUTHENTICATED_CONFLICT";
    case R::ClockError:return "TIME_REGRESSION";case R::BeforeState:return "STATE_NOT_CONFIRMED";
    case R::MacBudget:return "MAC_BUDGET";case R::PendingFull:return "PENDING_FULL";
    case R::Duplicate:return "DUPLICATE";case R::Metadata:return "FRAME_METADATA";
    case R::UnsupportedId:return "UNSUPPORTED_ID";
    }
    return "UNKNOWN";
}
bool countedRejection(wire::ReceiveReason reason){
    return reason!=wire::ReceiveReason::Duplicate && reason!=wire::ReceiveReason::MacBudget &&
           reason!=wire::ReceiveReason::UnsupportedId;
}
}

void VehicleDataService::configureRejectionReports(std::size_t capacity,unsigned frame_budget,std::uint64_t expiry_ms){
    std::lock_guard<std::mutex> lock(mutex_);
    if(session_ || rejection_reports_)throw std::logic_error("rejection report policy must be selected once before session");
    rejection_reports_=std::make_unique<wire::DiagnosticTxQueue>(capacity,frame_budget,expiry_ms);
    rejection_capacity_=capacity;
}
bool VehicleDataService::enableSession(SecOcKey key,wire::ExchangeLimits limits,Clock::time_point now){
    struct Erase{SecOcKey& key;~Erase(){OPENSSL_cleanse(key.data(),key.size());}} erase{key};
    std::lock_guard<std::mutex> lock(mutex_);
    if(session_||verifier_)return false;
    (void)millis(now);
    session_=std::make_unique<wire::Exchange>(wire::Endpoint::Ivi,key,limits);
    session_receipt_cooldown_=std::chrono::milliseconds(limits.retry_ms);
    verifier_instance_=wire::diagnosticUuid();
    snapshot_.session_protocol=true;snapshot_.connection_stage="waiting";
    snapshot_.last_message="Waiting for authenticated ECU session";
    return true;
}
SessionServiceResult VehicleDataService::processSessionFrame(const wire::Frame& frame,
    Clock::time_point captured,Clock::time_point now){return updateSession(&frame,captured,now);}
SessionServiceResult VehicleDataService::pollSession(Clock::time_point now){return updateSession(nullptr,now,now);}

SessionServiceResult VehicleDataService::updateSession(const wire::Frame* frame,Clock::time_point captured,Clock::time_point now){
    SessionServiceResult result;
    VehicleSnapshot notification;std::vector<Observer> observers;bool changed=false;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if(!session_)return result;
        if(now==Clock::time_point::min())now=Clock::now(); // clock after owner serialization
        if(frame){
            snapshot_.last_can_id=frame->id;
            result.outgoing=session_->receive(*frame,millis(now),millis(captured),monotonicNanoseconds(captured));
            result.result=ProcessResult::kPendingAuthentication;
        }else result.outgoing=session_->poll(millis(now));
        changed=applySessionLocked(now,result);
        const auto phase=session_->phase();
        if(phase==wire::Phase::Open && previous_session_phase_!=wire::Phase::Open)session_opened_at_=now;
        // A silent/long-disconnected peer needs a new authenticated session,
        // not a local counter reset or ECU process restart.
        const auto since=snapshot_.session_bms_ready ? last_good_bms_at_ : session_opened_at_;
        const auto& node=snapshot_.ecu_node_status;
        const bool input_paused=node && millis(now)>=node->received_ms &&
            millis(now)-node->received_ms<(snapshot_.physical_measurement || node->body[34]!=2 || node->body[32]==3 || node->body[32]==5 ? kNodeReportFreshMs : 300u);
        if(phase==wire::Phase::Open && !input_paused && since && now>=*since && now-*since>=kStaleTimeout){
            auto frames=session_->start(millis(now));
            const bool began=!frames.empty();
            result.outgoing.insert(result.outgoing.end(),frames.begin(),frames.end());
            if(began){snapshot_.connection_stage="authenticating";snapshot_.vehicle.stale=true;changed=true;}
        }
        previous_session_phase_=session_->phase();
        if(changed){++snapshot_.snapshot_revision;notification=snapshot_;for(const auto& entry:observers_)observers.push_back(entry.second);}
    }
    if(changed)notify(notification,observers);
    return result;
}

bool VehicleDataService::applySessionLocked(Clock::time_point now,SessionServiceResult& result){
    bool changed=false;
    const auto generation=session_->generation();
    if(snapshot_.session_generation!=generation){
        inherited_ids_mask_=snapshot_.observed_condition_mask;
        incident_links_=wire::IncidentRejectionLink{};snapshot_.incident_rejection_ids={};
        if(rejection_reports_)rejection_reports_->clear();
        snapshot_.session_generation=generation;snapshot_.session_bms_ready=false;
        if(snapshot_.physical_measurement)snapshot_.vehicle.valid=false;
        snapshot_.physical_measurement.reset();snapshot_.physical_received_ms=0;snapshot_.physical_valid.fill(false);
        snapshot_.authenticated_bms.reset();snapshot_.authenticated_bms_context.reset();
        snapshot_.vehicle.stale=true;snapshot_.vehicle.sensor_state=0;
        snapshot_.authenticated_diagnostic.reset();snapshot_.ecu_node_status.reset();snapshot_.ecu_metrics.reset();snapshot_.ecu_metrics_fresh=false;session_opened_at_.reset();changed=true;
        snapshot_.ecu_protection_status.reset();snapshot_.protection_confirmed=false;snapshot_.session_state_ready=false;
        protection_sequence_.reset();protection_inconsistent_=false;
        snapshot_.security_observation_ready=false;snapshot_.ecu_observed_fps.reset();snapshot_.ecu_observed_drops.reset();
        ids_source_.reset();ids_tick_=0;ids_observation_at_.reset();
        publication_meter_.reset();snapshot_.ivi_publication_metrics=publication_meter_.value();
        ids_order_=wire::IdsSubmissionOrder{};ids_quiet_ms_.fill(0);ids_pending_end_.fill(false);
        last_plan_receipt_at_.reset();
    }
    const auto& outcome=session_->lastReceiveOutcome();
    if(outcome.failed){snapshot_.session_bms_ready=false;snapshot_.vehicle.stale=true;changed=true;}
    for(const auto& decision:outcome.decisions){
        if(!countedRejection(decision.reason))continue;
        const auto reason=std::string("reason=")+rejection(decision.reason)+" session="+std::to_string(outcome.generation)+
            " can_id="+std::to_string(decision.original_id);
        recordSecOcFailureLocked(reason);changed=true;result.result=ProcessResult::kRejected;
        if(const auto body=wire::rejectionRecord(decision,session_->lastReceiveContext(),verifier_instance_,wire::diagnosticUuid())){
            snapshot_.local_rejection_record=body;++snapshot_.rejection_record_revision;
            if(session_->lastReceiveContext())incident_links_.rejected(*body,wire::contextId(*session_->lastReceiveContext()),millis(now));
            if(rejection_reports_ && session_->dataOpen()){
                if(rejection_reports_->pending()>=rejection_capacity_)++rejection_queue_full_;
                else try{
                    if(auto packet=session_->makeDiagnostic(wire::DiagnosticKind::Rejection,*body))
                        rejection_reports_->offer(std::move(*packet),millis(now));
                }catch(const std::runtime_error&){++rejection_queue_full_;}
            }
        }
    }
    for(const auto& message:outcome.applied){
        if(message.generation!=generation)continue;
        if(message.id==0x100){
            if(snapshot_.physical_measurement)continue; // never mix pack BMS with this physical instance
            const auto parsed=parseBmsStatus(message.payload);if(!parsed)throw std::logic_error("session receiver published invalid BMS");
            snapshot_.authenticated_bms=message;
            snapshot_.authenticated_bms_context=session_->lastReceiveContext() ?
                std::optional<wire::Nonce>{wire::contextId(*session_->lastReceiveContext())} : std::nullopt;
            snapshot_.vehicle.soc_percent=parsed->soc_percent;snapshot_.vehicle.soh_percent=parsed->soh_percent;
            snapshot_.vehicle.voltage_v=parsed->voltage_v;snapshot_.vehicle.current_a=parsed->current_a;
            snapshot_.vehicle.temperature_c=parsed->temperature_c;snapshot_.vehicle.valid=true;
            snapshot_.session_bms_ready=true;
            last_good_bms_at_=Clock::time_point(std::chrono::nanoseconds(std::max(message.raw_received_ns,message.auth_received_ns)));
            const auto age=now<=*last_good_bms_at_ ? 0 : std::chrono::duration_cast<std::chrono::milliseconds>(now-*last_good_bms_at_).count();
            snapshot_.vehicle.stale=age>=kStaleTimeout.count() ||
                (snapshot_.vehicle.sensor_state!=0 && snapshot_.vehicle.sensor_state!=2);snapshot_.last_good_age_ms=age;
            snapshot_.vehicle.received_monotonic_ns=message.raw_received_ns;
            snapshot_.t1_received_ns=message.raw_received_ns;
            // Timestamp after verification/order/application, not at the entry
            // to processSessionFrame/pollSession before their work was done.
            snapshot_.t2_published_ns=monotonicNanoseconds(Clock::now());
            publication_meter_.observe(snapshot_.t2_published_ns);
            snapshot_.ivi_publication_metrics=publication_meter_.value();
            ++snapshot_.measurement_sequence;snapshot_.last_message="Authenticated session BMS data published";
        }else if(message.id==0x101){
            const auto event=parseFailSafeEvent(message.payload);if(!event)throw std::logic_error("session receiver published invalid transition");
            snapshot_.vehicle.fail_safe_state=event->new_state;snapshot_.vehicle.fail_safe_reason=event->reason;
            snapshot_.fail_safe_known=true;snapshot_.last_message="Authenticated Fail-safe event published";
        }else if(message.id==0x104){
            snapshot_.vehicle.fail_safe_state=message.payload[0];snapshot_.vehicle.fail_safe_reason=message.payload[2];
            snapshot_.fail_safe_known=true;snapshot_.last_message="Authenticated current Fail-safe state synchronized";
            snapshot_.session_state_ready=true;
        }else continue;
        snapshot_.last_secoc_verified=true;snapshot_.consecutive_secoc_failure_count=0;
        appendLogLocked(snapshot_.last_message);changed=true;result.result=ProcessResult::kPublished;
    }
    const auto& diagnostic=session_->lastDiagnosticResult();
    if(diagnostic.code==wire::DiagnosticResultCode::Message && diagnostic.message){
        snapshot_.authenticated_diagnostic=diagnostic.message;++snapshot_.diagnostic_revision;changed=true;
        snapshot_.incident_semantic_accepted=false;
        snapshot_.incident_semantic_verified_ns=0;
        if(diagnostic.message->kind==wire::DiagnosticKind::Metrics){
            if(!snapshot_.ecu_metrics || diagnostic.message->sequence>snapshot_.ecu_metrics->sequence){
                snapshot_.ecu_metrics=diagnostic.message;
                snapshot_.ecu_metrics_fresh=true;
            }
        }
        if(diagnostic.message->kind==wire::DiagnosticKind::Observation){
            const auto& body=diagnostic.message->body;
            wire::Nonce source{};std::copy_n(body.begin(),16,source.begin());
            const std::uint32_t tick=(std::uint32_t(body[20])<<24)|(std::uint32_t(body[21])<<16)|
                (std::uint32_t(body[22])<<8)|body[23];
            if(ids_order_.accept({wire::DiagnosticKind::Observation,body},millis(now))){
                const bool continuous=ids_observation_at_ && now>=*ids_observation_at_ &&
                    now-*ids_observation_at_<std::chrono::seconds(3) && tick==ids_tick_+1;
                const auto elapsed=continuous ? static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::milliseconds>(now-*ids_observation_at_).count()) : 0;
                const std::uint32_t window=(std::uint32_t(body[32])<<24)|(std::uint32_t(body[33])<<16)|(std::uint32_t(body[34])<<8)|body[35];
                for(unsigned type=0;type<4;++type){
                    if(!continuous || body[16]!=1 || (body[48]&(1u<<type))){ids_quiet_ms_[type]=0;ids_pending_end_[type]=false;}
                    else ids_quiet_ms_[type]=std::min<std::uint64_t>(5000,ids_quiet_ms_[type]+std::min<std::uint64_t>(elapsed,window));
                }
                for(unsigned type=0;type<4;++type){
                    const unsigned bit=1u<<type;
                    if((inherited_ids_mask_&bit) && ids_quiet_ms_[type]>=5000){
                        snapshot_.observed_condition_mask&=static_cast<std::uint8_t>(~bit);
                        snapshot_.reconciled_unknown_mask|=bit;
                        snapshot_.security_incident_ids[type].reset();
                        inherited_ids_mask_&=static_cast<std::uint8_t>(~bit);
                        appendLogLocked("Previous observer incident remains unknown; current healthy observation confirmed type="+std::to_string(type+1));
                    }
                    if(ids_pending_end_[type] && ids_quiet_ms_[type]>=5000){
                        snapshot_.observed_condition_mask&=static_cast<std::uint8_t>(~(1u<<type));
                        ids_pending_end_[type]=false;
                        appendLogLocked("Authenticated IDS incident ended after local observation type="+std::to_string(type+1));
                    }
                }
                ids_source_=source;ids_tick_=tick;ids_observation_at_=now;
                snapshot_.observed_condition_mask|=body[48]; // heartbeat quiet alone does not close an incident
                snapshot_.security_observation_ready=body[16]==1;
                const std::uint32_t drops=(std::uint32_t(body[40])<<24)|(std::uint32_t(body[41])<<16)|(std::uint32_t(body[42])<<8)|body[43];
                if(drops==0xffffffffu)snapshot_.ecu_observed_drops.reset();
                else snapshot_.ecu_observed_drops=drops;
                const std::uint32_t frames=(std::uint32_t(body[36])<<24)|(std::uint32_t(body[37])<<16)|(std::uint32_t(body[38])<<8)|body[39];
                if(body[16]==1 && window && frames!=0xffffffffu)
                    snapshot_.ecu_observed_fps=double(frames)*1000/window;
                else snapshot_.ecu_observed_fps.reset();
            }
        }
        if(diagnostic.message->kind==wire::DiagnosticKind::IncidentStatus){
            const auto& body=diagnostic.message->body;
            const auto type=body[32]-1;
            // Validate terminal identity now, but defer visible clearing until
            // local continuous observation also supports the source assertion.
            if(ids_order_.accept({wire::DiagnosticKind::IncidentStatus,body},millis(now))){
                snapshot_.incident_semantic_accepted=true;
                snapshot_.incident_semantic_verified_ns=monotonicNanoseconds(Clock::now());
                incident_links_.incident(body,diagnostic.message->session_id,millis(now));
                if(body[33]==2){
                    ids_pending_end_[type]=ids_quiet_ms_[type]<5000;
                    if(!ids_pending_end_[type]){
                        snapshot_.observed_condition_mask&=static_cast<std::uint8_t>(~(1u<<type));
                        appendLogLocked("Authenticated IDS incident ended type="+std::to_string(body[32]));
                    }
                }else{
                    if(body[33]==1){
                        inherited_ids_mask_&=static_cast<std::uint8_t>(~(1u<<type));
                        snapshot_.reconciled_unknown_mask&=static_cast<std::uint8_t>(~(1u<<type));
                    }
                    wire::Nonce identity{};std::copy_n(body.begin()+16,16,identity.begin());
                    snapshot_.security_incident_ids[type]=identity;
                    ids_pending_end_[type]=false;
                    snapshot_.observed_condition_mask|=1u<<type;
                    if(body[33]==3)snapshot_.security_observation_ready=false;
                }
            }
        }
        if(diagnostic.message->kind==wire::DiagnosticKind::RestartPlan)
            snapshot_.ecu_restart_plan=diagnostic.message;
        if(diagnostic.message->kind==wire::DiagnosticKind::NodeStatus &&
           (!snapshot_.ecu_node_status || diagnostic.message->sequence>snapshot_.ecu_node_status->sequence)){
            snapshot_.ecu_node_status=diagnostic.message;
            const auto& body=diagnostic.message->body;
            snapshot_.vehicle.sensor_state=body[34];
            if(snapshot_.physical_measurement && !std::equal(body.begin(),body.begin()+16,snapshot_.physical_measurement->instance.begin())){
                snapshot_.physical_measurement.reset();snapshot_.physical_valid.fill(false);
                snapshot_.vehicle.valid=false;snapshot_.session_bms_ready=false;
            }
            if(body[34]!=2 || body[32]==3 || body[32]==5)snapshot_.vehicle.stale=true;
        }
        if(diagnostic.message->kind==wire::DiagnosticKind::PhysicalMeasurement && snapshot_.ecu_node_status){
            const auto& node=*snapshot_.ecu_node_status;const auto& message=*diagnostic.message;
            auto measurement=wire::decodePhysicalMeasurement(message.body);
            const bool node_current=millis(now)>=node.received_ms&&millis(now)-node.received_ms<kNodeReportFreshMs&&
                node.session_id==message.session_id&&node.body[35]==0xff;
            bool accept=measurement&&node_current&&std::equal(node.body.begin(),node.body.begin()+16,measurement->instance.begin());
            if(accept&&snapshot_.physical_measurement){
                const auto& old=*snapshot_.physical_measurement;const auto& next=*measurement;
                accept=next.instance==old.instance&&next.configuration==old.configuration&&next.sequence>=old.sequence&&
                    (!old.observation_gap||next.observation_gap)&&next.nominal_capacity_mah==old.nominal_capacity_mah&&
                    next.max_interval_ms==old.max_interval_ms&&next.soc_basis==old.soc_basis&&next.soh_basis==old.soh_basis;
                if(accept&&next.sequence==old.sequence){
                    auto unchanged=[](const auto& a,const auto& b){return !a||(b&&a==b);};
                    accept=unchanged(next.voltage_v,old.voltage_v)&&unchanged(next.current_a,old.current_a)&&
                        unchanged(next.temperature_c,old.temperature_c)&&unchanged(next.soc_percent,old.soc_percent)&&
                        next.soh_percent==old.soh_percent&&next.ina_age_ms>=old.ina_age_ms&&next.temperature_age_ms>=old.temperature_age_ms;
                }
            }
            if(accept){
                snapshot_.physical_measurement=std::move(measurement);snapshot_.physical_received_ms=message.received_ms;
                snapshot_.fail_safe_known=false;snapshot_.session_bms_ready=false;
                snapshot_.last_secoc_verified=true;snapshot_.consecutive_secoc_failure_count=0;
                snapshot_.last_message="Authenticated physical sensor report received";
                result.result=ProcessResult::kPublished;
            }
        }
        if(diagnostic.message->kind==wire::DiagnosticKind::ProtectionStatus &&
           (!protection_sequence_ || diagnostic.message->sequence>*protection_sequence_)){
            protection_sequence_=diagnostic.message->sequence;
            const auto& body=diagnostic.message->body;
            bool consistent=true;
            if(snapshot_.ecu_protection_status){
                const auto& old=snapshot_.ecu_protection_status->body;
                auto revision=[](const auto& b){std::uint32_t n=0;for(unsigned i=52;i<56;++i)n=(n<<8)|b[i];return n;};
                const bool same_incident=std::equal(body.begin()+32,body.begin()+48,old.begin()+32);
                consistent=std::equal(body.begin(),body.begin()+32,old.begin()) &&
                    (!same_incident || (revision(body)>=revision(old) &&
                        (revision(body)!=revision(old) || body==old)));
            }
            protection_inconsistent_=!consistent;
            if(consistent)snapshot_.ecu_protection_status=diagnostic.message;
        }
    }
    // Bounded receipt replies; a replay cannot trigger an unlimited TX stream.
    // Receipt is transport acknowledgement, independent from popup dismissal.
    if(!last_plan_receipt_at_ || (now>=*last_plan_receipt_at_ && now-*last_plan_receipt_at_>=session_receipt_cooldown_)){
        if(const auto body=wire::restartReceiptBody(diagnostic)){
            last_plan_receipt_at_=now;
            try{
                if(const auto packet=session_->makeDiagnostic(wire::DiagnosticKind::RestartReceipt,*body))
                    result.outgoing.insert(result.outgoing.end(),packet->frames.begin(),packet->frames.end());
            }catch(const std::runtime_error&){appendLogLocked("Diagnostic receipt generation failed; preserving BMS state");changed=true;}
        }
    }
    if(ids_observation_at_ && (now<*ids_observation_at_ || now-*ids_observation_at_>=std::chrono::seconds(3)) &&
       snapshot_.security_observation_ready){snapshot_.security_observation_ready=false;snapshot_.ecu_observed_fps.reset();changed=true;}
    if(ids_observation_at_ && (now<*ids_observation_at_ || now-*ids_observation_at_>=std::chrono::seconds(3)) && snapshot_.ecu_observed_drops){
        snapshot_.ecu_observed_drops.reset();changed=true;
    }
    if(snapshot_.ecu_metrics && snapshot_.ecu_metrics_fresh &&
       (millis(now)<snapshot_.ecu_metrics->received_ms || millis(now)-snapshot_.ecu_metrics->received_ms>=3000)){
        snapshot_.ecu_metrics_fresh=false;changed=true;
    }
    if(snapshot_.physical_measurement){
        const auto& m=*snapshot_.physical_measurement;const auto ms=millis(now);
        const auto& node=snapshot_.ecu_node_status;
        const bool current=session_->dataOpen()&&node&&ms>=node->received_ms&&ms-node->received_ms<kNodeReportFreshMs&&
            node->body[32]==2&&node->body[35]==0xff&&std::equal(node->body.begin(),node->body.begin()+16,m.instance.begin())&&
            ms>=snapshot_.physical_received_ms;
        const auto elapsed=ms>=snapshot_.physical_received_ms?ms-snapshot_.physical_received_ms:std::uint64_t(-1);
        const bool report_fresh=current&&elapsed<m.max_interval_ms;
        auto fresh=[&](std::uint32_t age){return report_fresh&&age!=0xffffffffu&&elapsed<m.max_interval_ms&&
            age<m.max_interval_ms-elapsed;};
        std::array<bool,5> valid{m.voltage_v.has_value()&&fresh(m.ina_age_ms),m.current_a.has_value()&&fresh(m.ina_age_ms),
            m.temperature_c.has_value()&&fresh(m.temperature_age_ms),m.soc_percent.has_value()&&fresh(m.ina_age_ms),
            m.soh_percent.has_value()&&report_fresh};
        const bool available=valid[0]||valid[1]||valid[2];
        if(snapshot_.physical_valid!=valid||snapshot_.vehicle.valid!=available){changed=true;snapshot_.physical_valid=valid;}
        snapshot_.vehicle.valid=available;snapshot_.vehicle.stale=!available;
        snapshot_.fail_safe_known=false;
        if(valid[0])snapshot_.vehicle.voltage_v=*m.voltage_v;
        if(valid[1])snapshot_.vehicle.current_a=*m.current_a;
        if(valid[2])snapshot_.vehicle.temperature_c=*m.temperature_c;
        if(valid[3])snapshot_.vehicle.soc_percent=*m.soc_percent;
        if(valid[4])snapshot_.vehicle.soh_percent=*m.soh_percent;
    }
    if(rejection_reports_ && session_->dataOpen() && session_->activeContext()){
        rejection_reports_->pump(wire::contextId(*session_->activeContext()),millis(now),[&](const wire::Frame& frame){
            result.outgoing.push_back(frame);return true; // local adapter handoff, not remote delivery proof
        });
        const auto dropped=rejection_queue_full_+rejection_reports_->dropped();
        if(dropped!=snapshot_.rejection_report_drops){snapshot_.rejection_report_drops=dropped;changed=true;}
    }
    if(snapshot_.unreconciled_incident_mask!=inherited_ids_mask_){snapshot_.unreconciled_incident_mask=inherited_ids_mask_;changed=true;}
    if(!snapshot_.security_observation_ready)incident_links_.gap();
    const auto linked=incident_links_.matches(millis(now));
    if(linked!=snapshot_.incident_rejection_ids){snapshot_.incident_rejection_ids=linked;changed=true;}
    bool protection_confirmed=false;
    if(session_->dataOpen() && session_->activeContext() && snapshot_.session_state_ready &&
       snapshot_.fail_safe_known && !protection_inconsistent_ &&
       snapshot_.ecu_protection_status && snapshot_.ecu_node_status){
        const auto& protection=*snapshot_.ecu_protection_status;
        const auto& node=*snapshot_.ecu_node_status;
        const auto& b=protection.body;const auto& n=node.body;
        const auto current=wire::contextId(*session_->activeContext());
        const auto ms=millis(now);
        const bool fresh=ms>=node.received_ms && ms>=protection.received_ms &&
            ms-node.received_ms<kNodeReportFreshMs && ms-protection.received_ms<kNodeReportFreshMs;
        protection_confirmed=fresh && protection.session_id==current && node.session_id==current &&
            std::equal(b.begin(),b.begin()+16,n.begin()) && n[35]==b[48] && n[36]==(b[49]!=0) && n[37]==b[49] &&
            snapshot_.vehicle.fail_safe_state==b[48] && snapshot_.vehicle.fail_safe_reason==b[49] &&
            (!(b[51]&1) || (n[33]==2 && n[52] && n[54]));
    }
    if(protection_confirmed!=snapshot_.protection_confirmed){snapshot_.protection_confirmed=protection_confirmed;changed=true;}
    std::string stage;
    switch(session_->phase()){
    case wire::Phase::Dormant:case wire::Phase::WaitChallenge:stage="waiting";break;
    case wire::Phase::WaitOffer:case wire::Phase::WaitConfirm:case wire::Phase::WaitAck:case wire::Phase::WaitReady:stage="authenticating";break;
    case wire::Phase::WaitState:case wire::Phase::WaitReceipt:stage="synchronizing";break;
    case wire::Phase::Failed:stage="fault";break;
    case wire::Phase::Open:stage=(snapshot_.session_bms_ready || snapshot_.physical_measurement) && snapshot_.vehicle.valid && !snapshot_.vehicle.stale ? "connected" : "waiting-data";break;
    }
    // A received plan announces intent; absence alone never proves a restart.
    // Only a new authenticated instance with restored state and fresh input/data
    // may report program recovery. Battery protection remains independent.
    bool program_ready=false;
    if(snapshot_.ecu_node_status){
        const auto& node=*snapshot_.ecu_node_status;
        const auto& body=node.body;
        const bool fresh=millis(now)>=node.received_ms && millis(now)-node.received_ms<kNodeReportFreshMs;
        program_ready=fresh && body[32]==2 && body[53] && snapshot_.session_bms_ready &&
            !snapshot_.vehicle.stale && snapshot_.fail_safe_known;
        if(program_ready && body[33]==2 && body[52] && body[54])stage="program-restored";
        if(fresh && body[32]==3)stage="task-restoring";
        if(fresh && body[32]==5)stage="operator-required";
    }
    if(snapshot_.ecu_restart_plan){
        const auto& plan=*snapshot_.ecu_restart_plan;
        const bool new_instance=snapshot_.ecu_node_status &&
            !std::equal(plan.body.begin(),plan.body.begin()+16,snapshot_.ecu_node_status->body.begin());
        if(new_instance && program_ready)snapshot_.ecu_restart_plan.reset();
        else {
            std::uint32_t wait=0;for(unsigned i=52;i<56;++i)wait=(wait<<8)|plan.body[i];
            const auto age=millis(now)>=plan.received_ms ? millis(now)-plan.received_ms : std::uint64_t(-1);
            if(age<static_cast<std::uint64_t>(wait)+3000)
                stage=new_instance ? "restoring" : "restart-announced";
            else snapshot_.ecu_restart_plan.reset();
        }
    }
    if(stage!=snapshot_.connection_stage){snapshot_.connection_stage=stage;changed=true;}
    return changed;
}
}
