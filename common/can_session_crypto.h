#pragma once

#include <array>
#include <cstdint>
#include <optional>
#include <vector>

// Approved session-v2 contract. Product integration status is tracked in CHG-029.
namespace capstone::session_v2 {
using Key = std::array<std::uint8_t, 32>;
using Nonce = std::array<std::uint8_t, 16>;
using Tag = std::array<std::uint8_t, 16>;
using Payload = std::array<std::uint8_t, 8>;
enum class Role : unsigned { Offer, Confirm, Ack, Data, Ready, StateReceipt, DiagEcu, DiagIvi };

struct Context {
    std::uint16_t transfer_id;
    Nonce nonce_b;
    Nonce nonce_a;
};

class SessionKeys {
public:
    ~SessionKeys();
    SessionKeys(const SessionKeys&) = delete;
    SessionKeys& operator=(const SessionKeys&) = delete;
    SessionKeys(SessionKeys&& other) noexcept;
    SessionKeys& operator=(SessionKeys&& other) noexcept;
    const Key& at(Role role) const;
private:
    SessionKeys() = default;
    friend SessionKeys deriveKeys(const Key&, const Context&);
    std::array<Key, 8> keys_{};
    bool valid_ = false;
};

std::vector<std::uint8_t> transcript(const Context& context);
SessionKeys deriveKeys(const Key& shared_key, const Context& context);
Tag controlTag(const SessionKeys& keys, const Context& context, Role role);
std::array<std::uint8_t, 4> dataMac(const Key& key, std::uint16_t can_id,
                                  std::uint32_t counter, const Payload& payload);
Tag stateReceiptTag(const SessionKeys& keys, const Context& context,
                    std::uint32_t counter, const Payload& payload);
bool tagMatches(const Tag& expected, const Tag& received);
Nonce freshNonce(); // OpenSSL CSPRNG; failure throws, no deterministic fallback.
// Reserve exactly one ordinal. Exhaustion leaves the sequence unchanged; only
// the authenticated session commit may install a new sequence starting at0.
std::optional<std::uint32_t> takeCounter(std::uint64_t& next);
Nonce contextId(const Context& context); // public transcript fingerprint, not a key hash
Tag diagnosticTag(const SessionKeys& keys, std::uint16_t sender_id,
                  const std::vector<std::uint8_t>& unsigned_envelope);
}
