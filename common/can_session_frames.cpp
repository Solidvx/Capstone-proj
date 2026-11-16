#include "can_session_frames.h"

#include <algorithm>
#include <stdexcept>

namespace capstone::session_v2 {
bool validCurrentState(const Payload& payload) {
    if(payload[0]>3 || payload[1]>1 ||
       !std::all_of(payload.begin()+3,payload.end(),[](auto value){return value==0;}))return false;
    if(payload[1]==0)return payload[2]==0;
    switch(payload[0]){
    case 0:return payload[2]==5 || payload[2]==6;
    case 1:return payload[2]==1 || payload[2]==3 || payload[2]==7;
    case 2:return payload[2]==2;
    case 3:return payload[2]==4;
    }
    return false;
}
namespace {
std::size_t bodyLength(Kind kind) {
    switch (kind) {
    case Kind::Request: return 4;
    case Kind::Offer: return 32;
    case Kind::Receipt: return 20;
    case Kind::Challenge: case Kind::Confirm: case Kind::Ack: case Kind::Ready: return 16;
    }
    throw std::invalid_argument("unknown session message kind");
}
std::uint16_t senderId(Kind kind) {
    return kind == Kind::Request || kind == Kind::Offer || kind == Kind::Ack ? 0x300 : 0x301;
}
bool requestValid(Kind kind, std::uint16_t id, const std::vector<std::uint8_t>& body) {
    return kind != Kind::Request || (id == 0 && std::all_of(body.begin(), body.end(),
                                                        [](auto byte){ return byte == 0; }));
}
}
std::vector<Frame> fragment(Kind kind, std::uint16_t transfer_id,
                            const std::vector<std::uint8_t>& body) {
    if (body.size() != bodyLength(kind) || !requestValid(kind, transfer_id, body))
        throw std::invalid_argument("session body length or REQUEST value");
    std::vector<Frame> result(body.size() / 4);
    for (std::size_t i = 0; i < result.size(); ++i) {
        auto& frame = result[i];
        frame.id = senderId(kind);
        frame.data[0] = 0x20 | static_cast<std::uint8_t>(kind);
        frame.data[1] = static_cast<std::uint8_t>(i);
        frame.data[2] = static_cast<std::uint8_t>(transfer_id >> 8);
        frame.data[3] = static_cast<std::uint8_t>(transfer_id);
        std::copy_n(body.begin() + i * 4, 4, frame.data.begin() + 4);
    }
    return result;
}
Assembly::Assembly(Kind kind, std::uint16_t transfer_id, std::uint64_t started_ms,
                   std::uint64_t timeout_ms)
    : kind_(kind), transfer_id_(transfer_id), started_ms_(started_ms),
      last_ms_(started_ms), timeout_ms_(timeout_ms) {
    bodyLength(kind);
    if (!timeout_ms || (kind == Kind::Request && transfer_id != 0))
        throw std::invalid_argument("session assembly requires valid context and positive limit");
}
Assembly::State Assembly::poll(std::uint64_t now_ms) {
    if (state_ != State::Pending) return state_;
    if (now_ms < last_ms_) state_ = State::ClockError;
    else if (now_ms - started_ms_ >= timeout_ms_) state_ = State::Expired;
    last_ms_ = now_ms;
    return state_;
}
std::optional<std::vector<std::uint8_t>> Assembly::accept(const Frame& frame, std::uint64_t now_ms) {
    // Expiry wins at the exact boundary. Neither duplicates nor bad frames
    // extend the caller's original exchange/message deadline.
    if (poll(now_ms) != State::Pending) return std::nullopt;
    const auto index = frame.data[1];
    const auto count = bodyLength(kind_) / 4;
    if (frame.extended || frame.remote || frame.error || frame.dlc != 8 ||
        frame.id != senderId(kind_) || frame.data[0] != (0x20 | static_cast<std::uint8_t>(kind_)) ||
        frame.data[2] != (transfer_id_ >> 8) || frame.data[3] != (transfer_id_ & 0xff) || index >= count)
        return std::nullopt;
    std::array<std::uint8_t, 4> chunk{};
    std::copy_n(frame.data.begin() + 4, 4, chunk.begin());
    if (seen_[index] && chunks_[index] != chunk) {
        state_ = State::Conflict;
        return std::nullopt;
    }
    chunks_[index] = chunk;
    seen_[index] = true;
    if (!std::all_of(seen_.begin(), seen_.begin() + count, [](bool value){return value;}))
        return std::nullopt;
    std::vector<std::uint8_t> body;
    for (std::size_t i = 0; i < count; ++i) body.insert(body.end(), chunks_[i].begin(), chunks_[i].end());
    if (!requestValid(kind_, transfer_id_, body)) {
        state_ = State::Conflict;
        return std::nullopt;
    }
    state_ = State::Complete;
    return body;
}
}
