#include "can_session_crypto.h"
#include "can_session_frames.h"

#include <algorithm>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>

using namespace capstone::session_v2;
namespace {
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
template<class Function> void rejects(Function function) {
    bool rejected = false;
    try { function(); } catch (const std::exception&) { rejected = true; }
    require(rejected, "invalid candidate input accepted");
}
template<class Bytes> std::string hex(const Bytes& bytes) {
    std::ostringstream out;
    out << std::hex << std::setfill('0');
    for (auto byte : bytes) out << std::setw(2) << static_cast<unsigned>(byte);
    return out.str();
}
template<class Bytes> std::vector<std::uint8_t> body(const Bytes& bytes) {
    return {bytes.begin(), bytes.end()};
}
Context context() {
    Context ctx{0x1234, {}, {}};
    ctx.nonce_b.fill(0x42); ctx.nonce_a.fill(0x41);
    return ctx;
}
Key dummyKey() {
    Key key{};
    for (unsigned i = 0; i < key.size(); ++i) key[i] = static_cast<std::uint8_t>(i);
    return key;
}
std::map<std::string, std::string> vectors() {
    const auto ctx = context();
    const auto keys = deriveKeys(dummyKey(), ctx);
    std::map<std::string, std::string> out;
    out["transcript"] = hex(transcript(ctx));
    const std::array<std::string, 6> names{"offer", "confirm", "ack", "data", "ready", "state-receipt"};
    for (unsigned i = 0; i < names.size(); ++i) out["key." + names[i]] = hex(keys.at(static_cast<Role>(i)));
    const auto offer = controlTag(keys, ctx, Role::Offer);
    const auto confirm = controlTag(keys, ctx, Role::Confirm);
    const auto ack = controlTag(keys, ctx, Role::Ack);
    const auto ready = controlTag(keys, ctx, Role::Ready);
    out["tag.offer"] = hex(offer); out["tag.confirm"] = hex(confirm);
    out["tag.ack"] = hex(ack); out["tag.ready"] = hex(ready);
    const Payload payload{0x96, 0xc8, 0x10, 0x68, 0xff, 0xec, 0x41, 0};
    for (const std::uint16_t id : {0x100, 0x101, 0x104})
        for (const std::uint32_t counter : {0u, 99u, 0xffffffffu})
            out["mac." + std::to_string(id) + "." + std::to_string(counter)] = hex(dataMac(keys.at(Role::Data), id, counter, payload));
    const Payload state{2, 1, 2, 0, 0, 0, 0, 0};
    out["state.raw"] = "260:" + hex(state);
    out["state.auth"] = "261:" + hex(dataMac(keys.at(Role::Data), 0x104, 7, state)) + "00000007";
    const auto receipt_tag = stateReceiptTag(keys, ctx, 7, state);
    out["tag.receipt"] = hex(receipt_tag);
    auto offer_body = body(ctx.nonce_a);
    offer_body.insert(offer_body.end(), offer.begin(), offer.end());
    auto receipt_body = std::vector<std::uint8_t>{0, 0, 0, 7};
    receipt_body.insert(receipt_body.end(), receipt_tag.begin(), receipt_tag.end());
    const std::array<std::vector<std::uint8_t>, 7> bodies{
        std::vector<std::uint8_t>(4), body(ctx.nonce_b), offer_body,
        body(confirm), body(ack), body(ready), receipt_body};
    for (unsigned i = 0; i < bodies.size(); ++i) {
        const auto frames = fragment(static_cast<Kind>(i), i == 0 ? 0 : ctx.transfer_id, bodies[i]);
        for (unsigned j = 0; j < frames.size(); ++j)
            out["frame." + std::to_string(i) + "." + std::to_string(j)] =
                std::to_string(frames[j].id) + ":" + hex(frames[j].data);
    }
    return out;
}
void cryptoNegatives() {
    std::uint64_t sequence=0xfffffffeULL;
    require(takeCounter(sequence)==0xfffffffeU && takeCounter(sequence)==0xffffffffU,"counter exhaustion boundary lost ordinal");
    require(sequence==0x100000000ULL && !takeCounter(sequence) && sequence==0x100000000ULL,"counter wrapped after exhaustion");
    sequence=std::numeric_limits<std::uint64_t>::max();
    require(!takeCounter(sequence) && sequence==std::numeric_limits<std::uint64_t>::max(),"invalid large sequence wrapped");
    const auto ctx = context();
    auto keys = deriveKeys(dummyKey(), ctx);
    for (auto role : {Role::Offer, Role::Confirm, Role::Ack, Role::Ready}) {
        const auto expected = controlTag(keys, ctx, role);
        require(tagMatches(expected, expected), "valid tag rejected");
        for (unsigned bit = 0; bit < 128; ++bit) {
            auto mutated = expected; mutated[bit / 8] ^= 1u << (bit % 8);
            require(!tagMatches(expected, mutated), "one-bit control mutation accepted");
        }
        auto changed = ctx; changed.nonce_a[0] ^= 1;
        require(!tagMatches(expected, controlTag(keys, changed, role)), "transcript mutation accepted");
    }
    require(!tagMatches(controlTag(keys, ctx, Role::Ack), controlTag(keys, ctx, Role::Ready)), "role reflection accepted");
    auto old_ctx = ctx; old_ctx.nonce_b[0] ^= 1;
    auto old_keys = deriveKeys(dummyKey(), old_ctx);
    require(!tagMatches(controlTag(keys, ctx, Role::Ack), controlTag(old_keys, old_ctx, Role::Ack)), "old session accepted");
    Payload state{2,1,2,0,0,0,0,0};
    auto receipt = stateReceiptTag(keys, ctx, 7, state);
    require(!tagMatches(receipt, stateReceiptTag(keys, ctx, 8, state)), "wrong receipt counter accepted");
    state[0] = 3;
    require(!tagMatches(receipt, stateReceiptTag(keys, ctx, 7, state)), "wrong receipt body accepted");
    rejects([&]{controlTag(keys, ctx, Role::Data);});
    rejects([&]{controlTag(keys, ctx, Role::StateReceipt);});
    rejects([&]{keys.at(static_cast<Role>(8));});
    rejects([&]{controlTag(keys,ctx,Role::DiagEcu);});
    rejects([&]{controlTag(keys,ctx,Role::DiagIvi);});
    rejects([&]{dataMac(keys.at(Role::Data), 0x800, 0, {});});
    auto moved = std::move(keys);
    rejects([&]{keys.at(Role::Ack);});
    require(tagMatches(controlTag(moved, ctx, Role::Ack), controlTag(moved, ctx, Role::Ack)), "moved keys invalid");
    freshNonce(); // failure must propagate; the generated secret is never printed
}
void assemblyNegatives() {
    std::vector<std::uint8_t> source(32);
    for (unsigned i=0; i<source.size(); ++i) source[i]=static_cast<std::uint8_t>(i);
    auto frames=fragment(Kind::Offer, 0x1234, source);
    Assembly reverse(Kind::Offer,0x1234,10,100);
    for (unsigned i=0;i<8;++i) {
        const auto result=reverse.accept(frames[7-i],11+i);
        if (i<7) require(!result,"incomplete body delivered");
        else require(result && *result==source,"reverse assembly differs");
    }
    require(!reverse.accept(frames[0],20),"duplicate complete body delivered");
    for (unsigned variant=0;variant<9;++variant) {
        Assembly checked(Kind::Offer,0x1234,10,100);
        auto bad=frames[0];
        switch (variant) {
        case 0: bad.extended=true; break;
        case 1: bad.remote=true; break;
        case 2: bad.error=true; break;
        case 3: bad.dlc=7; break;
        case 4: bad.id=0x301; break;
        case 5: bad.data[0]=0x12; break;
        case 6: bad.data[1]=8; break;
        case 7: bad.data[2]^=1; break;
        case 8: bad.data[0]=0x23; break;
        }
        require(!checked.accept(bad,11),"invalid frame delivered");
        for (unsigned i=1;i<8;++i) require(!checked.accept(frames[i],12+i),"invalid fragment entered assembly");
        auto result=checked.accept(frames[0],30);
        require(result && *result==source,"invalid frame poisoned valid context");
    }
    Assembly conflict(Kind::Offer,0x1234,10,100);
    conflict.accept(frames[0],11);
    auto bad=frames[0]; bad.data[4]^=1;
    conflict.accept(bad,12);
    require(conflict.state()==Assembly::State::Conflict,"conflict not failed");
    Assembly timed(Kind::Offer,0x1234,10,100);
    timed.accept(frames[0],11); timed.accept(frames[0],109);
    require(!timed.accept(frames[1],110) && timed.state()==Assembly::State::Expired,"duplicate extended deadline");
    Assembly regressed(Kind::Offer,0x1234,10,100);
    require(regressed.poll(9)==Assembly::State::ClockError,"backward clock accepted");
    rejects([]{Assembly bad(Kind::Ack,1,0,0);});
    rejects([]{fragment(Kind::Request,1,std::vector<std::uint8_t>(4));});
    rejects([]{fragment(Kind::Request,0,std::vector<std::uint8_t>(4,1));});
    rejects([]{fragment(Kind::Offer,1,std::vector<std::uint8_t>(31));});
}
}
int main(int argc,char** argv) {
    try {
        const auto actual=vectors();
        if (argc==2 && std::string(argv[1])=="--emit-dummy-vectors") {
            for (const auto& [name,value]:actual) std::cout<<name<<'\t'<<value<<'\n';
            return 0;
        }
        require(argc==1,"unexpected test argument");
        std::ifstream fixture(SESSION_FIXTURE_PATH);
        require(static_cast<bool>(fixture),"session fixture missing");
        std::map<std::string,std::string> expected;
        std::string line;
        while (std::getline(fixture,line)) {
            const auto tab=line.find('\t');
            require(tab!=std::string::npos,"bad fixture row");
            require(expected.emplace(line.substr(0,tab),line.substr(tab+1)).second,"duplicate fixture row");
        }
        require(actual==expected,"candidate differs from independent public dummy vectors");
        cryptoNegatives(); assemblyNegatives();
        std::cout<<"PASS candidate vectors="<<actual.size()<<"; crypto and assembly negatives passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr<<error.what()<<'\n'; return 1;
    }
}
