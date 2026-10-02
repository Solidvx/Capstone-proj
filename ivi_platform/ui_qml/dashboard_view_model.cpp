#include "dashboard_view_model.h"

#include <QMetaObject>
#include <QThread>

#include <chrono>

DashboardViewModel::DashboardViewModel(QObject* parent) : QObject(parent) {}

bool DashboardViewModel::valid() const { return snapshot_.vehicle.valid; }
bool DashboardViewModel::stale() const { return snapshot_.vehicle.stale; }
double DashboardViewModel::soc() const { return snapshot_.vehicle.soc_percent; }
QString DashboardViewModel::socBand() const {
    if (!measurementsAvailable()) {
        return QStringLiteral("unavailable");
    }
    if (snapshot_.vehicle.soc_percent < 20.0) {
        return QStringLiteral("low");
    }
    if (snapshot_.vehicle.soc_percent < 50.0) {
        return QStringLiteral("medium");
    }
    return QStringLiteral("high");
}
double DashboardViewModel::soh() const { return snapshot_.vehicle.soh_percent; }
double DashboardViewModel::voltage() const { return snapshot_.vehicle.voltage_v; }
double DashboardViewModel::current() const { return snapshot_.vehicle.current_a; }
double DashboardViewModel::temperature() const { return snapshot_.vehicle.temperature_c; }
bool DashboardViewModel::measurementsAvailable() const {
    const auto sensor_state = snapshot_.vehicle.sensor_state;
    return snapshot_.vehicle.valid && sensor_state != 1U && sensor_state != 3U &&
           sensor_state != 5U && sensor_state <= 6U;
}
QString DashboardViewModel::sensorState() const {
    return QString::fromLatin1(ivi::sensorStateName(snapshot_.vehicle.sensor_state));
}
bool DashboardViewModel::sensorStateWarning() const {
    return snapshot_.vehicle.sensor_state != 2U;
}
bool DashboardViewModel::sensorUsesLastGood() const {
    return snapshot_.vehicle.sensor_state == 4U || snapshot_.vehicle.sensor_state == 6U;
}
qulonglong DashboardViewModel::lastGoodAgeMs() const {
    return static_cast<qulonglong>(snapshot_.last_good_age_ms);
}

QString DashboardViewModel::failSafeState() const {
    return QString::fromLatin1(ivi::failSafeStateName(snapshot_.vehicle.fail_safe_state));
}

QString DashboardViewModel::failSafeReason() const {
    return QString::fromLatin1(ivi::failSafeReasonName(snapshot_.vehicle.fail_safe_reason));
}
bool DashboardViewModel::failSafeOverlayActive() const {
    return snapshot_.vehicle.fail_safe_state >= 2U;
}

bool DashboardViewModel::secocVerified() const { return snapshot_.last_secoc_verified; }
unsigned int DashboardViewModel::secocFailureCount() const {
    return snapshot_.secoc_failure_count;
}
bool DashboardViewModel::securityAlertActive() const {
    return snapshot_.security_alert.has_value();
}
QString DashboardViewModel::attackType() const {
    return snapshot_.security_alert.has_value()
               ? QString::fromLatin1(ivi::attackTypeName(snapshot_.security_alert->attack_type))
               : QStringLiteral("None");
}
double DashboardViewModel::anomalyScore() const {
    return snapshot_.security_alert.has_value() ? snapshot_.security_alert->anomaly_score : 0.0;
}
QString DashboardViewModel::lastMessage() const {
    return QString::fromStdString(snapshot_.last_message);
}
QStringList DashboardViewModel::logs() const {
    QStringList output;
    for (const auto& line : snapshot_.logs) {
        output.push_back(QString::fromStdString(line));
    }
    return output;
}

void DashboardViewModel::updateSnapshot(const ivi::VehicleSnapshot& snapshot) {
    if (QThread::currentThread() != thread()) {
        QMetaObject::invokeMethod(
            this, [this, snapshot]() { updateSnapshot(snapshot); }, Qt::QueuedConnection);
        return;
    }
    snapshot_ = snapshot;
    emit dataChanged();
    if (snapshot.measurement_sequence != 0U &&
        snapshot.measurement_sequence != last_measurement_sequence_) {
        last_measurement_sequence_ = snapshot.measurement_sequence;
        const auto now = std::chrono::steady_clock::now();
        const auto t3_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
                               now.time_since_epoch())
                               .count();
        emit measurementReady(static_cast<qulonglong>(snapshot.measurement_sequence),
                              static_cast<qulonglong>(snapshot.t1_received_ns),
                              static_cast<qulonglong>(snapshot.t2_published_ns),
                              static_cast<qulonglong>(t3_ns));
    }
}

void DashboardViewModel::acknowledgeSecurityAlert() {
    if (snapshot_.security_alert.has_value()) {
        emit securityAlertAcknowledgementRequested(
            static_cast<qulonglong>(snapshot_.security_alert_sequence));
    }
}
