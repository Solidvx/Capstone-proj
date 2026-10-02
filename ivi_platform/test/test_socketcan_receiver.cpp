#include "socketcan_receiver.h"

#include "can_types.h"
#include "secoc_verifier.h"
#include "test_support.h"
#include "vehicle_data_service.h"

#include <array>
#include <algorithm>
#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include <cerrno>
#include <linux/can.h>
#include <linux/can/raw.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>

namespace {

bool socketCanRequired() {
    const char* value = std::getenv("IVI_REQUIRE_SOCKETCAN");
    return value != nullptr && std::strcmp(value, "1") == 0;
}

bool isUnavailableSocketCanError(int error) {
    return error == ENODEV || error == ENXIO || error == EPERM || error == EACCES ||
           error == EAFNOSUPPORT || error == EPROTONOSUPPORT;
}

class CanSocket {
public:
    ~CanSocket() {
        if (fd_ >= 0) {
            ::close(fd_);
        }
    }

    bool open(const char* interface_name) {
        fd_ = ::socket(PF_CAN, SOCK_RAW | SOCK_CLOEXEC, CAN_RAW);
        if (fd_ < 0) {
            return false;
        }
        ifreq request{};
        std::strncpy(request.ifr_name, interface_name, IFNAMSIZ - 1);
        if (::ioctl(fd_, SIOCGIFINDEX, &request) != 0) {
            return false;
        }
        sockaddr_can address{};
        address.can_family = AF_CAN;
        address.can_ifindex = request.ifr_ifindex;
        return ::bind(fd_, reinterpret_cast<sockaddr*>(&address), sizeof(address)) == 0;
    }

    bool send(canid_t id, std::uint8_t dlc, const ivi::CanPayload& payload) const {
        can_frame frame{};
        frame.can_id = id;
        frame.can_dlc = dlc;
        std::copy(payload.begin(), payload.end(), frame.data);
        return ::write(fd_, &frame, sizeof(frame)) == static_cast<ssize_t>(sizeof(frame));
    }

private:
    int fd_ = -1;
};

ivi::SecOcKey dummyKey() {
    ivi::SecOcKey key{};
    for (std::size_t index = 0; index < key.size(); ++index) {
        key[index] = static_cast<std::uint8_t>(index);
    }
    return key;
}

ivi::CanPayload authPayload(const ivi::SecOcVerifier& signer,
                            std::uint32_t counter,
                            const ivi::CanPayload& payload) {
    const auto mac = signer.computeTruncatedMac(ivi::kCanIdBmsStatus, counter, payload);
    return {mac[0], mac[1], mac[2], mac[3],
            static_cast<std::uint8_t>((counter >> 24U) & 0xFFU),
            static_cast<std::uint8_t>((counter >> 16U) & 0xFFU),
            static_cast<std::uint8_t>((counter >> 8U) & 0xFFU),
            static_cast<std::uint8_t>(counter & 0xFFU)};
}

template <typename Predicate>
bool waitUntil(Predicate predicate) {
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds{2};
    while (std::chrono::steady_clock::now() < deadline) {
        if (predicate()) {
            return true;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds{2});
    }
    return predicate();
}

void testSocketCanReceiver() {
    ivi::SocketCanReceiver missing;
    EXPECT_FALSE(missing.open("ivi-interface-that-does-not-exist"));

    CanSocket sender;
    if (!sender.open("vcan0")) {
        const int open_error = errno;
        if (!socketCanRequired() && isUnavailableSocketCanError(open_error)) {
            throw std::runtime_error("SKIP: vcan0 is unavailable");
        }
        throw std::runtime_error("failed to open sender on vcan0: errno=" +
                                 std::to_string(open_error));
    }

    ivi::SocketCanReceiver receiver;
    EXPECT_TRUE(receiver.open("vcan0"));
    std::mutex mutex;
    std::condition_variable received;
    std::vector<std::uint32_t> ids;
    std::vector<ivi::SocketCanReceiver::Clock::time_point> timestamps;
    receiver.setCallback([&](std::uint32_t id,
                             const ivi::CanPayload&,
                             ivi::SocketCanReceiver::Clock::time_point timestamp) {
        std::lock_guard<std::mutex> lock(mutex);
        ids.push_back(id);
        timestamps.push_back(timestamp);
        received.notify_all();
    });
    EXPECT_TRUE(receiver.start());

    const ivi::CanPayload payload{0x96, 0xBE, 0x10, 0x68, 0xFF, 0xEC, 0x41, 0x00};
    EXPECT_TRUE(sender.send(ivi::kCanIdBmsStatus, 8, payload));
    EXPECT_TRUE(sender.send(0x555, 8, payload));
    EXPECT_TRUE(sender.send(ivi::kCanIdBmsStatus, 7, payload));
    EXPECT_TRUE(sender.send(ivi::kCanIdBmsStatus | CAN_RTR_FLAG, 8, payload));

    {
        std::unique_lock<std::mutex> lock(mutex);
        EXPECT_TRUE(received.wait_for(lock, std::chrono::seconds{2}, [&] {
            return !ids.empty();
        }));
    }
    std::this_thread::sleep_for(std::chrono::milliseconds{100});

    const auto stop_started = std::chrono::steady_clock::now();
    receiver.stop();
    const auto stop_elapsed = std::chrono::steady_clock::now() - stop_started;
    EXPECT_FALSE(receiver.isRunning());
    EXPECT_TRUE(stop_elapsed < std::chrono::milliseconds{200});

    std::lock_guard<std::mutex> lock(mutex);
    EXPECT_EQ(ids.size(), std::size_t{1});
    EXPECT_EQ(ids.front(), ivi::kCanIdBmsStatus);
    EXPECT_EQ(timestamps.size(), std::size_t{1});

    ivi::VehicleDataService service(dummyKey());
    ivi::SocketCanReceiver service_receiver;
    EXPECT_TRUE(service_receiver.open("vcan0"));
    service_receiver.setCallback(
        [&service](std::uint32_t id,
                   const ivi::CanPayload& data,
                   ivi::SocketCanReceiver::Clock::time_point received_at) {
            service.processFrame(id, data, received_at);
        });
    EXPECT_TRUE(service_receiver.start());

    const ivi::SecOcVerifier signer(dummyKey());
    EXPECT_TRUE(sender.send(ivi::kCanIdBmsStatus, 8, payload));
    EXPECT_TRUE(sender.send(ivi::kCanIdBmsSecOc, 8, authPayload(signer, 0, payload)));
    EXPECT_TRUE(waitUntil([&] { return service.latest().vehicle.valid; }));
    const auto accepted = service.latest();
    EXPECT_EQ(accepted.measurement_sequence, std::uint64_t{1});
    EXPECT_TRUE(accepted.t1_received_ns <= accepted.t2_published_ns);

    auto changed = payload;
    changed[0] = 0x28;
    auto tampered_auth = authPayload(signer, 1, changed);
    tampered_auth[0] ^= 0x80;
    EXPECT_TRUE(sender.send(ivi::kCanIdBmsStatus, 8, changed));
    EXPECT_TRUE(sender.send(ivi::kCanIdBmsSecOc, 8, tampered_auth));
    EXPECT_TRUE(waitUntil([&] { return service.latest().secoc_failure_count >= 1U; }));
    EXPECT_EQ(service.latest().measurement_sequence, std::uint64_t{1});

    EXPECT_TRUE(sender.send(ivi::kCanIdBmsStatus, 8, changed));
    EXPECT_TRUE(sender.send(ivi::kCanIdBmsSecOc, 8, authPayload(signer, 0, changed)));
    EXPECT_TRUE(waitUntil([&] { return service.latest().secoc_failure_count >= 2U; }));
    EXPECT_EQ(service.latest().measurement_sequence, std::uint64_t{1});

    EXPECT_TRUE(sender.send(ivi::kCanIdBmsStatus, 8, changed));
    std::this_thread::sleep_for(ivi::VehicleDataService::kPendingTimeout +
                                std::chrono::milliseconds{10});
    EXPECT_TRUE(sender.send(ivi::kCanIdBmsSecOc, 8, authPayload(signer, 1, changed)));
    EXPECT_TRUE(waitUntil([&] { return service.latest().pending_timeout_count >= 1U; }));
    EXPECT_EQ(service.latest().measurement_sequence, std::uint64_t{1});
    EXPECT_NEAR(service.latest().vehicle.soc_percent, 75.0, 0.001);
    service_receiver.stop();
}

}  // namespace

int main() {
    try {
        testSocketCanReceiver();
        std::cout << "PASS: SocketCAN vcan receive/filter/stop\n";
        return 0;
    } catch (const std::runtime_error& error) {
        if (std::string(error.what()).rfind("SKIP:", 0) == 0) {
            std::cout << error.what() << '\n';
            return 77;
        }
        std::cerr << "FAIL: SocketCAN vcan receive/filter/stop: " << error.what() << '\n';
        return 1;
    }
}
