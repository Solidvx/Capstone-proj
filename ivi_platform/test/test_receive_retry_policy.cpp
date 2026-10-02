#include "receive_retry_policy.h"
#include "test_support.h"

namespace {

void run() {
    ivi::ReceiveRetryBudget retries(3);
    EXPECT_TRUE(retries.consumeRetry());
    EXPECT_TRUE(retries.consumeRetry());
    EXPECT_TRUE(retries.consumeRetry());
    EXPECT_FALSE(retries.consumeRetry());
    EXPECT_EQ(retries.retriesUsed(), 3U);

    retries.reset();
    EXPECT_EQ(retries.retriesUsed(), 0U);
    EXPECT_TRUE(retries.consumeRetry());

    ivi::ReceiveRetryBudget no_retries(0);
    EXPECT_FALSE(no_retries.consumeRetry());
}

}  // namespace

int main() {
    return runTestProgram("SocketCAN receive retry budget", run);
}
