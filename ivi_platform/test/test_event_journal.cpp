#include "event_journal.h"
#include <QFile>
#include <QDir>
#include <QJsonDocument>
#include <QJsonArray>
#include <QTemporaryDir>
#include <QtTest>
#include <atomic>
#include <stdexcept>

// The journal emits from its disk worker. QSignalSpy appends directly while
// QList::size/first/last do not lock that worker's writes. Deliver into the
// test thread before observing the list, as the product's queued slots do.
class QueuedSignalSpy final : public QObject, public QList<QList<QVariant>> {
public:
    template<typename... Args>
    QueuedSignalSpy(const EventJournal* journal,void(EventJournal::*signal)(Args...)){
        QObject::connect(journal,signal,this,[this](Args... args){
            append(QList<QVariant>{QVariant::fromValue(args)...});
        },Qt::QueuedConnection);
    }
};

class JournalTest : public QObject {
    Q_OBJECT
    static QJsonObject event(int i,int size=0){return {{"event_id",QString::number(i)},{"display",QStringLiteral("배터리 이벤트 ")+QString::number(i)},
        {"recorded_utc","2026-11-11T00:00:00Z"},{"detail",QString(size,'x')}};}
    static EventJournal::Policy policy(const QString& path){return {path,65536,1048576,524288,1,64};}
private slots:
    void recordingLossRemainsVisibleInLaterProtectionLinks_data(){
        QTest::addColumn<QString>("source");
        QTest::newRow("oversized")<<QStringLiteral("oversized");
        QTest::newRow("full-queue")<<QStringLiteral("full-queue");
        QTest::newRow("unclean-exit")<<QStringLiteral("unclean-exit");
        QTest::newRow("prior-gap-link")<<QStringLiteral("prior-gap-link");
    }
    void recordingLossRemainsVisibleInLaterProtectionLinks(){
        QFETCH(QString,source);
        QTemporaryDir directory;auto limits=policy(directory.path());
        if(source=="full-queue")limits.queue_capacity=1;
        if(source=="unclean-exit"){
            QFile marker(QDir(directory.path()).filePath("writer-active"));
            QVERIFY(marker.open(QIODevice::WriteOnly));
            QVERIFY(marker.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner));
            marker.write("active\n");marker.close();
        }
        if(source=="prior-gap-link"){
            auto earlier=event(-1);earlier.insert("category","protection-status");
            earlier.insert("ecu_protection",QJsonObject{{"test_only","public-dummy"}});
            earlier.insert("protection_link",QJsonObject{{"status","unlinked"},{"gap_possible",true}});
            const auto payload=QString::fromUtf8(QJsonDocument(earlier).toJson(QJsonDocument::Compact));
            const auto line=QJsonDocument(QJsonObject{{"schema",1},{"sequence","1"},{"payload",payload},
                {"sha256",QString::fromLatin1(EventJournal::digest("1",payload))}}).toJson(QJsonDocument::Compact)+'\n';
            QFile file(QDir(directory.path()).filePath("events-00000000000000000001.jsonl"));
            QVERIFY(file.open(QIODevice::WriteOnly));
            QVERIFY(file.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner));
            QCOMPARE(file.write(line),line.size());file.close();
        }
        {
            EventJournal journal(limits);
            QueuedSignalSpy saved(&journal,&EventJournal::committed);
            QueuedSignalSpy protected_saved(&journal,&EventJournal::protectionCommitted);
            // An unrelated record may consume records_lost_before before the
            // next protection record reaches the disk worker.
            if(source=="oversized")QVERIFY(!journal.submit(event(0,20000)));
            QVERIFY(journal.submit(event(1)));
            if(source=="full-queue")QVERIFY(!journal.submit(event(0)));
            journal.start();QTRY_COMPARE_WITH_TIMEOUT(saved.size(),1,2000);
            auto protection=event(2);
            protection.insert("category","protection-status");
            protection.insert("ecu_protection",QJsonObject{{"test_only","public-dummy"}});
            protection.insert("protection_link",QJsonObject{{"status","updated"},{"gap_possible",false}});
            QVERIFY(journal.submit(protection));
            QTRY_COMPARE_WITH_TIMEOUT(protected_saved.size(),1,2000);
            const auto committed=protected_saved.first().first().toJsonObject();
            QVERIFY(!committed.contains("records_lost_before"));
            QVERIFY(committed.value("protection_link").toObject().value("gap_possible").toBool());
            QCOMPARE(committed.value("protection_link").toObject().value("status").toString(),QStringLiteral("updated"));
            // A later incident cannot imply that the missing history returned.
            protection.insert("event_id","3");
            protection.insert("protection_link",QJsonObject{{"status","new-incident"},{"gap_possible",false}});
            QVERIFY(journal.submit(protection));QTRY_COMPARE_WITH_TIMEOUT(protected_saved.size(),2,2000);
            QVERIFY(protected_saved.last().first().toJsonObject().value("protection_link").toObject().value("gap_possible").toBool());
            QCOMPARE(saved.size(),3);
        }
        EventJournal reopened(policy(directory.path()));
        QueuedSignalSpy loaded(&reopened,&EventJournal::protectionHistoryLoaded);reopened.start();
        QTRY_COMPARE_WITH_TIMEOUT(loaded.size(),1,2000);
        QVERIFY(loaded.first().at(1).toBool());
        QVERIFY(loaded.first().at(0).toJsonObject().value("protection_link").toObject().value("gap_possible").toBool());
    }
    void onlyFsyncedProtectionRecordsAreRecoveredAsLinkAnchors(){
        QTemporaryDir directory;auto protection=event(1);
        protection.insert("category","protection-status");
        protection.insert("ecu_protection",QJsonObject{{"test_only","public-dummy"}});
        {
            EventJournal journal(policy(directory.path()));
            QueuedSignalSpy loaded(&journal,&EventJournal::protectionHistoryLoaded);
            QueuedSignalSpy protected_saved(&journal,&EventJournal::protectionCommitted);
            QueuedSignalSpy saved(&journal,&EventJournal::committed);
            QVERIFY(journal.submit(protection));journal.start();
            QTRY_COMPARE_WITH_TIMEOUT(protected_saved.size(),1,2000);
            QCOMPARE(loaded.size(),1);QVERIFY(loaded.first().at(0).toJsonObject().isEmpty());
            QCOMPARE(protected_saved.first().at(0).toJsonObject().value("event_id"),protection.value("event_id"));
            QVERIFY(journal.submit(event(2)));QTRY_COMPARE_WITH_TIMEOUT(saved.size(),2,2000);
            QCOMPARE(protected_saved.size(),1); // unrelated events cannot replace the protection anchor
        }
        EventJournal journal(policy(directory.path()));
        QueuedSignalSpy loaded(&journal,&EventJournal::protectionHistoryLoaded);journal.start();
        QTRY_COMPARE_WITH_TIMEOUT(loaded.size(),1,2000);
        QCOMPARE(loaded.first().at(0).toJsonObject().value("event_id"),protection.value("event_id"));
        QVERIFY(!loaded.first().at(1).toBool());
    }
    void oversizedSubmissionIsCountedInNextDurableRecord(){
        QTemporaryDir directory;
        {
            EventJournal journal(policy(directory.path()));QueuedSignalSpy saved(&journal,&EventJournal::committed);
            QVERIFY(!journal.submit(event(1,20000)));
            QVERIFY(journal.submit(event(2)));
            journal.start();QTRY_COMPARE_WITH_TIMEOUT(saved.size(),1,2000);
        }
        const auto names=QDir(directory.path()).entryList({"events-*.jsonl"});QCOMPARE(names.size(),1);
        QFile file(QDir(directory.path()).filePath(names.first()));QVERIFY(file.open(QIODevice::ReadOnly));
        const auto row=QJsonDocument::fromJson(file.readLine()).object();
        const auto payload=row.value("payload").toString();
        QCOMPARE(row.value("sha256").toString().toLatin1(),EventJournal::digest(row.value("sequence").toString(),payload));
        const auto record=QJsonDocument::fromJson(payload.toUtf8()).object();
        QCOMPARE(record.value("event_id").toString(),QStringLiteral("2"));
        QCOMPARE(record.value("records_lost_before").toString(),QStringLiteral("1"));
        QCOMPARE(EventJournal::readHistory(directory.path()),QStringList{QStringLiteral("배터리 이벤트 2")});
    }
    void secondWriterCannotReplaceFirstWriterOrEraseItsMarker(){
        QTemporaryDir directory;
        {
            EventJournal owner(policy(directory.path()));QueuedSignalSpy saved(&owner,&EventJournal::committed);
            owner.start();QVERIFY(owner.submit(event(1)));QTRY_COMPARE_WITH_TIMEOUT(saved.size(),1,2000);
            QVERIFY(QFileInfo::exists(QDir(directory.path()).filePath("writer-active")));
            {
                EventJournal contender(policy(directory.path()));QueuedSignalSpy status(&contender,&EventJournal::storageStatus);
                contender.start();QTRY_VERIFY_WITH_TIMEOUT(!status.isEmpty(),2000);
                QVERIFY(status.last().first().toString().contains(QStringLiteral("실패")));
                QVERIFY(!contender.submit(event(2)));
                QVERIFY(QFileInfo::exists(QDir(directory.path()).filePath("writer-active")));
            }
            QVERIFY(owner.submit(event(3)));QTRY_COMPARE_WITH_TIMEOUT(saved.size(),2,2000);
        }
        QCOMPARE(EventJournal::readHistory(directory.path()),
                 (QStringList{QStringLiteral("배터리 이벤트 3"),QStringLiteral("배터리 이벤트 1")}));
        QVERIFY(!QFileInfo::exists(QDir(directory.path()).filePath("writer-active")));
    }
    void publicDirectoryCannotReceivePrivateHistory(){
        QTemporaryDir directory;
        QVERIFY(QFile::setPermissions(directory.path(),QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ExeOwner|
            QFileDevice::ReadGroup|QFileDevice::ExeGroup));
        {
            EventJournal journal(policy(directory.path()));QueuedSignalSpy status(&journal,&EventJournal::storageStatus);
            journal.start();QTRY_VERIFY_WITH_TIMEOUT(!status.isEmpty(),2000);
            QVERIFY(status.last().first().toString().contains(QStringLiteral("실패")));
            QVERIFY(!journal.submit(event(1)));
        }
        QVERIFY(QDir(directory.path()).entryList(QDir::Files|QDir::Hidden|QDir::System).isEmpty());
        QVERIFY(QFile::setPermissions(directory.path(),QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ExeOwner));
    }
    void validChecksumCannotHideMalformedEventBody(){
        QTemporaryDir directory;
        const auto path=QDir(directory.path()).filePath("events-00000000000000000001.jsonl");
        const auto payload=QString::fromUtf8(QJsonDocument(QJsonObject{{"event_id","dummy-without-display"}}).toJson(QJsonDocument::Compact));
        const auto bytes=QJsonDocument(QJsonObject{{"schema",1},{"sequence","1"},{"payload",payload},
            {"sha256",QString::fromLatin1(EventJournal::digest("1",payload))}}).toJson(QJsonDocument::Compact)+'\n';
        QFile file(path);QVERIFY(file.open(QIODevice::WriteOnly));
        QVERIFY(file.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner));
        QCOMPARE(file.write(bytes),bytes.size());file.close();
        QVERIFY_THROWS_EXCEPTION(std::runtime_error,EventJournal::readHistory(directory.path()));
        {
            EventJournal journal(policy(directory.path()));QueuedSignalSpy saved(&journal,&EventJournal::committed),status(&journal,&EventJournal::storageStatus);
            std::atomic<int> submission_on_failure{-1};
            connect(&journal,&EventJournal::storageStatus,&journal,[&](const QString& message){
                if(message.contains(QStringLiteral("실패")))
                    submission_on_failure.store(journal.submit(event(3)) ? 1 : 0);
            },Qt::DirectConnection);
            journal.start();QTRY_VERIFY_WITH_TIMEOUT(!status.isEmpty(),2000);
            QVERIFY(status.last().first().toString().contains(QStringLiteral("실패")));
            QCOMPARE(submission_on_failure.load(),0); // Failure publication already means submissions are closed.
            QVERIFY(!journal.submit(event(2)));QCOMPARE(saved.size(),0);
        }
        QVERIFY(file.open(QIODevice::ReadOnly));QCOMPARE(file.readAll(),bytes);
        QCOMPARE(QDir(directory.path()).entryList({"events-*.jsonl"}).size(),1);
    }
    void structuredIncidentAssociationSurvivesDiskSerialization(){
        QTemporaryDir directory;
        auto record=event(1);
        const QJsonArray links{QJsonObject{{"attack_type","replay"},{"incident_id","dummy-incident"},{"rejection_id","dummy-refusal"}},
                               QJsonObject{{"attack_type","flooding"},{"incident_id","dummy-flood"}}};
        record.insert("typed_incidents",links);
        {
            EventJournal journal(policy(directory.path()));QueuedSignalSpy saved(&journal,&EventJournal::committed);
            journal.start();QVERIFY(journal.submit(record));QTRY_COMPARE_WITH_TIMEOUT(saved.size(),1,2000);
        }
        const auto names=QDir(directory.path()).entryList({"events-*.jsonl"});QCOMPARE(names.size(),1);
        QFile file(QDir(directory.path()).filePath(names.first()));QVERIFY(file.open(QIODevice::ReadOnly));
        const auto row=QJsonDocument::fromJson(file.readLine()).object();
        const auto payload=row.value("payload").toString();
        QCOMPARE(row.value("sha256").toString().toLatin1(),EventJournal::digest(row.value("sequence").toString(),payload));
        QCOMPARE(QJsonDocument::fromJson(payload.toUtf8()).object().value("typed_incidents").toArray(),links);
    }
    void interruptedWriterLeavesVisibleGapEvidenceInNextRecord(){
        QTemporaryDir directory;
        QFile marker(QDir(directory.path()).filePath("writer-active"));QVERIFY(marker.open(QIODevice::WriteOnly));
        marker.setPermissions(QFileDevice::ReadOwner|QFileDevice::WriteOwner);marker.write("active\n");marker.close();
        {
            EventJournal journal(policy(directory.path()));QueuedSignalSpy saved(&journal,&EventJournal::committed);
            journal.start();journal.submit(event(1));QTRY_COMPARE_WITH_TIMEOUT(saved.size(),1,2000);
        }
        const auto file=QDir(directory.path()).entryList({"events-*.jsonl"}).first();
        QFile stored(QDir(directory.path()).filePath(file));QVERIFY(stored.open(QIODevice::ReadOnly));
        const auto row=QJsonDocument::fromJson(stored.readLine()).object();
        const auto payload=QJsonDocument::fromJson(row.value("payload").toString().toUtf8()).object();
        QVERIFY(payload.value("previous_gap_possible").toBool());
        QVERIFY(!QFileInfo::exists(marker.fileName()));
    }
    void commitsRotatesAndRestoresInOrder(){
        QTemporaryDir directory;QVERIFY(directory.isValid());
        {
            EventJournal journal(policy(directory.path()));QueuedSignalSpy saved(&journal,&EventJournal::committed);
            journal.start();for(int i=0;i<20;++i)QVERIFY(journal.submit(event(i,12000)));
            QTRY_COMPARE_WITH_TIMEOUT(saved.size(),20,5000);
        }
        const auto files=QDir(directory.path()).entryList({"events-*.jsonl"},QDir::Files);
        QVERIFY(files.size()>1);const auto history=EventJournal::readHistory(directory.path());
        QCOMPARE(history.size(),20);QCOMPARE(history.first(),QStringLiteral("배터리 이벤트 19"));
        EventJournal reopened(policy(directory.path()));QueuedSignalSpy loaded(&reopened,&EventJournal::historyLoaded);
        reopened.start();QTRY_COMPARE_WITH_TIMEOUT(loaded.size(),1,2000);
        QCOMPARE(loaded.first().first().toStringList(),history);
    }
    void partialTailIsPreservedAndNextRunUsesNewSegment(){
        QTemporaryDir directory;
        {
            EventJournal journal(policy(directory.path()));QueuedSignalSpy saved(&journal,&EventJournal::committed);
            journal.start();journal.submit(event(1));QTRY_COMPARE_WITH_TIMEOUT(saved.size(),1,2000);
        }
        const auto path=QDir(directory.path()).filePath(QDir(directory.path()).entryList({"events-*.jsonl"}).first());
        QFile damaged(path);QVERIFY(damaged.open(QIODevice::Append));damaged.write("{incomplete");damaged.close();
        {
            EventJournal journal(policy(directory.path()));QueuedSignalSpy saved(&journal,&EventJournal::committed);
            journal.start();journal.submit(event(2));QTRY_COMPARE_WITH_TIMEOUT(saved.size(),1,2000);
        }
        bool partial=false;const auto history=EventJournal::readHistory(directory.path(),&partial);
        QVERIFY(partial);QCOMPARE(history.size(),2);QCOMPARE(history.first(),QStringLiteral("배터리 이벤트 2"));
        QVERIFY(damaged.open(QIODevice::ReadOnly));QVERIFY(damaged.readAll().endsWith("{incomplete"));
    }
    void corruptionStopsWritesWithoutDeletingPreviousEvidence(){
        QTemporaryDir directory;
        {
            EventJournal journal(policy(directory.path()));QueuedSignalSpy saved(&journal,&EventJournal::committed);
            journal.start();journal.submit(event(1));QTRY_COMPARE_WITH_TIMEOUT(saved.size(),1,2000);
        }
        const auto path=QDir(directory.path()).filePath(QDir(directory.path()).entryList({"events-*.jsonl"}).first());
        QFile file(path);QVERIFY(file.open(QIODevice::ReadOnly));auto bytes=file.readAll();file.close();
bytes.replace("sha256\":\"","sha256\":\"0");
        QVERIFY(file.open(QIODevice::WriteOnly));file.write(bytes);file.close();
        EventJournal journal(policy(directory.path()));QueuedSignalSpy status(&journal,&EventJournal::storageStatus);
        journal.start();QTRY_VERIFY_WITH_TIMEOUT(!status.isEmpty(),2000);
        QVERIFY(status.last().first().toString().contains(QStringLiteral("실패")));
        QVERIFY(file.open(QIODevice::ReadOnly));QCOMPARE(file.readAll(),bytes);
    }
    void quotaPreservesExistingRowsAndRejectsFutureRecords(){
        QTemporaryDir directory;auto limits=policy(directory.path());limits.total_bytes=65536;limits.warning_bytes=32768;
        EventJournal journal(limits);QueuedSignalSpy saved(&journal,&EventJournal::committed),status(&journal,&EventJournal::storageStatus);
        journal.start();for(int i=0;i<20;++i)journal.submit(event(i,12000));
        QTRY_VERIFY_WITH_TIMEOUT(!status.isEmpty()&&status.last().first().toString().contains(QStringLiteral("중단")),3000);
        QVERIFY(saved.size()>0&&saved.size()<20);
        QCOMPARE(EventJournal::readHistory(directory.path()).size(),saved.size());
    }
};
QTEST_GUILESS_MAIN(JournalTest)
#include "test_event_journal.moc"
