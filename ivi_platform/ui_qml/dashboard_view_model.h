#pragma once

#include <QObject>
#include <QString>
#include <QStringList>
#include <QSet>
#include <QJsonObject>

#include "vehicle_data_service.h"

class DashboardViewModel : public QObject {
    Q_OBJECT
    Q_PROPERTY(bool valid READ valid NOTIFY dataChanged)
    Q_PROPERTY(bool stale READ stale NOTIFY dataChanged)
    Q_PROPERTY(bool sessionProtocol READ sessionProtocol NOTIFY dataChanged)
    Q_PROPERTY(QString connectionLabel READ connectionLabel NOTIFY dataChanged)
    Q_PROPERTY(double soc READ soc NOTIFY dataChanged)
    Q_PROPERTY(QString socBand READ socBand NOTIFY dataChanged)
    Q_PROPERTY(double soh READ soh NOTIFY dataChanged)
    Q_PROPERTY(double voltage READ voltage NOTIFY dataChanged)
    Q_PROPERTY(double current READ current NOTIFY dataChanged)
    Q_PROPERTY(double temperature READ temperature NOTIFY dataChanged)
    Q_PROPERTY(bool measurementsAvailable READ measurementsAvailable NOTIFY dataChanged)
    Q_PROPERTY(QString sensorState READ sensorState NOTIFY dataChanged)
    Q_PROPERTY(bool sensorStateWarning READ sensorStateWarning NOTIFY dataChanged)
    Q_PROPERTY(bool sensorUsesLastGood READ sensorUsesLastGood NOTIFY dataChanged)
    Q_PROPERTY(qulonglong lastGoodAgeMs READ lastGoodAgeMs NOTIFY dataChanged)
    Q_PROPERTY(QString failSafeState READ failSafeState NOTIFY dataChanged)
    Q_PROPERTY(QString failSafeReason READ failSafeReason NOTIFY dataChanged)
    Q_PROPERTY(bool authenticationError READ authenticationError NOTIFY dataChanged)
    Q_PROPERTY(bool failSafeOverlayActive READ failSafeOverlayActive NOTIFY dataChanged)
    Q_PROPERTY(bool secocVerified READ secocVerified NOTIFY dataChanged)
    Q_PROPERTY(unsigned int secocFailureCount READ secocFailureCount NOTIFY dataChanged)
    Q_PROPERTY(bool securityAlertActive READ securityAlertActive NOTIFY dataChanged)
    Q_PROPERTY(QString attackType READ attackType NOTIFY dataChanged)
    Q_PROPERTY(double anomalyScore READ anomalyScore NOTIFY dataChanged)
    Q_PROPERTY(QString lastMessage READ lastMessage NOTIFY dataChanged)
    Q_PROPERTY(QStringList logs READ logs NOTIFY dataChanged)

    Q_PROPERTY(bool darkMode READ darkMode WRITE setDarkMode NOTIFY themeChanged)
    Q_PROPERTY(QString statusTitle READ statusTitle NOTIFY dataChanged)
    Q_PROPERTY(QString statusDescription READ statusDescription NOTIFY dataChanged)
    Q_PROPERTY(bool failSafeKnown READ failSafeKnown NOTIFY dataChanged)
    Q_PROPERTY(QString securityTitle READ securityTitle NOTIFY dataChanged)
    Q_PROPERTY(QString securityDescription READ securityDescription NOTIFY dataChanged)
    Q_PROPERTY(QStringList floodingMetrics READ floodingMetrics NOTIFY dataChanged)
    Q_PROPERTY(QStringList incidentTreatments READ incidentTreatments NOTIFY dataChanged)
    Q_PROPERTY(QString rejectionSummary READ rejectionSummary NOTIFY dataChanged)
    Q_PROPERTY(QString historyStorageStatus READ historyStorageStatus NOTIFY dataChanged)
    Q_PROPERTY(QStringList eventHistory READ eventHistory NOTIFY dataChanged)
    Q_PROPERTY(QStringList recentEvents READ recentEvents NOTIFY dataChanged)
    Q_PROPERTY(bool popupVisible READ popupVisible NOTIFY popupChanged)
    Q_PROPERTY(QString popupTitle READ popupTitle NOTIFY popupChanged)
    Q_PROPERTY(QString popupDescription READ popupDescription NOTIFY popupChanged)
    Q_PROPERTY(QString popupKind READ popupKind NOTIFY popupChanged)

public:
    explicit DashboardViewModel(QObject* parent = nullptr);
    QStringList floodingMetrics() const;
    QStringList incidentTreatments() const;

    bool darkMode() const { return dark_mode_; }
    void setDarkMode(bool value);
    bool failSafeKnown() const { return fail_safe_known_; }
    QString statusTitle() const;
    QString statusDescription() const;
    QString securityTitle() const;
    QString securityDescription() const;
    QString rejectionSummary() const { return rejection_summary_; }
    QString historyStorageStatus() const { return history_storage_status_; }
    void restoreEventHistory(const QStringList& history);
    void expectProtectionHistory();
    void restoreProtectionHistory(const QJsonObject& record,bool gap_possible);
    void protectionCommitted(const QJsonObject& record);
    void setHistoryStorageStatus(const QString& message);
    QStringList eventHistory() const { return events_; }
    QStringList recentEvents() const {
        auto recent=events_.mid(0,2);
        for(auto& line:recent)if(line.size()>11&&line[4]==QChar('-')&&line[7]==QChar('-')&&line[10]==QChar(' '))line.remove(0,11);
        return recent;
    }
    bool popupVisible() const { return popup_visible_; }
    QString popupTitle() const { return popup_title_; }
    QString popupDescription() const { return popup_description_; }
    QString popupKind() const { return popup_kind_; }
    Q_INVOKABLE void dismissPopup();
    bool valid() const;
    bool sessionProtocol()const{return snapshot_.session_protocol;}
    QString connectionLabel()const;
    bool stale() const;
    double soc() const;
    QString socBand() const;
    double soh() const;
    double voltage() const;
    double current() const;
    double temperature() const;
    bool measurementsAvailable() const;
    QString sensorState() const;
    bool sensorStateWarning() const;
    bool sensorUsesLastGood() const;
    qulonglong lastGoodAgeMs() const;
    QString failSafeState() const;
    QString failSafeReason() const;
    bool authenticationError() const;
    bool failSafeOverlayActive() const;
    bool secocVerified() const;
    unsigned int secocFailureCount() const;
    bool securityAlertActive() const;
    QString attackType() const;
    double anomalyScore() const;
    QString lastMessage() const;
    QStringList logs() const;

public slots:
    void updateSnapshot(const ivi::VehicleSnapshot& snapshot);
    Q_INVOKABLE void acknowledgeSecurityAlert();

signals:
    void eventRecorded(const QJsonObject& event);
    void themeChanged();
    void popupChanged();
    void dataChanged();
    void measurementReady(qulonglong sequence,
                          qulonglong t1ReceivedNs,
                          qulonglong t2PublishedNs,
                          qulonglong t3ViewModelNs);
    void securityAlertAcknowledgementRequested(qulonglong sequence);

private:
    void recordProtectionUpdate();
    QJsonObject protectionLink(const QJsonObject& current)const;
    void recordEvent(const QString& text,const QString& category=QStringLiteral("event"));
    enum class PopupDomain { General, Battery, Security, Storage };
    void presentPopup(const QString& title, const QString& description, const QString& kind, int priority,PopupDomain domain=PopupDomain::General);
    bool dark_mode_ = true;
    bool fail_safe_known_ = false;
    bool popup_visible_ = false;
    int popup_priority_ = 0;
    PopupDomain popup_domain_=PopupDomain::General;
    std::uint8_t popup_battery_state_=0;
    QString popup_title_, popup_description_, popup_kind_;
    QString security_title_ = QStringLiteral("새 보안 알림 없음");
    QString security_description_ = QStringLiteral("새로운 탐지 보고가 없습니다.");
    QString rejection_summary_ = QStringLiteral("수신 메시지 거부 기록 없음");
    QString last_rejection_;
    QStringList events_;
    bool history_loaded_=false;
    bool protection_history_ready_=true,protection_history_gap_=false;
    bool protection_was_confirmed_=false,protection_observation_gap_=false;
    QJsonObject committed_protection_record_;
    QString protection_notice_signature_;
    QString event_source_instance_;
    QString history_storage_status_=QStringLiteral("기록은 이번 실행 동안만 유지됩니다");
    QSet<int> active_attack_types_;
    ivi::VehicleSnapshot snapshot_;
    std::uint64_t last_measurement_sequence_ = 0;
};
