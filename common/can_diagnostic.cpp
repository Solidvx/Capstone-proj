#include "can_diagnostic.h"
#include "physical_measurement.h"

#include <openssl/crypto.h>
#include <openssl/sha.h>
#include <algorithm>
#include <stdexcept>

namespace capstone::session_v2 {
std::optional<std::vector<std::uint8_t>> restartReceiptBody(const DiagnosticResult& result){
    if((result.code!=DiagnosticResultCode::Message&&result.code!=DiagnosticResultCode::Duplicate)||!result.message)return std::nullopt;
    const auto& message=*result.message;
    if(message.sender_id!=0x302||message.kind!=DiagnosticKind::RestartPlan||
       !validDiagnosticBody(0x302,message.kind,message.body))return std::nullopt;
    std::vector<std::uint8_t> body(message.body.begin(),message.body.begin()+32);
    body.resize(40,0);body[32]=1;
    for(unsigned i=0;i<4;++i)body[36+i]=static_cast<std::uint8_t>(message.sequence>>(24-8*i));
    return body;
}
namespace {
using Bytes=std::vector<std::uint8_t>;
constexpr std::array<unsigned,10> lengths{0,56,56,40,104,80,52,52,56,80};
std::uint32_t u32(const Bytes& b,unsigned at){
    std::uint32_t value=0;for(unsigned i=0;i<4;++i)value=(value<<8)|b[at+i];return value;
}
unsigned u16(const Bytes& b,unsigned at){return (b[at]<<8)|b[at+1];}
bool zero(const Bytes& b,unsigned at,unsigned length){
    return std::all_of(b.begin()+at,b.begin()+at+length,[](auto value){return value==0;});
}
bool uuid(const Bytes& b,unsigned at){return (b[at+6]&0xf0)==0x40 && (b[at+8]&0xc0)==0x80;}
bool maybeUuid(const Bytes& b,unsigned at){return zero(b,at,16)||uuid(b,at);}
bool direction(std::uint16_t sender,unsigned kind){
    if(sender!=0x302 && sender!=0x303)return false;
    if(kind==6)return true;
    return sender==0x302 ? kind==1 || kind==2 || kind==4 || kind==7 || kind==8 || kind==9 : kind==3 || kind==5;
}
bool reference(const Bytes& b,unsigned at){
    const auto kind=b[at];
    if(kind==0)return zero(b,at+1,43);
    if(kind>2 || b[at+3]!=0 || b[at+1]>8)return false;
    if(kind==1)return b[at+2]==0 && zero(b,at+8,4) && zero(b,at+36,8) &&
                       zero(b,at+28+b[at+1],8-b[at+1]);
    if(b[at+1]!=8 || b[at+2]!=8 || zero(b,at+12,16))return false;
    const auto raw=u32(b,at+4),auth=u32(b,at+8);
    return (raw==0x100 && auth==0x102)||(raw==0x101 && auth==0x103)||(raw==0x104 && auth==0x105);
}
unsigned length(DiagnosticKind kind){
    const auto n=static_cast<unsigned>(kind);
    return n>0 && n<lengths.size() ? lengths[n] : 0;
}
void be32(Bytes& bytes,std::uint32_t value){
    for(int shift=24;shift>=0;shift-=8)bytes.push_back(static_cast<std::uint8_t>(value>>shift));
}
}
bool validDiagnosticBody(std::uint16_t sender,DiagnosticKind kind,const Bytes& b){
    const auto n=static_cast<unsigned>(kind);
    if(!direction(sender,n)||!length(kind)||b.size()!=length(kind))return false;
    if(n==9)return decodePhysicalMeasurement(b).has_value();
    if(n==1){
        if(!uuid(b,0)||!maybeUuid(b,16)||b[32]<1||b[32]>5||b[33]<1||b[33]>2||
           b[34]<1||b[34]>6||b[38]>3||b[39]||b[55]||b[52]>1||b[53]>1||b[54]>1)return false;
        if(b[35]==0xff){if(b[36]||b[37]||b[54])return false;}
        else if(!validCurrentState(Payload{b[35],b[36],b[37],0,0,0,0,0}))return false;
        if(b[33]==1 && (b[52]||b[54]))return false;
        if(b[33]==2 && b[32]==2 && (!b[52]||!b[54]))return false;
        if(b[53]&&b[34]!=2)return false;
        return !b[52] || u32(b,48)!=0xffffffffu;
    }
    if(n==2){
        if(!uuid(b,0)||!uuid(b,16)||!maybeUuid(b,32)||b[48]<1||b[48]>3||
           b[50]<1||b[50]>3||b[51]||!u32(b,52))return false;
        if(b[48]==1 && (!uuid(b,32)||b[50]!=1))return false;
        return b[49]==(b[48]==2 ? 1 : 2);
    }
    if(n==3)return uuid(b,0)&&uuid(b,16)&&b[32]==1&&zero(b,33,3);
    if(n==4){
        if(!uuid(b,0)||!uuid(b,16)||b[32]<1||b[32]>4||b[33]<1||b[33]>3||
           !u16(b,34)||!u32(b,36)||!u32(b,40)||u16(b,58)>31||
           (u16(b,56)>0x7ff && u16(b,56)!=0xffff)||!reference(b,60))return false;
        if(b[33]==1 && (!u32(b,44)||!u32(b,48)||u32(b,48)==0xffffffffu||u32(b,52)))return false;
        if(b[33]==2 && (!u32(b,44)||u32(b,48)==0xffffffffu||u32(b,52)<5000))return false;
        if(b[33]==3 && (u32(b,52)||(!u32(b,44)&&u32(b,48)!=0xffffffffu)))return false;
        return b[60]!=2 || u16(b,56)==0xffff || u16(b,56)==u32(b,64);
    }
    if(n==5){
        if(!uuid(b,0)||!uuid(b,16)||b[32]<1||b[32]>15||b[33]>1||b[35]||!reference(b,36))return false;
        const auto reason=b[32];
        const unsigned treatment=reason==4||reason==5 ? 4 : reason==6 ? 2 : reason==9 ? 3 :
            reason==12||reason==13||reason==14 ? 5 : 1;
        const bool verified=reason>=7 && reason<=13;
        return b[34]==treatment && b[33]==static_cast<unsigned>(verified) && (!verified||b[36]==2);
    }
    if(n==6){
        if(!uuid(b,0)||!u32(b,16))return false;
        const auto mask=u32(b,48);
        if(!(mask&1)||mask>127)return false;
        for(unsigned i=0;i<7;++i)if(((mask>>i)&1)==(u32(b,20+i*4)==0xffffffffu))return false;
        if((mask&2)&&u32(b,24)>u32(b,20))return false;
        return (mask&24)!=24 || u32(b,32)<=u32(b,36);
    }
    if(n==8){
        if(!uuid(b,0)||!uuid(b,16)||b[50]>2||b[51]>1||
           !validCurrentState(Payload{b[48],static_cast<std::uint8_t>(b[49]!=0),b[49],0,0,0,0,0}))return false;
        if(b[50]==0)return zero(b,32,16)&&!u32(b,52)&&b[48]==0&&b[49]==0;
        return uuid(b,32)&&u32(b,52)!=0 && (b[50]==1 ? b[48]!=0 : b[48]==0);
    }
    if(!uuid(b,0)||b[16]<1||b[16]>3||b[17]>6||!zero(b,18,2)||!u32(b,20)||
       b[48]>15||!u16(b,49)||b[51])return false;
    if(b[16]==1)return b[17]==0 && u32(b,32)>0 && u32(b,36)>0 &&
        u32(b,36)!=0xffffffffu && u32(b,40)==0 && u32(b,44)>=u32(b,32);
    return b[17]!=0 && u32(b,44)==0 && (u32(b,32)!=0 || u32(b,36)==0xffffffffu);
}
DiagnosticPacket encodeDiagnostic(const SessionKeys& keys,const Context& context,std::uint16_t sender,
                                   std::uint32_t sequence,DiagnosticKind kind,const Bytes& body){
    if(!validDiagnosticBody(sender,kind,body))throw std::invalid_argument("invalid diagnostic body/direction");
    const auto id=contextId(context);
    Bytes envelope(id.begin(),id.end());be32(envelope,sequence);
    envelope.push_back(static_cast<std::uint8_t>(kind));envelope.push_back(static_cast<std::uint8_t>(body.size()));
    envelope.insert(envelope.end(),body.begin(),body.end());
    const auto proof=diagnosticTag(keys,sender,envelope);envelope.insert(envelope.end(),proof.begin(),proof.end());
    while(envelope.size()%4)envelope.push_back(0);
    DiagnosticPacket packet{sequence,id,{}};
    for(unsigned i=0;i<envelope.size()/4;++i){
        Frame frame{sender,{0xd1,static_cast<std::uint8_t>(i),static_cast<std::uint8_t>(sequence>>8),static_cast<std::uint8_t>(sequence)}};
        std::copy_n(envelope.begin()+i*4,4,frame.data.begin()+4);packet.frames.push_back(frame);
    }
    return packet;
}
DiagnosticSender::DiagnosticSender(std::shared_ptr<const SessionKeys> keys,Context context,std::uint16_t sender)
    : keys_(std::move(keys)),context_(context),sender_id_(sender){
    if(!keys_ || (sender!=0x302 && sender!=0x303))throw std::invalid_argument("authenticated diagnostic endpoint required");
    keys_->at(sender==0x302 ? Role::DiagEcu : Role::DiagIvi);
}
DiagnosticPacket DiagnosticSender::encode(DiagnosticKind kind,const Bytes& body){
    if(!validDiagnosticBody(sender_id_,kind,body))throw std::invalid_argument("invalid diagnostic body/direction");
    const auto next=takeCounter(next_);
    if(!next)throw std::overflow_error("diagnostic sequence requires a new authenticated session");
    return encodeDiagnostic(*keys_,context_,sender_id_,*next,kind,body);
}
void validateDiagnosticLimits(const DiagnosticLimits& limits){
    if(!limits.assembly_ms||!limits.verification_window_ms||!limits.assemblies||
       limits.assemblies>8||!limits.max_verifications)
        throw std::invalid_argument("explicit bounded diagnostic receive settings required");
}
DiagnosticReceiver::DiagnosticReceiver(std::shared_ptr<const SessionKeys> keys,Context context,
    std::uint16_t peer,DiagnosticLimits limits,std::uint64_t started)
    :keys_(std::move(keys)),context_id_(contextId(context)),peer_id_(peer),limits_(limits),
     last_now_(started),window_ms_(started){
    validateDiagnosticLimits(limits);
    if(!keys_||(peer!=0x302&&peer!=0x303))
        throw std::invalid_argument("explicit bounded diagnostic receive settings required");
    keys_->at(peer==0x302 ? Role::DiagEcu : Role::DiagIvi);
}
bool DiagnosticReceiver::advance(std::uint64_t now,DiagnosticResult& result){
    if(failed_){result.code=failure_;return false;}
    if(now<last_now_){failed_=true;failure_=result.code=DiagnosticResultCode::ClockError;assemblies_.clear();return false;}
    last_now_=now;
    if(now-window_ms_>=limits_.verification_window_ms){window_ms_=now;checks_=0;}
    for(auto it=assemblies_.begin();it!=assemblies_.end();){
        if(now-it->second.first_ms>=limits_.assembly_ms){it=assemblies_.erase(it);++result.expired_assemblies;}
        else ++it;
    }
    return true;
}
DiagnosticResult DiagnosticReceiver::poll(std::uint64_t now){
    DiagnosticResult result;
    if(advance(now,result)&&result.expired_assemblies)result.code=DiagnosticResultCode::Expired;
    return result;
}
DiagnosticResult DiagnosticReceiver::receive(const Frame& frame,std::uint64_t now,std::optional<std::uint64_t> captured){
    DiagnosticResult result;
    if(!advance(now,result))return result;
    if(frame.id!=peer_id_)return result;
    result.code=DiagnosticResultCode::Invalid;
    if(frame.extended||frame.remote||frame.error||frame.dlc!=8||frame.data[0]!=0xd1||frame.data[1]>=36)return result;
    const auto arrived=captured.value_or(now);
    if(arrived>now)return result;
    if(now-arrived>=limits_.assembly_ms){result.code=DiagnosticResultCode::Expired;return result;}
    const auto transfer=static_cast<std::uint16_t>((frame.data[2]<<8)|frame.data[3]);
    auto it=assemblies_.find(transfer);
    if(it==assemblies_.end()){
        if(assemblies_.size()>=limits_.assemblies){result.code=DiagnosticResultCode::Limit;return result;}
        it=assemblies_.emplace(transfer,Assembly{{},{},std::nullopt,arrived,arrived}).first;
    }
    auto& assembly=it->second;const auto index=frame.data[1];
    auto byte=[&](unsigned offset)->std::uint8_t&{return assembly.storage[offset];};
    if(assembly.count && index>=*assembly.count){assemblies_.erase(it);return result;}
    if(assembly.seen[index]){
        for(unsigned i=0;i<4;++i)if(byte(index*4+i)!=frame.data[4+i]){assemblies_.erase(it);return result;}
    }else{
        for(unsigned i=0;i<4;++i)byte(index*4+i)=frame.data[4+i];
        assembly.seen[index]=true;assembly.first_ms=std::min(assembly.first_ms,arrived);
        assembly.last_ms=std::max(assembly.last_ms,arrived);
    }
    if(now-assembly.first_ms>=limits_.assembly_ms){assemblies_.erase(it);result.code=DiagnosticResultCode::Expired;return result;}
    if(assembly.seen[5]){
        const auto kind=byte(20),body_length=byte(21);
        if(kind==0||kind>=lengths.size()||body_length!=lengths[kind]||!direction(peer_id_,kind)){
            assemblies_.erase(it);return result;
        }
        const auto count=(38u+body_length+3)/4;
        for(unsigned i=count;i<36;++i)if(assembly.seen[i]){assemblies_.erase(it);return result;}
        assembly.count=count;
    }
    result.code=DiagnosticResultCode::Pending;
    if(!assembly.count||!std::all_of(assembly.seen.begin(),assembly.seen.begin()+*assembly.count,[](bool b){return b;}))return result;
    Bytes envelope;
    for(unsigned i=0;i<*assembly.count*4;++i)envelope.push_back(byte(i));
    const auto received=assembly.last_ms;assemblies_.erase(it);
    const auto total=38u+envelope[21];
    result.code=DiagnosticResultCode::Invalid;
    if(!zero(envelope,total,static_cast<unsigned>(envelope.size()-total)))return result;
    envelope.resize(total);
    if((u32(envelope,16)&0xffff)!=transfer)return result;
    if(!std::equal(context_id_.begin(),context_id_.end(),envelope.begin())){result.code=DiagnosticResultCode::ForeignSession;return result;}
    const auto kind=static_cast<DiagnosticKind>(envelope[20]);
    Bytes body(envelope.begin()+22,envelope.end()-16);
    if(!validDiagnosticBody(peer_id_,kind,body))return result;
    if(checks_>=limits_.max_verifications){result.code=DiagnosticResultCode::Limit;return result;}
    ++checks_;
    Tag received_tag{};std::copy_n(envelope.end()-16,16,received_tag.begin());
    const Bytes unsigned_envelope(envelope.begin(),envelope.end()-16);
    if(!tagMatches(diagnosticTag(*keys_,peer_id_,unsigned_envelope),received_tag)){
        result.code=DiagnosticResultCode::AuthFailed;return result;
    }
    const auto sequence=u32(envelope,16);
    if(highest_&&sequence<=*highest_&&*highest_-sequence>=64){result.code=DiagnosticResultCode::Replay;return result;}
    std::array<std::uint8_t,32> hash{};
    if(!SHA256(unsigned_envelope.data(),unsigned_envelope.size(),hash.data()))throw std::runtime_error("diagnostic fingerprint failed");
    const auto prior=seen_.find(sequence);
    if(prior!=seen_.end()&&prior->second!=hash){
        failed_=true;failure_=result.code=DiagnosticResultCode::Conflict;assemblies_.clear();return result;
    }
    const bool duplicate=prior!=seen_.end();
    if(!duplicate){
        if(!highest_||sequence>*highest_)highest_=sequence;
        for(auto old=seen_.begin();old!=seen_.end();){
            if(*highest_-old->first>=64)old=seen_.erase(old);else ++old;
        }
        seen_[sequence]=hash;
    }
    result.code=duplicate ? DiagnosticResultCode::Duplicate : DiagnosticResultCode::Message;
    result.message=DiagnosticMessage{kind,sequence,peer_id_,context_id_,std::move(body),received,now,duplicate};
    return result;
}
}
