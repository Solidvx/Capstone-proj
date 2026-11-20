#include "latency_recorder.h"
#include <QTemporaryDir>
#include <QtTest>

class LatencyRecorderTest : public QObject {
    Q_OBJECT
private slots:
    void coalescedUpdatesNeverCountAsThreeSamples() {
        QTemporaryDir dir;
        const auto path = dir.filePath("latency.csv");
        LatencyRecorder recorder(path, "PERF-300", "real-boot-fixture", 2);
        QVERIFY(recorder.enabled());
        recorder.queue(1, 1, 2, 3);
        recorder.queue(2, 4, 5, 6);
        recorder.queue(3, 7, 8, 9);
        QVERIFY(!recorder.frameSwapped(3, 1, 10, true));
        QCOMPARE(recorder.completed(), std::size_t{1});
        QVERIFY(!recorder.frameSwapped(3, 2, 11, true)); // Animation/repeated frame.
        QCOMPARE(recorder.completed(), std::size_t{1});
        recorder.queue(4, 12, 13, 14);
        QVERIFY(recorder.frameSwapped(4, 3, 15, true));
        QFile file(path); QVERIFY(file.open(QIODevice::ReadOnly));
        const auto csv = file.readAll();
        QCOMPARE(csv.count("NOT_RENDERED,COALESCED_BEFORE_SYNC"), 2);
        QCOMPARE(csv.count(",T4,"), 2);
        QVERIFY(csv.contains("PERF-300,real-boot-fixture,3,T4,10,FRAME_SWAPPED"));
    }
    void laterGuiUpdateCannotBeAttributedToEarlierFrame() {
        QTemporaryDir dir;
        const auto path = dir.filePath("latency.csv");
        LatencyRecorder recorder(path, "PERF-1000", "boot", 1000);
        recorder.queue(1, 1, 2, 3);
        recorder.queue(2, 4, 5, 6); // Arrived after frame 1 synchronized.
        recorder.frameSwapped(1, 1, 7, true);
        QCOMPARE(recorder.completed(), std::size_t{1});
        recorder.finish();
        QFile file(path); QVERIFY(file.open(QIODevice::ReadOnly));
        QVERIFY(file.readAll().contains("2,RESULT,,INDETERMINATE,NO_MATCHING_SWAP_BEFORE_EXIT"));
    }
    void invalidAndHiddenFramesAreNotCompleteAndFilesAreNotOverwritten() {
        QTemporaryDir dir;
        const auto path = dir.filePath("latency.csv");
        LatencyRecorder recorder(path, "PERF", "boot", 1);
        recorder.queue(1, 10, 20, 30);
        QVERIFY(!recorder.frameSwapped(1, 1, 25, true));
        recorder.queue(2, 40, 50, 60);
        QVERIFY(!recorder.frameSwapped(2, 2, 70, false));
        QCOMPARE(recorder.completed(), std::size_t{0});
        LatencyRecorder duplicate(path, "OTHER", "boot", 1);
        QVERIFY(!duplicate.enabled());
        QFile file(path); QVERIFY(file.open(QIODevice::ReadOnly));
        const auto csv = file.readAll();
        QVERIFY(csv.contains("INDETERMINATE,TIMESTAMP_ORDER"));
        QVERIFY(csv.contains("INDETERMINATE,WINDOW_NOT_EXPOSED"));
        QVERIFY(!csv.contains(",T4,"));
    }
};
QTEST_GUILESS_MAIN(LatencyRecorderTest)
#include "test_latency_recorder.moc"
