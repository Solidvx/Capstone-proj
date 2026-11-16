#pragma once
#include "can_diagnostic.h"
#include <algorithm>
#include <array>
#include <deque>

namespace capstone::session_v2 {
// Match a single attested candidate, not an attacker identity/whole attack.
// Repeated observations/decisions are ambiguous. A context/coverage gap resets
// claims; only current local decisions and current healthy incidents may link.
class IncidentRejectionLink {
public:
    using Matches=std::array<std::optional<Nonce>,4>;
    void incident(const std::vector<std::uint8_t>& body,const Nonce& session,std::uint64_t now){
        if(!validDiagnosticBody(0x302,DiagnosticKind::IncidentStatus,body))return;
        const auto type=body[32]-1;
        claims_[type].reset();
        // Present implementation attests replay candidates. Other types stay
        // pending until they have an equally strong verifier-specific witness.
        if(body[32]!=2||body[33]!=1||body[60]!=2||!(body[59]&4)||
           !std::equal(session.begin(),session.end(),body.begin()+72))return;
        Claim claim{};std::copy_n(body.begin()+16,16,claim.incident.begin());
        std::copy_n(body.begin()+60,44,claim.reference.begin());claim.at=now;
        claims_[type]=claim;
    }
    void rejected(const std::vector<std::uint8_t>& body,const Nonce& session,std::uint64_t now){
        if(!validDiagnosticBody(0x303,DiagnosticKind::Rejection,body)||body[32]!=7||body[33]!=1||body[36]!=2||
           !std::equal(session.begin(),session.end(),body.begin()+48))return;
        prune(now);Nonce identity{};std::copy_n(body.begin()+16,16,identity.begin());
        bool duplicate=false,conflict=false;
        for(const auto& record:records_)if(record.identity==identity){
            duplicate=true;conflict=!std::equal(record.reference.begin(),record.reference.end(),body.begin()+36);break;
        }
        // End iterator/reference lifetimes before clearing their container.
        if(duplicate){
            if(conflict){gap();blocked_until_=now+3000;}
            return; // retransmission of same result is not a second observation
        }
        if(records_.size()>=64){records_.clear();claims_={};blocked_until_=now+3000;return;}
        Record record{};record.identity=identity;record.at=now;
        std::copy_n(body.begin()+36,44,record.reference.begin());
        for(auto& previous:records_)if(previous.reference==record.reference){previous.ambiguous=true;record.ambiguous=true;}
        records_.push_back(record);
    }
    Matches matches(std::uint64_t now){
        prune(now);Matches result{};if(now<blocked_until_)return result;
        for(unsigned type=0;type<4;++type){
            if(!claims_[type])continue;
            unsigned count=0;std::optional<Nonce> match;
            for(const auto& record:records_)if(record.reference==claims_[type]->reference){
                ++count;if(!record.ambiguous)match=record.identity;
            }
            if(count==1&&match)result[type]=match;
        }
        return result;
    }
    void gap(){claims_={};records_.clear();}
private:
    using Reference=std::array<std::uint8_t,44>;
    struct Claim{Nonce incident{};Reference reference{};std::uint64_t at=0;};
    struct Record{Nonce identity{};Reference reference{};std::uint64_t at=0;bool ambiguous=false;};
    void prune(std::uint64_t now){
        if(last_now_&&now<*last_now_){gap();blocked_until_=now+3000;}
        last_now_=now;
        while(!records_.empty()&&(now<records_.front().at||now-records_.front().at>=3000))records_.pop_front();
        for(auto& claim:claims_)if(claim&&(now<claim->at||now-claim->at>=3000))claim.reset();
    }
    std::array<std::optional<Claim>,4> claims_{};
    std::deque<Record> records_;
    std::optional<std::uint64_t> last_now_;
    std::uint64_t blocked_until_=0;
};
}
