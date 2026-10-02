#include "can_frame_validator.h"
#include "can_types.h"
#include "test_support.h"

namespace {

void run() {
    EXPECT_EQ(ivi::validateClassicCanFrame(ivi::kCanIdBmsStatus, 8),
              ivi::CanFrameValidation::kAccepted);
    EXPECT_EQ(ivi::validateClassicCanFrame(ivi::kCanIdBmsFailSafe, 8),
              ivi::CanFrameValidation::kAccepted);
    EXPECT_EQ(ivi::validateClassicCanFrame(ivi::kCanIdBmsSecOc, 8),
              ivi::CanFrameValidation::kAccepted);
    EXPECT_EQ(ivi::validateClassicCanFrame(ivi::kCanIdFailSafeSecOc, 8),
              ivi::CanFrameValidation::kAccepted);
    EXPECT_EQ(ivi::validateClassicCanFrame(ivi::kCanIdIdsAlert, 8),
              ivi::CanFrameValidation::kAccepted);

    EXPECT_EQ(ivi::validateClassicCanFrame(ivi::kCanIdBmsStatus, 7),
              ivi::CanFrameValidation::kInvalidLength);
    EXPECT_EQ(ivi::validateClassicCanFrame(0x777, 8),
              ivi::CanFrameValidation::kUnsupportedId);
    EXPECT_EQ(ivi::validateClassicCanFrame(ivi::kCanIdBmsStatus | ivi::kCanEffFlag, 8),
              ivi::CanFrameValidation::kExtendedFrame);
    EXPECT_EQ(ivi::validateClassicCanFrame(0x8100, 8),
              ivi::CanFrameValidation::kExtendedFrame);
    EXPECT_EQ(ivi::validateClassicCanFrame(ivi::kCanIdBmsStatus | ivi::kCanRtrFlag, 8),
              ivi::CanFrameValidation::kRemoteFrame);
    EXPECT_EQ(ivi::validateClassicCanFrame(ivi::kCanIdBmsStatus | ivi::kCanErrFlag, 8),
              ivi::CanFrameValidation::kErrorFrame);
}

}  // namespace

int main() {
    return runTestProgram("Classic CAN frame validation", run);
}
