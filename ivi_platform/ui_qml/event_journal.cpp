#include "event_journal.h"
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QStorageInfo>
#include <QUuid>
#include <algorithm>
#include <cerrno>
#include <limits>
#include <stdexcept>
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

namespace {
constexpr qint64 max_line=65536;
struct FileGuard{int fd=-1;~FileGuard(){if(fd>=0)::close(fd);}};
void privateDir(const QString& path){
    struct stat info{};const auto bytes=QFile::encodeName(path);
    if(!QDir::isAbsolutePath(path)||::lstat(bytes.constData(),&info)||!S_ISDIR(info.st_mode)||info.st_uid!=geteuid()||(info.st_mode&0077))
        throw std::runtime_error("event store needs an existing private owned directory");
}
QStringList segments(const QString& path){
    const auto names=QDir(path).entryList({QStringLiteral("events-*.jsonl")},QDir::Files|QDir::System,QDir::Name);
    if(names.size()>4096)throw std::runtime_error("event segment count limit");
    const QRegularExpression pattern(QStringLiteral("^events-[0-9]{20}\\.jsonl$"));
    for(const auto& name:names)if(!pattern.match(name).hasMatch())throw std::runtime_error("event segment name rejected");
    return names;
}
struct Scan{QStringList display;QJsonObject protection;quint64 sequence=0,bytes=0;bool partial=false,corrupt=false,gaps=false;};
Scan scan(const QString& directory){
    privateDir(directory);Scan result;
    for(const auto& name:segments(directory)){
      try{
        const auto path=QFile::encodeName(QDir(directory).filePath(name));
        FileGuard guard;guard.fd=::open(path.constData(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK);
        struct stat info{};
        if(guard.fd<0||fstat(guard.fd,&info)||!S_ISREG(info.st_mode)||info.st_uid!=geteuid()||(info.st_mode&0077))
            throw std::runtime_error("event segment ownership or type rejected");
        result.bytes+=static_cast<quint64>(info.st_size);
        QFile file;if(!file.open(guard.fd,QIODevice::ReadOnly,QFileDevice::DontCloseHandle))throw std::runtime_error("event read failed");
        while(!file.atEnd()){
            const auto line=file.readLine(max_line+1);
            if(line.size()>max_line)throw std::runtime_error("event row exceeds bound");
            if(!line.endsWith('\n')){result.partial=true;break;} // preserve original, never append to it
            QJsonParseError error{};const auto document=QJsonDocument::fromJson(line,&error);
            if(error.error!=QJsonParseError::NoError||!document.isObject())throw std::runtime_error("corrupt event row");
            const auto row=document.object();bool ok=false;const auto sequence=row.value("sequence").toString().toULongLong(&ok);
            const auto payload=row.value("payload").toString();
            if(row.value("schema").toInt()!=1||!ok||sequence<=result.sequence||row.value("sha256").toString().toLatin1()!=EventJournal::digest(row.value("sequence").toString(),payload))
                throw std::runtime_error("event sequence or checksum rejected");
            const auto event=QJsonDocument::fromJson(payload.toUtf8(),&error);
            if(error.error!=QJsonParseError::NoError||!event.isObject()||!event.object().value("display").isString())
                throw std::runtime_error("event body rejected");
            result.gaps|=event.object().value("previous_gap_possible").toBool()||event.object().contains("records_lost_before")||
                event.object().value("protection_link").toObject().value("gap_possible").toBool();
            if(event.object().value("category").toString()==QStringLiteral("protection-status") &&
               event.object().value("ecu_protection").isObject())result.protection=event.object();
            result.sequence=sequence;result.display.prepend(event.object().value("display").toString());
            while(result.display.size()>100)result.display.removeLast();
        }
      }catch(const std::exception&){result.corrupt=true;return result;}
    }
    return result;
}
void syncDirectory(const QString& directory){
    FileGuard guard;const auto name=QFile::encodeName(directory);guard.fd=::open(name.constData(),O_RDONLY|O_DIRECTORY|O_CLOEXEC);
    if(guard.fd<0||::fsync(guard.fd))throw std::runtime_error("event directory sync failed");
}
}
QByteArray EventJournal::digest(const QString& sequence,const QString& payload){
    return QCryptographicHash::hash(sequence.toUtf8()+'\n'+payload.toUtf8(),QCryptographicHash::Sha256).toHex();
}
QStringList EventJournal::readHistory(const QString& directory,bool* partial){
    const auto result=scan(directory);if(result.corrupt)throw std::runtime_error("corrupt event history");if(partial)*partial=result.partial;return result.display;
}
EventJournal::Policy EventJournal::loadPolicy(const QString& path){
    QFile file(path);if(!file.open(QIODevice::ReadOnly)||file.size()>4096)throw std::invalid_argument("event policy unavailable or oversized");
    QJsonParseError error{};const auto document=QJsonDocument::fromJson(file.readAll(),&error);
    const auto object=document.object();
    const QStringList keys{"directory","segment_bytes","total_bytes","warning_bytes","min_free_bytes","queue_capacity"};
    if(error.error!=QJsonParseError::NoError||!document.isObject()||object.size()!=keys.size())throw std::invalid_argument("event policy fields rejected");
    for(const auto& key:keys)if(!object.contains(key))throw std::invalid_argument("event policy incomplete");
    auto number=[&](const char* key){
        const auto value=object.value(key).toDouble(-1);
        if(value<1||value>static_cast<double>(std::numeric_limits<unsigned>::max())||value!=static_cast<quint64>(value))
            throw std::invalid_argument("event policy integer rejected");
        return static_cast<quint64>(value);
    };
    return {object.value("directory").toString(),number("segment_bytes"),number("total_bytes"),number("warning_bytes"),number("min_free_bytes"),static_cast<unsigned>(number("queue_capacity"))};
}
EventJournal::EventJournal(Policy policy,QObject* parent):QObject(parent),policy_(std::move(policy)){
    if(policy_.segment_bytes<max_line||policy_.segment_bytes>policy_.total_bytes||!policy_.warning_bytes||policy_.warning_bytes>policy_.total_bytes||!policy_.queue_capacity||policy_.queue_capacity>1024)
        throw std::invalid_argument("event policy limits rejected");
}
void EventJournal::start(){
    if(worker_.joinable())throw std::logic_error("event worker already started");
    worker_=std::thread([this]{work();});
}
EventJournal::~EventJournal(){
    {std::lock_guard<std::mutex> guard(mutex_);stopping_=true;}wake_.notify_one();if(worker_.joinable())worker_.join();
}
bool EventJournal::submit(const QJsonObject& event){
    if(QJsonDocument(event).toJson(QJsonDocument::Compact).size()>max_line/4){
        std::lock_guard<std::mutex> guard(mutex_);++lost_;return false;
    }
    std::lock_guard<std::mutex> guard(mutex_);
    if(stopping_||queue_.size()>=policy_.queue_capacity){++lost_;return false;}
    queue_.push_back(event);wake_.notify_one();return true;
}
void EventJournal::work(){
    FileGuard lock,active;
    bool protection_loaded=false;
    QString last_status;
    auto status=[&](const QString& message){if(message!=last_status){last_status=message;emit storageStatus(message);}};
    auto lost=[&]{std::lock_guard<std::mutex> guard(mutex_);++lost_;};
    try{
        privateDir(policy_.directory);const auto name=QFile::encodeName(QDir(policy_.directory).filePath("journal.lock"));
        lock.fd=::open(name.constData(),O_CREAT|O_RDWR|O_NOFOLLOW|O_CLOEXEC,0600);struct stat info{};
        if(lock.fd<0||fstat(lock.fd,&info)||!S_ISREG(info.st_mode)||info.st_uid!=geteuid()||(info.st_mode&0077)||flock(lock.fd,LOCK_EX|LOCK_NB))
            throw std::runtime_error("event store already owned or lock rejected");
        const auto marker_name=QFile::encodeName(QDir(policy_.directory).filePath("writer-active"));
        FileGuard marker;marker.fd=::open(marker_name.constData(),O_CREAT|O_EXCL|O_WRONLY|O_NOFOLLOW|O_CLOEXEC,0600);
        bool previous_gap=marker.fd<0&&errno==EEXIST;
        if(previous_gap)marker.fd=::open(marker_name.constData(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC|O_NONBLOCK);
        struct stat marker_info{};
        if(marker.fd<0||::fstat(marker.fd,&marker_info)||!S_ISREG(marker_info.st_mode)||marker_info.st_uid!=geteuid()||(marker_info.st_mode&0077))
            throw std::runtime_error("event writer marker rejected");
        if(!previous_gap){if(::write(marker.fd,"active\n",7)!=7||::fsync(marker.fd))throw std::runtime_error("event marker sync failed");syncDirectory(policy_.directory);}
        const auto recovered=scan(policy_.directory);quint64 sequence=recovered.sequence,total=recovered.bytes,segment_size=0,reported_loss=0;
        emit historyLoaded(recovered.display);
        emit protectionHistoryLoaded(recovered.corrupt?QJsonObject{}:recovered.protection,
            recovered.corrupt||recovered.partial||recovered.gaps||previous_gap);
        protection_loaded=true;
        if(recovered.corrupt)throw std::runtime_error("event corruption; verified prefix retained");
        previous_gap|=recovered.partial;
        bool history_gap=recovered.gaps||previous_gap;
        status(previous_gap ? QStringLiteral("이전 종료 구간의 기록 누락 가능성을 확인하고 있습니다") : recovered.partial ? QStringLiteral("일부 불완전 기록을 제외하고 복구했습니다") : QStringLiteral("이벤트 기록 저장 준비 완료"));
        quint64 file_sequence=sequence;
        const auto existing=segments(policy_.directory);
        if(!existing.isEmpty())file_sequence=std::max(file_sequence,existing.last().mid(7,20).toULongLong());
        QString day;
        while(true){
            QJsonObject event;
            {std::unique_lock<std::mutex> guard(mutex_);wake_.wait(guard,[&]{return stopping_||!queue_.empty();});
                if(queue_.empty()){
                    if(!lost_&&!previous_gap){
                        struct stat current{};
                        if(!::lstat(marker_name.constData(),&current)&&current.st_dev==marker_info.st_dev&&current.st_ino==marker_info.st_ino){
                            if(::unlink(marker_name.constData()))throw std::runtime_error("event marker cleanup failed");
                            syncDirectory(policy_.directory);
                        }
                    }
                    return;
                }
                event=std::move(queue_.front());queue_.pop_front();}
            quint64 omitted;{std::lock_guard<std::mutex> guard(mutex_);omitted=lost_;}
            if(previous_gap)event.insert("previous_gap_possible",true);
            if(omitted>reported_loss)event.insert("records_lost_before",QString::number(omitted-reported_loss));
            // Only the writer knows losses that occurred after this event was
            // queued. Keep that history in the durable link even if an earlier
            // unrelated record already consumed records_lost_before.
            if(event.value("category").toString()==QStringLiteral("protection-status") &&
               event.value("ecu_protection").isObject() && event.value("protection_link").isObject() &&
               (history_gap||previous_gap||omitted>reported_loss)){
                auto link=event.value("protection_link").toObject();
                link.insert("gap_possible",true);event.insert("protection_link",link);
            }
            if(sequence==std::numeric_limits<quint64>::max())throw std::runtime_error("event sequence exhausted");
            const auto next=QString::number(sequence+1);
            const auto payload=QString::fromUtf8(QJsonDocument(event).toJson(QJsonDocument::Compact));
            const auto line=QJsonDocument(QJsonObject{{"schema",1},{"sequence",next},{"payload",payload},{"sha256",QString::fromLatin1(digest(next,payload))}}).toJson(QJsonDocument::Compact)+'\n';
            QStorageInfo space(policy_.directory);space.refresh();
            if(line.size()>max_line||total+static_cast<quint64>(line.size())>policy_.total_bytes||!space.isValid()||space.bytesAvailable()<0||static_cast<quint64>(space.bytesAvailable())<policy_.min_free_bytes){
                lost();status(QStringLiteral("기록 저장 중단 · 공간 확보 또는 내보내기가 필요합니다"));continue;
            }
            const auto today=QDateTime::currentDateTimeUtc().toString(Qt::ISODate).left(10);
            if(active.fd<0||segment_size+static_cast<quint64>(line.size())>policy_.segment_bytes||today!=day){
                if(active.fd>=0){::close(active.fd);active.fd=-1;}
                if(segments(policy_.directory).size()>=4096){lost();status(QStringLiteral("기록 저장 중단 · 파일 보관 한도에 도달했습니다"));continue;}
                if(file_sequence==std::numeric_limits<quint64>::max())throw std::runtime_error("event segment ordinal exhausted");
                const auto path=QFile::encodeName(QDir(policy_.directory).filePath(QStringLiteral("events-%1.jsonl").arg(++file_sequence,20,10,QChar('0'))));
                active.fd=::open(path.constData(),O_CREAT|O_EXCL|O_WRONLY|O_NOFOLLOW|O_CLOEXEC,0600);
                if(active.fd<0)throw std::runtime_error("new event segment unavailable");
                syncDirectory(policy_.directory);segment_size=0;day=today;
            }
            qint64 offset=0;
            while(offset<line.size()){
                const auto count=::write(active.fd,line.constData()+offset,line.size()-offset);
                if(count<0&&errno==EINTR)continue;
                if(count<=0)throw std::runtime_error("event write failed");offset+=count;
            }
            if(::fsync(active.fd))throw std::runtime_error("event sync failed");
            history_gap|=previous_gap||omitted>reported_loss;previous_gap=false;
            sequence++;total+=line.size();segment_size+=line.size();reported_loss=omitted;
            emit committed(event.value("event_id").toString());
            if(event.value("category").toString()==QStringLiteral("protection-status") && event.value("ecu_protection").isObject())
                emit protectionCommitted(event);
            status(total>=policy_.warning_bytes ? QStringLiteral("기록 공간이 부족해지고 있습니다 · 내보내기를 권장합니다") : history_gap ? QStringLiteral("이벤트 저장 중 · 기록 누락 가능 구간이 있습니다") : QStringLiteral("이벤트 기록 저장 중"));
        }
    }catch(const std::exception&){
        if(!protection_loaded)emit protectionHistoryLoaded(QJsonObject{},true);
        // Keep the object alive to count rejected future submissions. No disk
        // retry loop or destructive repair can conceal corruption/permission loss.
        {std::lock_guard<std::mutex> guard(mutex_);stopping_=true;++lost_;lost_+=queue_.size();queue_.clear();}
        status(QStringLiteral("이벤트 기록 저장 실패 · 현재 화면은 계속 동작합니다"));
    }
}
