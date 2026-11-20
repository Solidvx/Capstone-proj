#pragma once

#include <QFile>
#include <QString>
#include <cstdint>
#include <map>

// GUI-thread writer. Render-thread signal handlers pass immutable frame IDs and
// signal timestamps here via queued calls; they never inspect this map.
class LatencyRecorder {
public:
    LatencyRecorder(const QString& path, const QString& run, const QString& boot,
                    std::size_t target) : run_(run), boot_(boot), target_(target) {
        if (path.isEmpty()) return;
        output_.setFileName(path);
        if (output_.open(QIODevice::WriteOnly | QIODevice::NewOnly)) {
            write("run_id,boot_id,sample_id,stage,timestamp_ns,status,reason,frame_id\n");
        }
    }
    bool enabled() const { return output_.isOpen(); }
    bool healthy() const { return healthy_; }
    std::size_t completed() const { return completed_; }
    void queue(std::uint64_t id, std::uint64_t t1, std::uint64_t t2, std::uint64_t t3) {
        if (!enabled() || pending_.count(id)) return;
        pending_[id] = {t1, t2, t3};
        row(id, "T1", QString::number(t1), "PENDING", "", 0);
        row(id, "T2", QString::number(t2), "PENDING", "", 0);
        row(id, "T3", QString::number(t3), "PENDING", "", 0);
        flush();
    }
    bool frameSwapped(std::uint64_t id, std::uint64_t frame, std::uint64_t t4, bool exposed) {
        // ID was captured while the GUI was blocked for scene synchronization.
        // Later GUI updates must not be assigned to this already-built frame.
        if (!enabled() || id == 0) return false;
        auto end = pending_.upper_bound(id);
        for (auto it = pending_.begin(); it != end;) {
            const auto sample = it->first;
            const auto times = it->second;
            if (sample < id) {
                row(sample, "RESULT", "", "NOT_RENDERED", "COALESCED_BEFORE_SYNC", frame);
            } else if (!exposed || !(times.t1 <= times.t2 && times.t2 <= times.t3 && times.t3 <= t4)) {
                row(sample, "RESULT", "", "INDETERMINATE", exposed ? "TIMESTAMP_ORDER" : "WINDOW_NOT_EXPOSED", frame);
            } else {
                row(sample, "T4", QString::number(t4), "FRAME_SWAPPED", "QT_SIGNAL_PROXY_ONLY", frame);
                ++completed_;
            }
            it = pending_.erase(it);
        }
        flush();
        return target_ > 0 && completed_ >= target_;
    }
    void finish() {
        for (const auto& item : pending_)
            row(item.first, "RESULT", "", "INDETERMINATE", "NO_MATCHING_SWAP_BEFORE_EXIT", 0);
        pending_.clear();
        flush();
    }
    ~LatencyRecorder() { finish(); }
private:
    void flush() { if (enabled() && !output_.flush()) healthy_ = false; }
    struct Times { std::uint64_t t1, t2, t3; };
    void write(const QByteArray& bytes) {
        if (output_.write(bytes) != bytes.size()) healthy_ = false;
    }
    void row(std::uint64_t id, const char* stage, const QString& time,
             const char* status, const char* reason, std::uint64_t frame) {
        write((run_ + ',' + boot_ + ',' + QString::number(id) + ',' + stage + ',' + time + ',' +
               status + ',' + reason + ',' + (frame ? QString::number(frame) : QString()) + '\n').toUtf8());
    }
    QFile output_;
    QString run_, boot_;
    std::map<std::uint64_t, Times> pending_;
    std::size_t target_, completed_ = 0;
    bool healthy_ = true;
};
