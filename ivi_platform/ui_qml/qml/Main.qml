pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ApplicationWindow {
    id: root
    required property var vehicleModel
    width: 1100
    height: 720
    visible: true
    title: "Node B IVI"
    color: "#101318"

    readonly property color green: "#36d399"
    readonly property color orange: "#f59e0b"
    readonly property color red: "#fb7185"
    readonly property color panel: "#1b2029"
    readonly property color muted: "#9aa4b2"
    readonly property bool portraitPanel: height > width

    function socColor(band) {
        if (band === "low") return red
        if (band === "medium") return orange
        if (band === "high") return green
        return muted
    }

    function ageText(milliseconds) {
        if (milliseconds < 1000) return milliseconds + " ms"
        return (milliseconds / 1000).toFixed(1) + " s"
    }

    Item {
        id: landscapeScene
        objectName: "landscapeScene"
        anchors.centerIn: parent
        width: root.portraitPanel ? root.height : root.width
        height: root.portraitPanel ? root.width : root.height
        rotation: root.portraitPanel ? -90 : 0

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 14

        RowLayout {
            Layout.fillWidth: true
            Text {
                text: "Qt Quick IVI Dashboard"
                color: "white"
                font.pixelSize: 30
                font.bold: true
            }
            Item { Layout.fillWidth: true }
            Label {
                text: root.vehicleModel.valid ? (root.vehicleModel.stale ? "STALE" : "LIVE") : "WAITING"
                color: root.vehicleModel.valid && !root.vehicleModel.stale ? root.green : root.orange
                font.pixelSize: 18
                font.bold: true
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: root.vehicleModel.securityAlertActive ? 68 : 0
            visible: root.vehicleModel.securityAlertActive
            color: "#501923"
            border.color: root.red
            radius: 6
            RowLayout {
                anchors.fill: parent
                anchors.margins: 14
                Text {
                    text: "⚠ " + root.vehicleModel.attackType + " Attack Detected"
                    color: "white"
                    font.pixelSize: 20
                    font.bold: true
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: "score " + root.vehicleModel.anomalyScore.toFixed(2)
                    color: "#fecdd3"
                }
                Button {
                    id: acknowledgeButton
                    text: "Acknowledge"
                    onClicked: root.vehicleModel.acknowledgeSecurityAlert()
                    contentItem: Text {
                        text: acknowledgeButton.text
                        color: "white"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        color: "#7f1d1d"
                        border.color: root.red
                        radius: 4
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: visible ? 54 : 0
            visible: root.vehicleModel.valid &&
                     (root.vehicleModel.stale || root.vehicleModel.sensorStateWarning)
            color: root.vehicleModel.stale ? "#4a3210" : "#273244"
            border.color: root.vehicleModel.stale ? root.orange : "#64748b"
            radius: 6
            RowLayout {
                anchors.fill: parent
                anchors.margins: 12
                Text {
                    text: root.vehicleModel.stale
                          ? "Last authenticated BMS data is stale"
                          : "Sensor state: " + root.vehicleModel.sensorState
                    color: "white"
                    font.bold: true
                }
                Item { Layout.fillWidth: true }
                Text {
                    visible: root.vehicleModel.valid
                    text: "last good " + root.ageText(root.vehicleModel.lastGoodAgeMs) + " ago"
                    color: "#cbd5e1"
                }
            }
        }

        Label {
            objectName: "authenticationErrorIndicator"
            Layout.fillWidth: true
            visible: root.vehicleModel.authenticationError
            text: "인증 오류 — 마지막 정상값을 유지합니다"
            color: root.red
            font.bold: true
            font.pixelSize: 22
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 3
            columnSpacing: 14
            rowSpacing: 14

            MetricCard {
                title: "SOC"
                value: root.vehicleModel.measurementsAvailable ? root.vehicleModel.soc.toFixed(1) : "--"
                unit: "%"
                valueColor: root.socColor(root.vehicleModel.socBand)
            }
            MetricCard {
                title: "SOH"
                value: root.vehicleModel.measurementsAvailable ? root.vehicleModel.soh.toFixed(1) : "--"
                unit: "%"
            }
            MetricCard {
                title: "Voltage"
                value: root.vehicleModel.measurementsAvailable ? root.vehicleModel.voltage.toFixed(2) : "--"
                unit: "V"
            }
            MetricCard {
                title: "Current"
                value: root.vehicleModel.measurementsAvailable ? root.vehicleModel.current.toFixed(1) : "--"
                unit: "A"
            }
            MetricCard {
                title: "Temperature"
                value: root.vehicleModel.measurementsAvailable ? root.vehicleModel.temperature.toFixed(0) : "--"
                unit: "°C"
            }
            MetricCard {
                title: "Fail-safe"
                value: root.vehicleModel.failSafeState
                unit: root.vehicleModel.failSafeReason
                valueColor: root.vehicleModel.failSafeState === "NORMAL" ? root.green
                            : root.vehicleModel.failSafeState === "WARNING" ? root.orange : root.red
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: root.panel
            radius: 8
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                RowLayout {
                    Layout.fillWidth: true
                    Text {
                        text: root.vehicleModel.secocVerified
                              ? "SecOC VERIFIED" : "SecOC WAITING/REJECTED"
                        color: root.vehicleModel.secocVerified ? root.green : root.orange
                        font.bold: true
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: "failures " + root.vehicleModel.secocFailureCount
                        color: root.muted
                    }
                }
                Text {
                    text: root.vehicleModel.lastMessage
                    color: "#cbd5e1"
                    wrapMode: Text.Wrap
                    Layout.fillWidth: true
                }
                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: root.vehicleModel.logs
                    clip: true
                    delegate: Text {
                        required property string modelData
                        text: modelData
                        color: root.muted
                    }
                }
            }
        }
    }

        Rectangle {
            anchors.fill: parent
            visible: root.vehicleModel.failSafeOverlayActive
            color: "#e6101118"
            border.color: root.red
            border.width: 8
            z: 1000

            ColumnLayout {
                anchors.centerIn: parent
                width: Math.min(parent.width - 120, 760)
                spacing: 20
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: root.vehicleModel.failSafeState
                color: "white"
                font.pixelSize: 58
                font.bold: true
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "FAIL-SAFE ACTIVE"
                color: root.red
                font.pixelSize: 30
                font.bold: true
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: root.vehicleModel.failSafeReason
                color: "white"
                font.pixelSize: 22
                wrapMode: Text.Wrap
                horizontalAlignment: Text.AlignHCenter
            }
            Text {
                Layout.alignment: Qt.AlignHCenter
                text: "The warning remains until an authenticated ECU state transition is received."
                color: "#fecdd3"
                font.pixelSize: 16
                wrapMode: Text.Wrap
                horizontalAlignment: Text.AlignHCenter
            }
            }
        }
    }

    component MetricCard: Rectangle {
        id: card
        property string title
        property string value
        property string unit
        property color valueColor: "white"
        Layout.fillWidth: true
        Layout.preferredHeight: 120
        color: root.panel
        radius: 8
        opacity: root.vehicleModel.stale || root.vehicleModel.sensorUsesLastGood ? 0.72 : 1.0
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            Text { text: card.title; color: root.muted }
            RowLayout {
                Text {
                    text: card.value
                    color: card.valueColor
                    font.pixelSize: 30
                    font.bold: true
                }
                Text {
                    text: card.unit
                    color: root.muted
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }
        }
    }
}
