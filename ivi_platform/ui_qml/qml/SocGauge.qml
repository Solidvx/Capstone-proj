import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    required property real value
    required property bool available
    required property bool stale
    property bool showLabel: true
    property color highColor: "#36d399"
    property color mediumColor: "#f59e0b"
    property color lowColor: "#fb7185"
    property color mutedColor: "#9aa4b2"
    property color textColor: "white"
    property color trackColor: "#374151"
    property color panelColor: "#1b2029"

    readonly property real clampedValue: Math.max(0, Math.min(100, value))
    readonly property color gaugeColor: !available ? mutedColor
                                               : clampedValue >= 50 ? highColor
                                               : clampedValue >= 20 ? mediumColor
                                                                    : lowColor

    implicitWidth: 220
    implicitHeight: 140
    color: panelColor
    radius: 8
    opacity: stale ? 0.72 : 1.0

    onClampedValueChanged: gaugeArc.requestPaint()
    onGaugeColorChanged: gaugeArc.requestPaint()
    onAvailableChanged: gaugeArc.requestPaint()
    onTrackColorChanged: gaugeArc.requestPaint()

    Text {
        objectName: "socGaugeLabel"
        visible: root.showLabel
        font.pixelSize: 12
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 8
        text: "배터리 잔량(SOC)"
        color: root.mutedColor
    }

    Item {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: root.showLabel ? 13 : 0
        width: Math.min(parent.width - 24, parent.height - (root.showLabel ? 48 : 24))
        height: width

        Canvas {
            id: gaugeArc
            objectName: "socGaugeArc"
            anchors.fill: parent

            onPaint: {
                const context = getContext("2d")
                const center = width / 2
                const radius = Math.max(0, center - 8)
                const start = -Math.PI / 2
                const end = start + Math.PI * 2
                context.clearRect(0, 0, width, height)
                context.lineWidth = 10
                context.lineCap = "round"
                context.strokeStyle = root.trackColor
                context.beginPath()
                context.arc(center, center, radius, start, end, false)
                context.stroke()
                if (root.available && root.clampedValue > 0) {
                    context.strokeStyle = root.gaugeColor
                    context.beginPath()
                    context.arc(center, center, radius, start,
                                start + Math.PI * 2 * root.clampedValue / 100, false)
                    context.stroke()
                }
            }
        }

        Text {
            objectName: "socGaugeValue"
            anchors.centerIn: parent
            width: Math.max(1, parent.width - 28)
            text: root.available ? root.clampedValue.toFixed(1) + "%" : "--"
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.NoWrap
            color: root.gaugeColor
            font.pixelSize: 27
            font.bold: true
            minimumPixelSize: 18
            fontSizeMode: Text.Fit
        }
    }
}
