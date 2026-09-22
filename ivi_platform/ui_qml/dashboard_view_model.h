#pragma once

#include <QObject>
#include <QString>
#include <QStringList>

#include "vehicle_data_service.h"

class DashboardViewModel : public QObject {
    Q_OBJECT
    Q_PROPERTY(bool valid READ valid NOTIFY dataChanged)
    Q_PROPERTY(bool stale READ stale NOTIFY dataChanged)
    Q_PROPERTY(double soc READ soc NOTIFY dataChanged)
    Q_PROPERTY(double soh READ soh NOTIFY dataChanged)
    Q_PROPERTY(double voltage READ voltage NOTIFY dataChanged)
    Q_PROPERTY(double current READ current NOTIFY dataChanged)
    Q_PROPERTY(double temperature READ temperature NOTIFY dataChanged)
    Q_PROPERTY(QString failSafeState READ failSafeState NOTIFY dataChanged)
    Q_PROPERTY(QString failSafeReason READ failSafeReason NOTIFY dataChanged)
    Q_PROPERTY(bool secocVerified READ secocVerified NOTIFY dataChanged)
    Q_PROPERTY(unsigned int secocFailureCount READ secocFailureCount NOTIFY dataChanged)
    Q_PROPERTY(bool securityAlertActive READ securityAlertActive NOTIFY dataChanged)
    Q_PROPERTY(QString attackType READ attackType NOTIFY dataChanged)
    Q_PROPERTY(double anomalyScore READ anomalyScore NOTIFY dataChanged)
    Q_PROPERTY(QString lastMessage READ lastMessage NOTIFY dataChanged)
    Q_PROPERTY(QStringList logs READ logs NOTIFY dataChanged)

public:
    explicit DashboardViewModel(QObject* parent = nullptr);

    bool valid() const;
    bool stale() const;
    double soc() const;
    double soh() const;
    double voltage() const;
    double current() const;
    double temperature() const;
    QString failSafeState() const;
    QString failSafeReason() const;
    bool secocVerified() const;
    unsigned int secocFailureCount() const;
    bool securityAlertActive() const;
    QString attackType() const;
    double anomalyScore() const;
    QString lastMessage() const;
    QStringList logs() const;

public slots:
    void updateSnapshot(const ivi::VehicleSnapshot& snapshot);

signals:
    void dataChanged();

private:
    ivi::VehicleSnapshot snapshot_;
};
