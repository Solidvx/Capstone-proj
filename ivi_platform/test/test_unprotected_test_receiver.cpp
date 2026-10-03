#include "test_support.h"
#include "unprotected_test_receiver.h"

int main() {
    UnprotectedTestReceiver experimental;
    ivi::VehicleDataService product;
    const ivi::CanPayload spoof{200,190,0x10,0x68,0xff,0xec,65,0};
    EXPECT_TRUE(experimental.process(ivi::kCanIdBmsStatus, spoof) == ivi::ProcessResult::kPublished);
    EXPECT_TRUE(experimental.latest().vehicle.soc_percent == 100.0);
    EXPECT_TRUE(!experimental.latest().last_secoc_verified);
    EXPECT_TRUE(product.processFrame(ivi::kCanIdBmsStatus, spoof) == ivi::ProcessResult::kPendingAuthentication);
    EXPECT_TRUE(!product.latest().vehicle.valid);
    auto invalid = spoof;
    invalid[0] = 201;
    EXPECT_TRUE(experimental.process(ivi::kCanIdBmsStatus, invalid) == ivi::ProcessResult::kRejected);
    EXPECT_TRUE(experimental.latest().vehicle.soc_percent == 100.0);
    EXPECT_TRUE(experimental.process(ivi::kCanIdBmsSecOc, spoof) == ivi::ProcessResult::kIgnored);
    return 0;
}
