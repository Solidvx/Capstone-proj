#include "dashboard_view_model.h"

#include <QSignalSpy>
#include <QElapsedTimer>
#include <QEventLoop>
#include <QTimer>
#include <QtTest>

#include <algorithm>
#include <numeric>
#include <thread>
#include <vector>

class DashboardViewModelTest : public QObject {
    Q_OBJECT

private slots:
    void initialStateHidesMeasurements() {
        DashboardViewModel model;
        QVERIFY(!model.valid());
        QVERIFY(!model.measurementsAvailable());
        QCOMPARE(model.sensorState(), QStringLiteral("UNSUPPORTED_LEGACY_WIRE"));
        QVERIFY(model.sensorStateWarning());
        QVERIFY(!model.failSafeOverlayActive());
    }

    void mapsStateAndFullScreenWarning() {
        DashboardViewModel model;
        ivi::VehicleSnapshot snapshot;
        snapshot.vehicle.valid = true;
        snapshot.vehicle.stale = true;
        snapshot.vehicle.soc_percent = 12.5;
        snapshot.vehicle.sensor_state = 4;
        snapshot.vehicle.fail_safe_state = 2;
        snapshot.vehicle.fail_safe_reason = 7;
        snapshot.last_good_age_ms = 450;

        model.updateSnapshot(snapshot);
        QVERIFY(model.measurementsAvailable());
        QVERIFY(model.sensorUsesLastGood());
        QCOMPARE(model.lastGoodAgeMs(), qulonglong{450});
        QCOMPARE(model.failSafeState(), QStringLiteral("CRITICAL"));
        QCOMPARE(model.failSafeReason(), QStringLiteral("WATCHDOG_RESTART_FAILED"));
        QVERIFY(model.failSafeOverlayActive());
    }

    void socBandUsesSpecifiedBoundaries() {
        DashboardViewModel model;
        ivi::VehicleSnapshot snapshot;
        snapshot.vehicle.valid = true;

        snapshot.vehicle.soc_percent = 50.0;
        model.updateSnapshot(snapshot);
        QCOMPARE(model.socBand(), QStringLiteral("high"));
        snapshot.vehicle.soc_percent = 49.5;
        model.updateSnapshot(snapshot);
        QCOMPARE(model.socBand(), QStringLiteral("medium"));
        snapshot.vehicle.soc_percent = 20.0;
        model.updateSnapshot(snapshot);
        QCOMPARE(model.socBand(), QStringLiteral("medium"));
        snapshot.vehicle.soc_percent = 19.5;
        model.updateSnapshot(snapshot);
        QCOMPARE(model.socBand(), QStringLiteral("low"));

        snapshot.vehicle.valid = false;
        model.updateSnapshot(snapshot);
        QCOMPARE(model.socBand(), QStringLiteral("unavailable"));
    }

    void acknowledgementCarriesObservedSequence() {
        DashboardViewModel model;
        ivi::VehicleSnapshot snapshot;
        snapshot.security_alert = ivi::SecurityAlert{4, 1.5, 0x100, 1};
        snapshot.security_alert_sequence = 42;
        model.updateSnapshot(snapshot);

        QSignalSpy acknowledgement(
            &model, &DashboardViewModel::securityAlertAcknowledgementRequested);
        model.acknowledgeSecurityAlert();
        QCOMPARE(acknowledgement.count(), 1);
        QCOMPARE(acknowledgement.takeFirst().at(0).toULongLong(), qulonglong{42});
    }

    void workerUpdateIsQueuedToOwnerThread() {
        DashboardViewModel model;
        QSignalSpy changes(&model, &DashboardViewModel::dataChanged);
        ivi::VehicleSnapshot snapshot;
        snapshot.vehicle.valid = true;
        snapshot.vehicle.soc_percent = 88.0;

        std::thread worker([&model, snapshot]() { model.updateSnapshot(snapshot); });
        worker.join();

        QTRY_COMPARE(changes.count(), 1);
        QVERIFY(model.valid());
        QCOMPARE(model.soc(), 88.0);
        QCOMPARE(model.thread(), QThread::currentThread());
    }

    void measurementCarriesT1ThroughT3Once() {
        DashboardViewModel model;
        QSignalSpy measurements(&model, &DashboardViewModel::measurementReady);
        ivi::VehicleSnapshot snapshot;
        snapshot.vehicle.valid = true;
        snapshot.measurement_sequence = 7;
        snapshot.t1_received_ns = 100;
        snapshot.t2_published_ns = 200;

        model.updateSnapshot(snapshot);
        QCOMPARE(measurements.count(), 1);
        const auto values = measurements.takeFirst();
        QCOMPARE(values.at(0).toULongLong(), qulonglong{7});
        QCOMPARE(values.at(1).toULongLong(), qulonglong{100});
        QCOMPARE(values.at(2).toULongLong(), qulonglong{200});
        QVERIFY(values.at(3).toULongLong() >= qulonglong{200});

        model.updateSnapshot(snapshot);
        QCOMPARE(measurements.count(), 0);
    }

    void queuedUpdateLatencyMeetsHostTarget() {
        DashboardViewModel model;
        std::vector<qint64> latencies;
        latencies.reserve(100);

        for (int sample = 0; sample < 100; ++sample) {
            ivi::VehicleSnapshot snapshot;
            snapshot.vehicle.valid = true;
            snapshot.vehicle.soc_percent = static_cast<double>(sample);
            QEventLoop loop;
            QTimer timeout;
            timeout.setSingleShot(true);
            connect(&model, &DashboardViewModel::dataChanged, &loop, &QEventLoop::quit,
                    Qt::SingleShotConnection);
            connect(&timeout, &QTimer::timeout, &loop, &QEventLoop::quit);

            QElapsedTimer timer;
            timer.start();
            timeout.start(1000);
            std::thread worker([&model, snapshot]() { model.updateSnapshot(snapshot); });
            loop.exec();
            worker.join();
            QVERIFY2(timeout.isActive(), "queued ViewModel update timed out");
            latencies.push_back(timer.nsecsElapsed());
        }

        std::sort(latencies.begin(), latencies.end());
        const double average_ms =
            static_cast<double>(std::accumulate(latencies.begin(), latencies.end(), qint64{0})) /
            static_cast<double>(latencies.size()) / 1000000.0;
        const double p99_ms = static_cast<double>(latencies[98]) / 1000000.0;
        qInfo() << "DashboardViewModel T2-T3 host latency: average" << average_ms
                << "ms, p99" << p99_ms << "ms, samples" << latencies.size();
        QVERIFY2(average_ms <= 20.0, "average queued update latency exceeded 20 ms");
        QVERIFY2(p99_ms <= 50.0, "p99 queued update latency exceeded 50 ms");
    }
};

QTEST_GUILESS_MAIN(DashboardViewModelTest)

#include "test_dashboard_view_model.moc"
