#pragma once
#include <QObject>
#include <QJsonObject>
#include <QStringList>
#include <condition_variable>
#include <deque>
#include <mutex>
#include <thread>

// Local event summaries only. Private directory, explicit nondestructive policy.
// All filesystem operations, including history recovery, run on the worker.
class EventJournal : public QObject {
    Q_OBJECT
public:
    struct Policy {
        QString directory;
        quint64 segment_bytes,total_bytes,warning_bytes,min_free_bytes;
        unsigned queue_capacity;
    };
    explicit EventJournal(Policy policy,QObject* parent=nullptr);
    ~EventJournal();
    void start();
    bool submit(const QJsonObject& event);
    static Policy loadPolicy(const QString& path);
    static QByteArray digest(const QString& sequence,const QString& payload);
    static QStringList readHistory(const QString& directory,bool* partial=nullptr);
signals:
    void historyLoaded(const QStringList& history);
    void protectionHistoryLoaded(const QJsonObject& record,bool gap_possible);
    void protectionCommitted(const QJsonObject& record);
    void storageStatus(const QString& message);
    void committed(const QString& event_id);
private:
    void work();
    Policy policy_;
    std::mutex mutex_;
    std::condition_variable wake_;
    std::deque<QJsonObject> queue_;
    bool stopping_=false;
    quint64 lost_=0;
    std::thread worker_;
};
