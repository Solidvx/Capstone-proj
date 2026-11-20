#include "can_session_crypto.h"

#include <openssl/crypto.h>
#include <openssl/evp.h>
#include <openssl/hmac.h>
#include <openssl/kdf.h>
#include <openssl/rand.h>
#include <openssl/sha.h>

#include <algorithm>
#include <memory>
#include <limits>
#include <stdexcept>
#include <string>

namespace capstone::session_v2 {
namespace {
constexpr const char* labels[] = {"offer", "confirm", "ack", "data", "ready", "state-receipt", "diag-ecu", "diag-ivi"};
unsigned index(Role role) {
    const auto i = static_cast<unsigned>(role);
    if (i >= 8) throw std::invalid_argument("unknown session key role");
    return i;
}
void be16(std::vector<std::uint8_t>& out, std::uint16_t value) {
    out.push_back(static_cast<std::uint8_t>(value >> 8));
    out.push_back(static_cast<std::uint8_t>(value));
}
void be32(std::vector<std::uint8_t>& out, std::uint32_t value) {
    for (int shift = 24; shift >= 0; shift -= 8)
        out.push_back(static_cast<std::uint8_t>(value >> shift));
}
std::vector<std::uint8_t> dataInput(std::uint16_t id, std::uint32_t counter, const Payload& payload) {
    if (id > 0x7ff) throw std::invalid_argument("session data requires standard CAN ID");
    std::vector<std::uint8_t> out;
    be16(out, id); be32(out, counter);
    out.insert(out.end(), payload.begin(), payload.end());
    return out;
}
template<std::size_t N>
std::array<std::uint8_t, N> mac(const Key& key, const std::vector<std::uint8_t>& input) {
    std::array<std::uint8_t, EVP_MAX_MD_SIZE> digest{};
    unsigned length = 0;
    if (!HMAC(EVP_sha256(), key.data(), static_cast<int>(key.size()), input.data(),
              input.size(), digest.data(), &length) || length != 32) {
        OPENSSL_cleanse(digest.data(), digest.size());
        throw std::runtime_error("session HMAC failed");
    }
    std::array<std::uint8_t, N> result{};
    std::copy_n(digest.begin(), N, result.begin());
    OPENSSL_cleanse(digest.data(), digest.size());
    return result;
}
}

SessionKeys::~SessionKeys() { OPENSSL_cleanse(keys_.data(), sizeof keys_); }
SessionKeys::SessionKeys(SessionKeys&& other) noexcept : keys_(other.keys_), valid_(other.valid_) {
    OPENSSL_cleanse(other.keys_.data(), sizeof other.keys_);
    other.valid_ = false;
}
SessionKeys& SessionKeys::operator=(SessionKeys&& other) noexcept {
    if (this != &other) {
        OPENSSL_cleanse(keys_.data(), sizeof keys_);
        keys_ = other.keys_;
        valid_ = other.valid_;
        OPENSSL_cleanse(other.keys_.data(), sizeof other.keys_);
        other.valid_ = false;
    }
    return *this;
}
const Key& SessionKeys::at(Role role) const {
    if (!valid_) throw std::logic_error("session keys not available");
    return keys_.at(index(role));
}

std::vector<std::uint8_t> transcript(const Context& context) {
    const std::string domain = "CAPSTONE-CAN-SESSION";
    std::vector<std::uint8_t> result(domain.begin(), domain.end());
    result.push_back(2);
    be16(result, 0x300); be16(result, 0x301); be16(result, context.transfer_id);
    result.insert(result.end(), context.nonce_b.begin(), context.nonce_b.end());
    result.insert(result.end(), context.nonce_a.begin(), context.nonce_a.end());
    return result;
}

SessionKeys deriveKeys(const Key& shared_key, const Context& context) {
    SessionKeys result;
    std::vector<std::uint8_t> salt(context.nonce_b.begin(), context.nonce_b.end());
    salt.insert(salt.end(), context.nonce_a.begin(), context.nonce_a.end());
    const auto t = transcript(context);
    for (unsigned i = 0; i < 8; ++i) {
        const std::string label(labels[i]);
        std::vector<std::uint8_t> info(label.begin(), label.end());
        info.insert(info.end(), t.begin(), t.end());
        std::unique_ptr<EVP_PKEY_CTX, decltype(&EVP_PKEY_CTX_free)> ctx(
            EVP_PKEY_CTX_new_id(EVP_PKEY_HKDF, nullptr), EVP_PKEY_CTX_free);
        auto length = result.keys_[i].size();
        if (!ctx || EVP_PKEY_derive_init(ctx.get()) <= 0 ||
            EVP_PKEY_CTX_set_hkdf_mode(ctx.get(), EVP_PKEY_HKDEF_MODE_EXTRACT_AND_EXPAND) <= 0 ||
            EVP_PKEY_CTX_set_hkdf_md(ctx.get(), EVP_sha256()) <= 0 ||
            EVP_PKEY_CTX_set1_hkdf_salt(ctx.get(), salt.data(), static_cast<int>(salt.size())) <= 0 ||
            EVP_PKEY_CTX_set1_hkdf_key(ctx.get(), shared_key.data(), static_cast<int>(shared_key.size())) <= 0 ||
            EVP_PKEY_CTX_add1_hkdf_info(ctx.get(), info.data(), static_cast<int>(info.size())) <= 0 ||
            EVP_PKEY_derive(ctx.get(), result.keys_[i].data(), &length) <= 0 || length != 32)
            throw std::runtime_error("session HKDF failed");
    }
    result.valid_ = true;
    return result;
}

Tag controlTag(const SessionKeys& keys, const Context& context, Role role) {
    if (role!=Role::Offer && role!=Role::Confirm && role!=Role::Ack && role!=Role::Ready)
        throw std::invalid_argument("control key role required");
    return mac<16>(keys.at(role), transcript(context));
}
std::array<std::uint8_t, 4> dataMac(const Key& key, std::uint16_t can_id,
                                  std::uint32_t counter, const Payload& payload) {
    return mac<4>(key, dataInput(can_id, counter, payload));
}
Tag stateReceiptTag(const SessionKeys& keys, const Context& context,
                    std::uint32_t counter, const Payload& payload) {
    auto input = transcript(context);
    const auto data = dataInput(0x104, counter, payload);
    input.insert(input.end(), data.begin(), data.end());
    return mac<16>(keys.at(Role::StateReceipt), input);
}
bool tagMatches(const Tag& expected, const Tag& received) {
    return CRYPTO_memcmp(expected.data(), received.data(), expected.size()) == 0;
}
Nonce freshNonce() {
    Nonce nonce{};
    if (RAND_bytes(nonce.data(), static_cast<int>(nonce.size())) != 1)
        throw std::runtime_error("session nonce generation failed");
    return nonce;
}
std::optional<std::uint32_t> takeCounter(std::uint64_t& next) {
    if(next>std::numeric_limits<std::uint32_t>::max())return std::nullopt;
    return static_cast<std::uint32_t>(next++);
}
Nonce contextId(const Context& context) {
    const auto input=transcript(context);
    std::array<std::uint8_t,SHA256_DIGEST_LENGTH> hash{};
    if(!SHA256(input.data(),input.size(),hash.data()))throw std::runtime_error("session identity hash failed");
    Nonce id{};std::copy_n(hash.begin(),id.size(),id.begin());return id;
}
Tag diagnosticTag(const SessionKeys& keys,std::uint16_t sender_id,const std::vector<std::uint8_t>& envelope) {
    if((sender_id!=0x302 && sender_id!=0x303) || envelope.size()<22 || envelope.size()>126)
        throw std::invalid_argument("diagnostic direction or envelope size");
    const std::string domain="CAPSTONE-CAN-DIAG";
    std::vector<std::uint8_t> input(domain.begin(),domain.end());
    input.push_back(1);be16(input,sender_id);input.insert(input.end(),envelope.begin(),envelope.end());
    return mac<16>(keys.at(sender_id==0x302 ? Role::DiagEcu : Role::DiagIvi),input);
}
}
