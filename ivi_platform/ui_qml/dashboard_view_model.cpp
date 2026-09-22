#include "dashboard_view_model.h"

#include <QMetaObject>
#include <QThread>

DashboardViewModel::DashboardViewModel(QObject* parent) : QObject(parent) {}

bool DashboardViewModel::valid() const { return snapshot_.vehicle.valid; }
bool DashboardViewModel::stale() const { return snapshot_.vehicle.stale; }
double DashboardViewModel::soc() const { return snapshot_.vehicle.soc_percent; }
double DashboardViewModel::soh() const { return snapshot_.vehicle.soh_percent; }
double DashboardViewModel::voltage() const { return snapshot_.vehicle.voltage_v; }
double DashboardViewModel::current() const { return snapshot_.vehicle.current_a; }
double DashboardViewModel::temperature() const { return snapshot_.vehicle.temperature_c; }

QString DashboardViewModel::failSafeState() const {
    return QString::fromLatin1(ivi::failSafeStateName(snapshot_.vehicle.fail_safe_state));
}

QString DashboardViewModel::failSafeReason() const {
    return QString::fromLatin1(ivi::failSafeReasonName(snapshot_.vehicle.fail_safe_reason));
}

bool DashboardViewModel::authenticationError() const {
    return snapshot_.consecutive_secoc_failure_count >= 10U;
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
}
