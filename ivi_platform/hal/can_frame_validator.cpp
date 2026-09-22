#include "can_frame_validator.h"

#include "can_parser.h"
#include "can_types.h"

namespace ivi {

CanFrameValidation validateClassicCanFrame(std::uint32_t raw_can_id, std::uint8_t dlc) {
    if ((raw_can_id & kCanEffFlag) != 0U) {
        return CanFrameValidation::kExtendedFrame;
    }
    if ((raw_can_id & kCanRtrFlag) != 0U) {
        return CanFrameValidation::kRemoteFrame;
    }
    if ((raw_can_id & kCanErrFlag) != 0U) {
        return CanFrameValidation::kErrorFrame;
    }
    if ((raw_can_id & ~kCanSffMask) != 0U) {
        return CanFrameValidation::kExtendedFrame;
    }
    if (dlc != kClassicCanPayloadSize) {
        return CanFrameValidation::kInvalidLength;
    }
    if (!isSupportedCanId(raw_can_id & kCanSffMask)) {
        return CanFrameValidation::kUnsupportedId;
    }
    return CanFrameValidation::kAccepted;
}

}  // namespace ivi
