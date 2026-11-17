pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

ApplicationWindow {
    id: root
    required property var vehicleModel
    property bool demonstration: false
    width: 800
    height: 480
    visible: true
    title: demonstration ? "배터리 모니터 · 화면 시연" : "배터리 모니터"
    color: backgroundColor
    readonly property bool dark: vehicleModel.darkMode
    readonly property color backgroundColor: dark ? "#101722" : "#f4f6fa"
    readonly property color panel: dark ? "#182231" : "#ffffff"
    readonly property color ink: dark ? "#edf3ff" : "#172134"
    readonly property color muted: dark ? "#bdcbe0" : "#4f6077"
    readonly property color waitingPanel: dark ? "#3b2d17" : "#fff0ca"
    readonly property color lineColor: dark ? "#2c3a50" : "#e5eaf2"
    readonly property color green: dark ? "#36d399" : "#087f62"
    readonly property color orange: dark ? "#ffcb77" : "#925600"
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
                    UiText {
                        text: root.currentPage === 0 ? "배터리 현황" : root.pageNames[root.currentPage]
                        color: root.ink; font.pixelSize: 22; font.bold: true
                    }
                    Item { Layout.fillWidth: true }
                    UiText {
                        objectName: "connectionStatusLabel"
                        text: root.demonstration ? "화면 시연 · 가상 데이터" : root.vehicleModel.sessionProtocol ? root.vehicleModel.connectionLabel : !root.vehicleModel.valid ? "연결 대기" : root.vehicleModel.stale ? "마지막 확인값 · " + root.ageText(root.vehicleModel.lastGoodAgeMs) : "현재 수신값"
                        color: root.vehicleModel.stale ? root.orange : root.muted
                        font.pixelSize: 14
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
                                            showLabel: !root.vehicleModel.physicalMode
                                            available: root.vehicleModel.socAvailable
                                            stale: root.vehicleModel.stale || root.vehicleModel.sensorUsesLastGood
                                            highColor: root.green; mediumColor: root.orange; lowColor: root.red
                                            mutedColor: root.muted; panelColor: root.panel
                                            textColor: root.ink; trackColor: root.lineColor
                                        }
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 5
                                            UiText {
                                                objectName: "socStatusLabel"
                                                Layout.fillWidth: true
                                                text: !root.vehicleModel.socAvailable ? (root.vehicleModel.physicalSocOutsideModel ? "잔량 추정 범위 밖" : root.vehicleModel.physicalSocInitializing ? "초기 잔량 확인 중" : root.vehicleModel.physicalMode ? "잔량 추정 준비 중" : "배터리 정보 대기") : root.vehicleModel.physicalMode ? "배터리 잔량(SOC)" : root.vehicleModel.soc < 20 ? "충전이 필요합니다" : "잔량이 충분합니다"
                                                color: root.ink; font.pixelSize: 20; font.bold: true
                                                wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                                            }
                                            UiText {
                                                objectName: "socInitializationHint"
                                                Layout.fillWidth: true
                                                visible: root.vehicleModel.physicalSocInitializing || root.vehicleModel.physicalSocOutsideModel
                                                text: root.vehicleModel.physicalSocOutsideModel ? "추정 범위: 3.0~4.25V\n전압과 셀 상태를 확인해 주세요." : "저항 연결을 빼둔 채\n전압 안정화를 기다려 주세요."
                                                color: root.muted; font.pixelSize: 14
                                                wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                                            }
                                            UiText {
                                                objectName: "socEstimateHint"
                                                Layout.fillWidth: true
                                                visible: root.vehicleModel.physicalMode && root.vehicleModel.socAvailable
                                                text: root.vehicleModel.physicalObservationGap ? "측정 공백으로 추정 오차가 커질 수 있습니다." : "참고 모델로 계산한 추정값입니다."
                                                color: root.muted; font.pixelSize: 14
                                                wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                                            }
                                            UiText {
                                                Layout.fillWidth: true
                                                text: root.vehicleModel.physicalMode ? "배터리 건강도(SOH)" : root.vehicleModel.stale || root.vehicleModel.sensorUsesLastGood ? "마지막으로 확인한 값입니다." : "배터리 건강도(SOH)"
                                                color: root.muted; font.pixelSize: 14
                                                wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                                            }
                                            UiText {
                                                objectName: "sohValue"
                                                text: root.vehicleModel.sohAvailable ? root.vehicleModel.soh.toFixed(1) + "%" : "--"
                                                color: root.ink; font.pixelSize: 32; font.bold: true
                                            }
                                            UiText {
                                                objectName: "sohHint"
                                                Layout.fillWidth: true
                                                visible: root.vehicleModel.physicalMode
                                                text: root.vehicleModel.sohHint
                                                color: root.muted; font.pixelSize: 14
                                                wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                                            }
                                            UiText { text: "배터리 건강도(SOH)"; visible: !root.vehicleModel.physicalMode && (root.vehicleModel.stale || root.vehicleModel.sensorUsesLastGood); color: root.muted; font.pixelSize: 14 }
                                        }
                                    }
                                }
                                RowLayout {
                                    Layout.fillWidth: true; Layout.preferredHeight: 70; Layout.minimumHeight: 70; Layout.maximumHeight: 70
                                    spacing: 8
                                    Metric { objectName: "voltageMetric"; title: root.vehicleModel.physicalMode ? "셀 전압" : "팩 전압"; inputWaiting: root.vehicleModel.physicalMode && !root.vehicleModel.voltageAvailable; value: root.vehicleModel.voltageAvailable ? root.vehicleModel.voltage.toFixed(root.vehicleModel.physicalMode ? 3 : 2) + " V" : "--" }
                                    Metric { objectName: "currentMetric"; title: "전류"; inputWaiting: root.vehicleModel.physicalMode && !root.vehicleModel.currentAvailable; value: root.vehicleModel.currentAvailable ? root.vehicleModel.current.toFixed(root.vehicleModel.physicalMode ? 3 : 1) + " A" : "--" }
                                    Metric { objectName: "temperatureMetric"; title: "온도"; inputWaiting: root.vehicleModel.physicalMode && !root.vehicleModel.temperatureAvailable; value: root.vehicleModel.temperatureAvailable ? root.vehicleModel.temperature.toFixed(root.vehicleModel.physicalMode ? 1 : 0) + " °C" : "--" }
                                }
                            }
                            ColumnLayout {
                                Layout.fillWidth: true; Layout.preferredWidth: 310
                                Layout.fillHeight: true; spacing: 8
                                Card {
                                    objectName: "systemStatusCard"
                                    Layout.fillWidth: true; Layout.fillHeight: true
                                    Layout.preferredHeight: 112; Layout.minimumHeight: 112
                                    border.color: root.vehicleModel.failSafeOverlayActive ? root.red : root.vehicleModel.failSafeState === "WARNING" ? root.orange : root.lineColor
                                    ColumnLayout {
                                        anchors.fill: parent; anchors.margins: 10; spacing: 5
                                        UiText { text: "시스템 상태"; color: root.muted; font.pixelSize: 14 }
                                        UiText {
                                            objectName: "statusTitle"
                                            Layout.fillWidth: true
                                            text: root.vehicleModel.statusTitle
                                            color: root.vehicleModel.failSafeOverlayActive ? root.red : root.vehicleModel.failSafeState === "WARNING" ? root.orange : root.ink
                                            font.pixelSize: 20; font.bold: true; elide: Text.ElideRight
                                        }
                                        UiText {
                                            objectName: "statusDescriptionLabel"
                                            Layout.fillWidth: true
                                            text: root.vehicleModel.statusDescription
                                            color: root.muted; font.pixelSize: 14
                                            wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                                        }
                                        Item { Layout.fillHeight: true }
                                    }
                                }
                                Card {
                                    Layout.fillWidth: true; Layout.fillHeight: true
                                    Layout.preferredHeight: 140; Layout.minimumHeight: 140
                                    ColumnLayout {
                                        anchors.fill: parent; anchors.margins: 8; spacing: 4
                                        UiText { text: "보안 탐지 결과"; color: root.muted; font.pixelSize: 14 }
                                        UiText {
                                            objectName: "securityTitle"
                                            Layout.fillWidth: true
                                            text: root.vehicleModel.securityTitle
                                            color: root.ink; font.pixelSize: 19; font.bold: true
                                            wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                                        }
                                        UiText { Layout.fillWidth: true; text: root.vehicleModel.secocFailureCount + "건 수신 검증 실패"; color: root.muted; font.pixelSize: 14 }
                                        AppButton { text: "보안 내역 보기"; padding: 5; Layout.preferredHeight: 32; Layout.minimumHeight: 32; Layout.maximumHeight: 32; onClicked: root.currentPage = 1 }
                                    }
                                }
                            }
                        }
                        Card {
                            id: recentCard
                            objectName: "recentEventsCard"
                            Layout.fillWidth: true; Layout.preferredHeight: 96
                            ColumnLayout {
                                anchors.fill: parent; anchors.margins: 8; spacing: 3
                                RowLayout {
                                    Layout.fillWidth: true
                                    UiText { text: "최근 이벤트"; color: root.ink; font.pixelSize: 14; font.bold: true }
                                    Item { Layout.fillWidth: true }
                                    AppButton { text: "전체 보기"; padding: 4; Layout.preferredHeight: 26; Layout.minimumHeight: 26; Layout.maximumHeight: 26; onClicked: root.currentPage = 2 }
                                }
                                Repeater {
                                    model: root.vehicleModel.recentEvents
                                    UiText { required property string modelData; Layout.fillWidth: true; text: modelData; color: root.muted; font.pixelSize: 14; elide: Text.ElideRight }
                                }
                                UiText { visible: root.vehicleModel.recentEvents.length === 0; text: "아직 기록된 이벤트가 없습니다."; color: root.muted; font.pixelSize: 14 }
                                Item { Layout.fillHeight: true }
                            }
                        }
                    }
                    Flickable {
                        id: securityScroll
                        objectName: "securityScroll"
                        clip: true; contentWidth: width
                        contentHeight: securityDetails.implicitHeight
                        flickableDirection: Flickable.VerticalFlick
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded; interactive: true }
                        ColumnLayout {
                            id: securityDetails
                            width: Math.max(0, securityScroll.width - 16)
                            spacing: 18
                            UiText { text: root.vehicleModel.securityTitle; color: root.ink; font.pixelSize: 24; font.bold: true; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            UiText { text: root.vehicleModel.securityDescription; color: root.muted; font.pixelSize: 16; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            UiText { text: "수신 검증 결과"; color: root.ink; font.pixelSize: 19; font.bold: true }
                            Repeater { model: root.vehicleModel.incidentTreatments; UiText { required property string modelData; text: modelData; color: root.ink; font.pixelSize: 15; Layout.fillWidth: true; wrapMode: Text.Wrap } }
                            UiText { objectName: "rejectionSummary"; text: root.vehicleModel.rejectionSummary; color: root.muted; font.pixelSize: 16; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            UiText { text: "검증 실패 누적 " + root.vehicleModel.secocFailureCount + "건"; color: root.ink; font.pixelSize: 17 }
                            UiText { objectName: "authenticationErrorIndicator"; visible: root.vehicleModel.authenticationError; text: "데이터 확인이 계속 실패하고 있습니다. 점검이 필요합니다."; color: root.red; font.pixelSize: 17; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            UiText { text: "검증 거부는 이 IVI의 수신 결과입니다. 공격 노드의 송신 중단이나 특정 공격 전체 차단을 의미하지 않습니다."; color: root.muted; font.pixelSize: 14; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            UiText { objectName: "canHealthHeading"; text: "CAN 통신 상태"; color: root.ink; font.pixelSize: 19; font.bold: true }
                            Repeater {
                                model: root.vehicleModel.floodingMetrics
                                UiText { required property string modelData; text: modelData; color: root.muted; font.pixelSize: 15; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            }
                            UiText { text: "상세 진단"; color: root.ink; font.pixelSize: 17 }
                            Repeater { model: root.vehicleModel.logs; UiText { required property string modelData; text: modelData; color: root.muted; font.pixelSize: 14; Layout.fillWidth: true; wrapMode: Text.Wrap } }
                        }
                    }
                    ListView {
                        objectName: "historyList"
                        clip: true; spacing: 10
                        id: eventHistoryList
                        model: root.vehicleModel.eventHistory
                        header: UiText { width: eventHistoryList.width; text: root.vehicleModel.historyStorageStatus; color: root.muted; font.pixelSize: 14; wrapMode: Text.Wrap; bottomPadding: 12; textFormat: Text.PlainText }
                        ScrollBar.vertical: ScrollBar {}
                        delegate: Rectangle {
                            required property string modelData
                            width: ListView.view.width; height: historyText.implicitHeight + 28
                            color: root.panel; radius: 10
                            UiText { id: historyText; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 12; text: parent.modelData; textFormat: Text.PlainText; color: root.ink; font.pixelSize: 16; wrapMode: Text.Wrap }
                        }
                    }
                    ScrollView {
                        clip: true; contentWidth: availableWidth
                        ColumnLayout {
                            width: parent.width; spacing: 18
                            UiText { text: "화면 모드"; color: root.ink; font.pixelSize: 22; font.bold: true }
                            RowLayout {
                                AppButton { text: "화이트 모드"; highlighted: !root.dark; onClicked: root.vehicleModel.darkMode = false }
                                AppButton { text: "다크 모드"; highlighted: root.dark; onClicked: root.vehicleModel.darkMode = true }
                            }
                            UiText { text: "선택한 모드는 다음 실행에도 유지됩니다."; color: root.muted; font.pixelSize: 15 }
                            UiText { Layout.fillWidth: true; text: "알림을 닫으면 팝업만 사라집니다. 위험 상태, 보안 탐지 결과, 이벤트 기록은 바뀌지 않습니다."; color: root.muted; font.pixelSize: 15; wrapMode: Text.Wrap }
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
                    width: 500; height: 320
                    radius: 20; color: root.panel
                    border.color: root.vehicleModel.popupKind === "success" ? root.green : root.vehicleModel.popupKind === "warning" ? root.orange : root.red
                    border.width: 2
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 22; spacing: 10
                        UiText {
                            text: root.vehicleModel.popupKind === "success" ? "처리 결과" : "주의가 필요합니다"
                            color: root.vehicleModel.popupKind === "success" ? root.green : root.orange; font.pixelSize: 14; font.bold: true
                        }
                        UiText { Layout.fillWidth: true; text: root.vehicleModel.popupTitle; color: root.ink; font.pixelSize: 26; font.bold: true; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight }
                        UiText { Layout.fillWidth: true; text: root.vehicleModel.popupDescription; color: root.muted; font.pixelSize: 16; wrapMode: Text.Wrap; maximumLineCount: 4; elide: Text.ElideRight }
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
                        Layout.fillWidth: true; spacing: 6
                        UiText { Layout.fillWidth: true; text: root.vehicleModel.popupTitle; color: root.ink; font.pixelSize: 19; font.bold: true; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight }
                        UiText { Layout.fillWidth: true; text: root.vehicleModel.popupDescription; color: root.muted; font.pixelSize: 14; wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight }
                    }
                    AppButton { objectName: "dismissNotification"; text: "닫기"; Layout.preferredWidth: 60; Layout.preferredHeight: 40; onClicked: root.vehicleModel.dismissPopup() }
                }
            }
        }
    }
    component UiText: Text {
        font.pixelSize: 14
        font.weight: Font.Medium
        lineHeight: 1.2
        lineHeightMode: Text.ProportionalHeight
        textFormat: Text.PlainText
    }
    component AppButton: Button {
        id: control
        padding: 8
        font.pixelSize: 15
        font.weight: Font.DemiBold
        contentItem: UiText {
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
        id: metric
        property string title
        property string value
        property bool inputWaiting: false
        readonly property string statusText: inputWaiting ? "센서 입력 대기" : ""
        Accessible.role: Accessible.StaticText
        Accessible.name: title + " · " + (inputWaiting ? statusText : value)
        color: inputWaiting ? root.waitingPanel : root.panel
        border.color: inputWaiting ? root.orange : root.lineColor
        border.width: inputWaiting ? 2 : 1
        Layout.fillWidth: true; Layout.fillHeight: true
        Rectangle { anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom; anchors.margins: 6; width: 3; radius: 1; color: root.orange; visible: metric.inputWaiting }
        Column { anchors.fill: parent; anchors.margins: 8; anchors.leftMargin: metric.inputWaiting ? 14 : 8; spacing: 4
            UiText { width: parent.width; text: metric.title; color: metric.inputWaiting ? root.orange : root.muted; font.pixelSize: 14; font.weight: Font.DemiBold }
            UiText { objectName: "metricReading"; width: parent.width; text: metric.inputWaiting ? metric.statusText : metric.value; color: metric.inputWaiting ? root.orange : root.ink; font.pixelSize: metric.inputWaiting ? 16 : 24; font.bold: true; elide: Text.ElideRight }
        }
    }
}
