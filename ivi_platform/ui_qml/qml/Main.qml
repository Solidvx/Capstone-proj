import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: root
    width: 1100
    height: 680
    visible: true
    title: "Node B IVI"
    color: "#101318"

    readonly property color green: "#36d399"
    readonly property color orange: "#f59e0b"
    readonly property color red: "#fb7185"
    readonly property color panel: "#1b2029"

    function socColor(value) {
        if (value < 20) return red
        if (value < 50) return orange
        return green
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

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
                text: vehicleModel.valid ? (vehicleModel.stale ? "STALE" : "LIVE") : "WAITING"
                color: vehicleModel.valid && !vehicleModel.stale ? root.green : root.orange
                font.pixelSize: 18
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: vehicleModel.securityAlertActive ? 64 : 0
            visible: vehicleModel.securityAlertActive
            color: "#501923"
            border.color: root.red
            radius: 6
            RowLayout {
                anchors.fill: parent
                anchors.margins: 16
                Text {
                    text: "⚠ " + vehicleModel.attackType + " Attack Detected"
                    color: "white"
                    font.pixelSize: 20
                    font.bold: true
                }
                Item { Layout.fillWidth: true }
                Text {
                    text: "score " + vehicleModel.anomalyScore.toFixed(2)
                    color: "#fecdd3"
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 3
            columnSpacing: 16
            rowSpacing: 16

            MetricCard {
                title: "SOC"
                value: vehicleModel.valid ? vehicleModel.soc.toFixed(1) : "--"
                unit: "%"
                valueColor: vehicleModel.valid ? root.socColor(vehicleModel.soc) : "#9aa4b2"
            }
            MetricCard { title: "SOH"; value: vehicleModel.valid ? vehicleModel.soh.toFixed(1) : "--"; unit: "%" }
            MetricCard { title: "Voltage"; value: vehicleModel.valid ? vehicleModel.voltage.toFixed(2) : "--"; unit: "V" }
            MetricCard { title: "Current"; value: vehicleModel.valid ? vehicleModel.current.toFixed(1) : "--"; unit: "A" }
            MetricCard { title: "Temperature"; value: vehicleModel.valid ? vehicleModel.temperature.toFixed(0) : "--"; unit: "°C" }
            MetricCard { title: "Fail-safe"; value: vehicleModel.failSafeState; unit: vehicleModel.failSafeReason }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: panel
            radius: 8
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 16
                Text {
                    text: vehicleModel.secocVerified ? "SecOC VERIFIED" : "SecOC WAITING/REJECTED"
                    color: vehicleModel.secocVerified ? root.green : root.orange
                    font.bold: true
                }
                Text { text: vehicleModel.lastMessage; color: "#cbd5e1" }
                ListView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    model: vehicleModel.logs
                    clip: true
                    delegate: Text { text: modelData; color: "#94a3b8" }
                }
            }
        }
    }

    component MetricCard: Rectangle {
        property string title
        property string value
        property string unit
        property color valueColor: "white"
        Layout.fillWidth: true
        Layout.preferredHeight: 130
        color: root.panel
        radius: 8
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            Text { text: title; color: "#9aa4b2" }
            RowLayout {
                Text { text: value; color: valueColor; font.pixelSize: 30; font.bold: true }
                Text { text: unit; color: "#9aa4b2" }
            }
        }
    }
}
