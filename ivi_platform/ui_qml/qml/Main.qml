pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ApplicationWindow {
    id: root
    required property var vehicleModel
    width: 800
    height: 480
    visible: true
    title: "배터리 모니터"
    color: backgroundColor
    readonly property bool dark: vehicleModel.darkMode
    readonly property color backgroundColor: dark ? "#101722" : "#f4f6fa"
    readonly property color panel: dark ? "#182231" : "#ffffff"
    readonly property color ink: dark ? "#edf3ff" : "#172134"
    readonly property color muted: dark ? "#a0b0c8" : "#66738a"
    readonly property color lineColor: dark ? "#2c3a50" : "#e5eaf2"
    readonly property color green: dark ? "#36d399" : "#087f62"
    readonly property color orange: dark ? "#ffcb77" : "#a36007"
    readonly property color red: dark ? "#ff9aab" : "#c1374d"
    readonly property color blue: dark ? "#8ab4ff" : "#326cdb"
    readonly property bool portraitPanel: height > width
    property int currentPage: 0
    readonly property bool batteryPopupVisible: currentPage === 0 && vehicleModel.popupVisible
    property bool toastVisible: false
    function updateNotification() {
        toastVisible = currentPage !== 0 && vehicleModel.popupVisible
        if (toastVisible) toastTimer.restart()
        else toastTimer.stop()
    }
    onCurrentPageChanged: updateNotification()
    Connections {
        target: root.vehicleModel
        function onPopupChanged() { root.updateNotification() }
    }
    Timer {
        id: toastTimer
        objectName: "notificationTimer"
        interval: 6000
        onTriggered: {
            root.toastVisible = false
            if (root.currentPage !== 0) root.vehicleModel.dismissPopup()
        }
    }
    readonly property var pageNames: ["배터리", "보안", "이벤트", "설정"]
    function ageText(ms) { return ms < 1000 ? ms + " ms" : (ms / 1000).toFixed(1) + "초" }

    Item {
        id: landscapeScene
        objectName: "landscapeScene"
        anchors.centerIn: parent
        width: root.portraitPanel ? root.height : root.width
        height: root.portraitPanel ? root.width : root.height
        rotation: root.portraitPanel ? -90 : 0
        Item {
            id: canvas
            objectName: "appCanvas"
            width: 800; height: 480
            anchors.centerIn: parent
            scale: Math.min(landscapeScene.width / width, landscapeScene.height / height)
            clip: true
            Rectangle {
                anchors.fill: parent
                color: "transparent"
                border.width: root.vehicleModel.failSafeOverlayActive ? 3 : 0
                border.color: root.red
                z: 1
            }
            ColumnLayout {
                id: shell
                anchors.fill: parent
                anchors.margins: 12
                spacing: 8
                enabled: !root.batteryPopupVisible
                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 32; Layout.minimumHeight: 32; Layout.maximumHeight: 32
                    Text {
                        text: root.currentPage === 0 ? "배터리 현황" : root.pageNames[root.currentPage]
                        color: root.ink; font.pixelSize: 20; font.bold: true
                    }
                    Item { Layout.fillWidth: true }
                    Text {
                        text: root.vehicleModel.sessionProtocol ? root.vehicleModel.connectionLabel : !root.vehicleModel.valid ? "연결 대기" : root.vehicleModel.stale ? "마지막 확인값 · " + root.ageText(root.vehicleModel.lastGoodAgeMs) : "현재 수신값"
                        color: root.vehicleModel.stale ? root.orange : root.muted
                        font.pixelSize: 12
                    }
                }
                StackLayout {
                    id: pages
                    objectName: "appPages"
                    Layout.fillWidth: true; Layout.fillHeight: true
                    Layout.minimumHeight: 0
                    currentIndex: root.currentPage
                    // This page has a fixed allocation, not a Flickable/outer ScrollView.
                    ColumnLayout {
                        id: overview
                        objectName: "batteryOverview"
                        spacing: 8
                        RowLayout {
                            Layout.fillWidth: true; Layout.fillHeight: true
                            spacing: 10
                            ColumnLayout {
                                Layout.fillWidth: true; Layout.preferredWidth: 440
                                Layout.fillHeight: true
                                spacing: 8
                                Card {
                                    objectName: "batterySummaryCard"
                                    Layout.fillWidth: true; Layout.fillHeight: true
                                    Layout.minimumHeight: 170
                                    RowLayout {
                                        anchors.fill: parent; anchors.margins: 10
                                        SocGauge {
                                            objectName: "socGauge"
                                            Layout.preferredWidth: 190; Layout.fillHeight: true
                                            value: root.vehicleModel.soc
                                            available: root.vehicleModel.socAvailable
                                            stale: root.vehicleModel.stale || root.vehicleModel.sensorUsesLastGood
                                            highColor: root.green; mediumColor: root.orange; lowColor: root.red
                                            mutedColor: root.muted; panelColor: root.panel
                                            textColor: root.ink; trackColor: root.lineColor
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            Text {
                                                Layout.fillWidth: true
                                                text: !root.vehicleModel.socAvailable ? (root.vehicleModel.physicalMode ? "잔량 추정 준비 중" : "배터리 정보 대기") : root.vehicleModel.physicalMode ? (root.vehicleModel.physicalObservationGap ? "측정 공백이 있는 잔량 추정" : "배터리 잔량 추정 중") : root.vehicleModel.soc < 20 ? "충전이 필요합니다" : "잔량이 충분합니다"
                                                color: root.ink; font.pixelSize: 18; font.bold: true
                                                wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                                            }
                                            Text {
                                                Layout.fillWidth: true
                                                text: root.vehicleModel.physicalMode ? (root.vehicleModel.sohAvailable ? "배터리 건강도(SOH) · 용량 시험값 기준" : "배터리 건강도(SOH) · 용량 측정 전") : root.vehicleModel.stale || root.vehicleModel.sensorUsesLastGood ? "마지막으로 확인한 값입니다." : "배터리 건강도(SOH)"
                                                color: root.muted; font.pixelSize: 12
                                                wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                                            }
                                            Text {
                                                objectName: "sohValue"
                                                text: root.vehicleModel.sohAvailable ? root.vehicleModel.soh.toFixed(1) + "%" : "--"
                                                color: root.ink; font.pixelSize: 30; font.bold: true
                                            }
                                            Text { text: "배터리 건강도(SOH)"; visible: root.vehicleModel.stale || root.vehicleModel.sensorUsesLastGood; color: root.muted; font.pixelSize: 12 }
                                        }
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true; Layout.preferredHeight: 62; Layout.minimumHeight: 62; Layout.maximumHeight: 62
                                    spacing: 8
                                    Metric { objectName: "voltageMetric"; title: root.vehicleModel.physicalMode ? "셀 전압" : "팩 전압"; value: root.vehicleModel.voltageAvailable ? root.vehicleModel.voltage.toFixed(root.vehicleModel.physicalMode ? 3 : 2) + " V" : "--" }
                                    Metric { objectName: "currentMetric"; title: "전류"; value: root.vehicleModel.currentAvailable ? root.vehicleModel.current.toFixed(root.vehicleModel.physicalMode ? 3 : 1) + " A" : "--" }
                                    Metric { objectName: "temperatureMetric"; title: "온도"; value: root.vehicleModel.temperatureAvailable ? root.vehicleModel.temperature.toFixed(root.vehicleModel.physicalMode ? 1 : 0) + " °C" : "--" }
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true; Layout.preferredWidth: 310
                                Layout.fillHeight: true; spacing: 8
                                Card {
                                    objectName: "systemStatusCard"
                                    Layout.fillWidth: true; Layout.fillHeight: true
                                    border.color: root.vehicleModel.failSafeOverlayActive ? root.red : root.vehicleModel.failSafeState === "WARNING" ? root.orange : root.lineColor
                                    ColumnLayout {
                                        anchors.fill: parent; anchors.margins: 12; spacing: 5
                                        Text { text: "시스템 상태"; color: root.muted; font.pixelSize: 12 }
                                        Text {
                                            objectName: "statusTitle"
                                            Layout.fillWidth: true
                                            text: root.vehicleModel.statusTitle
                                            color: root.vehicleModel.failSafeOverlayActive ? root.red : root.vehicleModel.failSafeState === "WARNING" ? root.orange : root.ink
                                            font.pixelSize: 18; font.bold: true; elide: Text.ElideRight
                                        }
                                        Text {
                                            Layout.fillWidth: true
                                            text: root.vehicleModel.statusDescription
                                            color: root.muted; font.pixelSize: 12
                                            wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                                        }
                                        Item { Layout.fillHeight: true }
                                    }
                                }
                                Card {
                                    Layout.fillWidth: true; Layout.fillHeight: true
                                    ColumnLayout {
                                        anchors.fill: parent; anchors.margins: 12; spacing: 5
                                        Text { text: "보안 탐지 결과"; color: root.muted; font.pixelSize: 12 }
                                        Text {
                                            objectName: "securityTitle"
                                            Layout.fillWidth: true
                                            text: root.vehicleModel.securityTitle
                                            color: root.ink; font.pixelSize: 17; font.bold: true
                                            wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                                        }
                                        Text { Layout.fillWidth: true; text: root.vehicleModel.secocFailureCount + "건 수신 검증 실패"; color: root.muted; font.pixelSize: 12 }
                                        AppButton { text: "보안 내역 보기"; Layout.preferredHeight: 32; onClicked: root.currentPage = 1 }
                                    }
                                }
                            }
                        }
                        Card {
                            id: recentCard
                            objectName: "recentEventsCard"
                            Layout.fillWidth: true; Layout.preferredHeight: 86
                            ColumnLayout {
                                anchors.fill: parent; anchors.margins: 10; spacing: 3
                                RowLayout {
                                    Layout.fillWidth: true
                                    Text { text: "최근 이벤트"; color: root.ink; font.pixelSize: 13; font.bold: true }
                                    Item { Layout.fillWidth: true }
                                    AppButton { text: "전체 보기"; Layout.preferredHeight: 26; Layout.minimumHeight: 26; Layout.maximumHeight: 26; onClicked: root.currentPage = 2 }
                                }
                                Repeater {
                                    model: root.vehicleModel.recentEvents
                                    Text { required property string modelData; Layout.fillWidth: true; text: modelData; color: root.muted; font.pixelSize: 12; elide: Text.ElideRight }
                                }
                                Text { visible: root.vehicleModel.recentEvents.length === 0; text: "아직 기록된 이벤트가 없습니다."; color: root.muted; font.pixelSize: 12 }
                                Item { Layout.fillHeight: true }
                            }
                        }
                    }
                    ScrollView {
                        objectName: "securityScroll"
                        clip: true; contentWidth: availableWidth
                        ColumnLayout {
                            width: parent.width
                            spacing: 14
                            Text { text: root.vehicleModel.securityTitle; color: root.ink; font.pixelSize: 23; font.bold: true; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            Text { text: root.vehicleModel.securityDescription; color: root.muted; font.pixelSize: 15; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            Text { text: "수신 검증 결과"; color: root.ink; font.pixelSize: 17; font.bold: true }
                            Text { text: "통신 상태 · Flooding 관찰"; color: root.muted; font.pixelSize: 18; font.bold: true }
                            Repeater {
                                model: root.vehicleModel.floodingMetrics
                                Text { required property string modelData; text: modelData; color: root.muted; font.pixelSize: 14; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            }
                            Repeater { model: root.vehicleModel.incidentTreatments; Text { required property string modelData; text: modelData; color: root.ink; font.pixelSize: 14; Layout.fillWidth: true; wrapMode: Text.Wrap } }
                            Text { objectName: "rejectionSummary"; text: root.vehicleModel.rejectionSummary; color: root.muted; font.pixelSize: 15; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            Text { text: "검증 실패 누적 " + root.vehicleModel.secocFailureCount + "건"; color: root.ink; font.pixelSize: 16 }
                            Text { objectName: "authenticationErrorIndicator"; visible: root.vehicleModel.authenticationError; text: "데이터 확인이 계속 실패하고 있습니다. 점검이 필요합니다."; color: root.red; font.pixelSize: 16; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            Text { text: "검증 거부는 이 IVI의 수신 결과입니다. 공격 노드의 송신 중단이나 특정 공격 전체 차단을 의미하지 않습니다."; color: root.muted; font.pixelSize: 13; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            Text { text: "상세 진단"; color: root.ink; font.pixelSize: 16 }
                            Repeater { model: root.vehicleModel.logs; Text { required property string modelData; text: modelData; color: root.muted; font.pixelSize: 12; Layout.fillWidth: true; wrapMode: Text.Wrap } }
                        }
                    }
                    ListView {
                        objectName: "historyList"
                        clip: true; spacing: 8
                        id: eventHistoryList
                        model: root.vehicleModel.eventHistory
                        header: Text { width: eventHistoryList.width; text: root.vehicleModel.historyStorageStatus; color: root.muted; font.pixelSize: 13; wrapMode: Text.Wrap; bottomPadding: 12; textFormat: Text.PlainText }
                        ScrollBar.vertical: ScrollBar {}
                        delegate: Rectangle {
                            required property string modelData
                            width: ListView.view.width; height: historyText.implicitHeight + 24
                            color: root.panel; radius: 10
                            Text { id: historyText; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 12; text: parent.modelData; textFormat: Text.PlainText; color: root.ink; font.pixelSize: 15; wrapMode: Text.Wrap }
                        }
                    }
                    ScrollView {
                        clip: true; contentWidth: availableWidth
                        ColumnLayout {
                            width: parent.width; spacing: 18
                            Text { text: "화면 모드"; color: root.ink; font.pixelSize: 21; font.bold: true }
                            RowLayout {
                                AppButton { text: "화이트 모드"; highlighted: !root.dark; onClicked: root.vehicleModel.darkMode = false }
                                AppButton { text: "다크 모드"; highlighted: root.dark; onClicked: root.vehicleModel.darkMode = true }
                            }
                            Text { text: "선택한 모드는 다음 실행에도 유지됩니다."; color: root.muted; font.pixelSize: 14 }
                            Text { Layout.fillWidth: true; text: "알림을 닫으면 팝업만 사라집니다. 위험 상태, 보안 탐지 결과, 이벤트 기록은 바뀌지 않습니다."; color: root.muted; font.pixelSize: 14; wrapMode: Text.Wrap }
                        }
                    }
                }
                RowLayout {
                    id: bottomTabs
                    objectName: "bottomTabs"
                    Layout.fillWidth: true; Layout.preferredHeight: 44; Layout.minimumHeight: 44; Layout.maximumHeight: 44
                    spacing: 8
                    Repeater {
                        model: ["배터리", "보안", "이력", "설정"]
                        AppButton {
                            required property int index
                            required property string modelData
                            Layout.fillWidth: true; Layout.fillHeight: true
                            text: modelData; highlighted: root.currentPage === index
                            onClicked: root.currentPage = index
                        }
                    }
                }
            }
            FocusScope {
                id: popupLayer
                objectName: "alertOverlay"
                anchors.fill: parent
                z: 100
                visible: root.batteryPopupVisible
                onVisibleChanged: { if (visible) closeButton.forceActiveFocus(); else canvas.forceActiveFocus() }
                Keys.onEscapePressed: root.vehicleModel.dismissPopup()
                Rectangle { anchors.fill: parent; color: "#99101928" }
                MouseArea { anchors.fill: parent }
                Rectangle {
                    id: popupCard
                    objectName: "alertDialog"
                    Accessible.role: Accessible.Dialog
                    Accessible.name: root.vehicleModel.popupTitle
                    anchors.centerIn: parent
                    width: 440; height: 290
                    radius: 20; color: root.panel
                    border.color: root.vehicleModel.popupKind === "success" ? root.green : root.vehicleModel.popupKind === "warning" ? root.orange : root.red
                    border.width: 2
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 24; spacing: 12
                        Text {
                            text: root.vehicleModel.popupKind === "success" ? "처리 결과" : "주의가 필요합니다"
                            color: root.vehicleModel.popupKind === "success" ? root.green : root.orange; font.pixelSize: 13; font.bold: true
                        }
                        Text { Layout.fillWidth: true; text: root.vehicleModel.popupTitle; color: root.ink; font.pixelSize: 25; font.bold: true; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight }
                        Text { Layout.fillWidth: true; text: root.vehicleModel.popupDescription; color: root.muted; font.pixelSize: 15; wrapMode: Text.Wrap; maximumLineCount: 4; elide: Text.ElideRight }
                        Item { Layout.fillHeight: true }
                        AppButton { id: closeButton; objectName: "dismissAlert"; text: "닫기"; Layout.fillWidth: true; Layout.preferredHeight: 44; onClicked: root.vehicleModel.dismissPopup() }
                    }
                }
            }
            Rectangle {
                id: notificationToast
                objectName: "notificationToast"
                z: 110
                anchors.top: parent.top; anchors.horizontalCenter: parent.horizontalCenter
                anchors.topMargin: 12
                width: 600; height: toastContent.implicitHeight + 24
                visible: root.toastVisible && root.currentPage !== 0
                radius: 12; color: root.panel; border.width: 2
                border.color: root.vehicleModel.popupKind === "success" ? root.green : root.vehicleModel.popupKind === "danger" ? root.red : root.orange
                Accessible.role: Accessible.AlertMessage
                Accessible.name: root.vehicleModel.popupTitle
                MouseArea { anchors.fill: parent }
                RowLayout {
                    id: toastContent
                    anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top
                    anchors.margins: 12; spacing: 12
                    ColumnLayout {
                        Layout.fillWidth: true; spacing: 4
                        Text { Layout.fillWidth: true; text: root.vehicleModel.popupTitle; color: root.ink; font.pixelSize: 17; font.bold: true; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight }
                        Text { Layout.fillWidth: true; text: root.vehicleModel.popupDescription; color: root.muted; font.pixelSize: 13; wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight }
                    }
                    AppButton { objectName: "dismissNotification"; text: "닫기"; Layout.preferredWidth: 60; Layout.preferredHeight: 40; onClicked: root.vehicleModel.dismissPopup() }
                }
            }
        }
    }
    component AppButton: Button {
        id: control
        padding: 8
        font.pixelSize: 13
        contentItem: Text {
            text: control.text; color: control.highlighted ? root.blue : root.ink
            font: control.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        background: Rectangle {
            radius: 9
            color: control.highlighted ? (root.dark ? "#243958" : "#edf3ff") : root.panel
            border.color: control.activeFocus ? root.blue : root.lineColor
            border.width: control.activeFocus ? 2 : 1
            opacity: control.down ? 0.65 : 1
        }
    }
    component Card: Rectangle { color: root.panel; radius: 14; border.color: root.lineColor; clip: true }
    component Metric: Card {
        property string title
        property string value
        Layout.fillWidth: true; Layout.fillHeight: true
        Column { anchors.fill: parent; anchors.margins: 10; spacing: 3
            Text { text: parent.parent.title; color: root.muted; font.pixelSize: 11 }
            Text { text: parent.parent.value; color: root.ink; font.pixelSize: 19; font.bold: true }
        }
    }
}
