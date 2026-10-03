import QtQuick
import QtQuick.Controls as Controls
import Quickshell
import "native/Commons"
import qs.Commons as Theme
import "native/Ui" as Ui

Ui.Panel {
    id: root
    moduleName: "ubruckhaus.my-plugins"
    manageIpc: false

    property var anchorItem: null
    property var hostWidget: null

    property var plugins: []
    property int totalViews: 0
    property int totalDownloads: 0
    property int totalHearts: 0
    property int totalStars: 0
    property bool hasChanges: false
    property string changesSummary: ""
    property int intervalMinutes: 5
    property string lastUpdatedText: ""
    property bool isQuerying: false

    signal refreshRequested()
    signal acknowledgeRequested()
    signal intervalSelected(int minutes)
    signal openUrl(string url)

    function formatTime(isoString) {
        if (!isoString) return "Never"
        try {
            var d = new Date(isoString)
            if (isNaN(d.getTime())) return isoString
            var hours = ("0" + d.getHours()).slice(-2)
            var mins = ("0" + d.getMinutes()).slice(-2)
            var secs = ("0" + d.getSeconds()).slice(-2)
            return hours + ":" + mins + ":" + secs
        } catch (e) {
            return isoString
        }
    }

    Ui.PopupCard {
        id: popup
        bar: root.bar
        anchorItem: root.anchorItem
        owner: root.hostWidget || root
        open: root.opened
        contentWidth: fittedContentWidth(Style.space(520))
        contentHeight: fittedContentHeight(content.implicitHeight, Style.space(660))

        Flickable {
            id: panelScroll
            anchors.fill: parent
            contentWidth: width
            contentHeight: content.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            Controls.ScrollBar.vertical: Controls.ScrollBar { policy: Controls.ScrollBar.AsNeeded }

            Column {
                id: content
                width: parent.width
                focus: root.opened
                spacing: Style.space(12)
                Keys.onEscapePressed: root.close()

                // Header
                Item {
                    width: parent.width
                    height: Style.space(32)

                    Row {
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: Style.space(8)

                        Text {
                            text: "🛍️"
                            font.pixelSize: Style.font.title
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Column {
                            anchors.verticalCenter: parent.verticalCenter
                            Text {
                                text: "My Plugins"
                                color: Theme.Color.accent
                                font.family: Theme.Style.font.family
                                font.pixelSize: Theme.Style.font.title
                                font.bold: true
                            }
                            Text {
                                text: "Omarchy Marketplace & GitHub Monitor"
                                color: Theme.Color.foreground
                                opacity: 0.6
                                font.family: Theme.Style.font.family
                                font.pixelSize: Theme.Style.font.caption
                            }
                        }
                    }

                    Row {
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: Style.space(6)

                        Ui.Button {
                            implicitHeight: Style.space(26)
                            text: root.isQuerying ? "Checking..." : "↻ Refresh"
                            fontSize: Style.font.caption
                            bordered: true
                            focusable: true
                            enabled: !root.isQuerying
                            onClicked: root.refreshRequested()
                        }

                        Ui.Button {
                            implicitHeight: Style.space(26)
                            text: "✕"
                            fontSize: Style.font.caption
                            bordered: true
                            focusable: true
                            onClicked: root.close()
                        }
                    }
                }

                // Changes Notification Banner (if changes detected)
                Rectangle {
                    width: parent.width
                    height: bannerCol.implicitHeight + Style.space(16)
                    radius: Style.radius(6)
                    visible: root.hasChanges
                    color: Qt.rgba(Theme.Color.accent.r, Theme.Color.accent.g, Theme.Color.accent.b, 0.12)
                    border.width: 1
                    border.color: Theme.Color.accent

                    Column {
                        id: bannerCol
                        anchors.fill: parent
                        anchors.margins: Style.space(8)
                        spacing: Style.space(4)

                        Row {
                            width: parent.width
                            spacing: Style.space(6)

                            Text {
                                text: "⚡"
                                font.pixelSize: Style.font.body
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: "New updates detected!"
                                color: Theme.Color.accent
                                font.family: Theme.Style.font.family
                                font.pixelSize: Theme.Style.font.body
                                font.bold: true
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Item { Layout.fillWidth: true; width: 10 }

                            Ui.Button {
                                implicitHeight: Style.space(22)
                                text: "✓ Mark as Read"
                                fontSize: Style.font.caption
                                bordered: true
                                focusable: true
                                onClicked: root.acknowledgeRequested()
                            }
                        }

                        Text {
                            width: parent.width
                            text: root.changesSummary !== "" ? root.changesSummary : "Metrics or status updated in latest query."
                            color: Theme.Color.foreground
                            font.family: Theme.Style.font.family
                            font.pixelSize: Theme.Style.font.caption
                            wrapMode: Text.Wrap
                        }
                    }
                }

                // Global Stats Cards Strip
                Row {
                    width: parent.width
                    spacing: Style.space(8)

                    // Views Card
                    Rectangle {
                        width: (parent.width - Style.space(24)) / 4
                        height: Style.space(52)
                        radius: Style.radius(6)
                        color: Qt.rgba(Theme.Color.surface.r, Theme.Color.surface.g, Theme.Color.surface.b, 0.45)
                        border.width: 1
                        border.color: Theme.Color.popups.border

                        Column {
                            anchors.centerIn: parent
                            spacing: Style.space(2)
                            Text {
                                text: "👁 Views"
                                color: Theme.Color.foreground
                                opacity: 0.65
                                font.pixelSize: Style.font.caption
                                anchors.horizontalCenter: parent.horizontalCenter
                            }
                            Text {
                                text: String(root.totalViews)
                                color: Theme.Color.foreground
                                font.pixelSize: Style.font.title
                                font.bold: true
                                anchors.horizontalCenter: parent.horizontalCenter
                            }
                        }
                    }

                    // Downloads Card
                    Rectangle {
                        width: (parent.width - Style.space(24)) / 4
                        height: Style.space(52)
                        radius: Style.radius(6)
                        color: Qt.rgba(Theme.Color.surface.r, Theme.Color.surface.g, Theme.Color.surface.b, 0.45)
                        border.width: 1
                        border.color: Theme.Color.popups.border

                        Column {
                            anchors.centerIn: parent
                            spacing: Style.space(2)
                            Text {
                                text: "📥 Downloads"
                                color: Theme.Color.foreground
                                opacity: 0.65
                                font.pixelSize: Style.font.caption
                                anchors.horizontalCenter: parent.horizontalCenter
                            }
                            Text {
                                text: String(root.totalDownloads)
                                color: Theme.Color.foreground
                                font.pixelSize: Style.font.title
                                font.bold: true
                                anchors.horizontalCenter: parent.horizontalCenter
                            }
                        }
                    }

                    // Hearts Card
                    Rectangle {
                        width: (parent.width - Style.space(24)) / 4
                        height: Style.space(52)
                        radius: Style.radius(6)
                        color: Qt.rgba(Theme.Color.surface.r, Theme.Color.surface.g, Theme.Color.surface.b, 0.45)
                        border.width: 1
                        border.color: Theme.Color.popups.border

                        Column {
                            anchors.centerIn: parent
                            spacing: Style.space(2)
                            Text {
                                text: "❤️ Hearts"
                                color: Theme.Color.foreground
                                opacity: 0.65
                                font.pixelSize: Style.font.caption
                                anchors.horizontalCenter: parent.horizontalCenter
                            }
                            Text {
                                text: String(root.totalHearts)
                                color: Theme.Color.foreground
                                font.pixelSize: Style.font.title
                                font.bold: true
                                anchors.horizontalCenter: parent.horizontalCenter
                            }
                        }
                    }

                    // GitHub Stars Card
                    Rectangle {
                        width: (parent.width - Style.space(24)) / 4
                        height: Style.space(52)
                        radius: Style.radius(6)
                        color: Qt.rgba(Theme.Color.surface.r, Theme.Color.surface.g, Theme.Color.surface.b, 0.45)
                        border.width: 1
                        border.color: Theme.Color.popups.border

                        Column {
                            anchors.centerIn: parent
                            spacing: Style.space(2)
                            Text {
                                text: "⭐ GH Stars"
                                color: Theme.Color.foreground
                                opacity: 0.65
                                font.pixelSize: Style.font.caption
                                anchors.horizontalCenter: parent.horizontalCenter
                            }
                            Text {
                                text: String(root.totalStars)
                                color: Theme.Color.foreground
                                font.pixelSize: Style.font.title
                                font.bold: true
                                anchors.horizontalCenter: parent.horizontalCenter
                            }
                        }
                    }
                }

                // Query Interval Configuration Strip
                Rectangle {
                    width: parent.width
                    height: Style.space(42)
                    radius: Style.radius(6)
                    color: Qt.rgba(Theme.Color.surface.r, Theme.Color.surface.g, Theme.Color.surface.b, 0.3)
                    border.width: 1
                    border.color: Theme.Color.popups.border

                    Row {
                        anchors.fill: parent
                        anchors.margins: Style.space(6)
                        spacing: Style.space(6)

                        Text {
                            text: "Interval:"
                            color: Theme.Color.foreground
                            opacity: 0.8
                            font.pixelSize: Style.font.caption
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Repeater {
                            model: [1, 2, 5, 10, 15, 30, 60]
                            delegate: Ui.Button {
                                implicitHeight: Style.space(24)
                                implicitWidth: Style.space(32)
                                text: modelData + "m"
                                fontSize: Style.font.caption
                                bordered: true
                                focusable: true
                                selected: root.intervalMinutes === modelData
                                onClicked: root.intervalSelected(modelData)
                            }
                        }

                        Item { width: 1; Layout.fillWidth: true }

                        Text {
                            text: "Updated: " + root.formatTime(root.lastUpdatedText)
                            color: Theme.Color.foreground
                            opacity: 0.55
                            font.pixelSize: Style.font.caption
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }

                // Section Divider
                Ui.PanelSectionHeader {
                    title: "Published Plugins (" + root.plugins.length + ")"
                }

                // Plugins List Repeater
                Repeater {
                    model: root.plugins
                    delegate: Rectangle {
                        width: parent.width
                        height: cardColumn.implicitHeight + Style.space(16)
                        radius: Style.radius(6)
                        color: Qt.rgba(Theme.Color.surface.r, Theme.Color.surface.g, Theme.Color.surface.b, 0.4)
                        border.width: 1
                        border.color: modelData.has_changes ? Theme.Color.accent : Theme.Color.popups.border

                        Column {
                            id: cardColumn
                            anchors.fill: parent
                            anchors.margins: Style.space(10)
                            spacing: Style.space(8)

                            // Plugin Title + Status Row
                            Row {
                                width: parent.width
                                spacing: Style.space(8)

                                Text {
                                    text: {
                                        var ic = modelData.display_icon
                                        if (ic === "rocket") return "🚀"
                                        if (ic === "tile") return "🪟"
                                        if (ic === "video") return "🌐"
                                        if (ic === "reader") return "📖"
                                        if (ic === "recipes") return "👨‍🍳"
                                        return "📦"
                                    }
                                    font.pixelSize: Style.font.body
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Text {
                                    text: modelData.name
                                    color: Theme.Color.foreground
                                    font.family: Theme.Style.font.family
                                    font.pixelSize: Theme.Style.font.body
                                    font.bold: true
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Item { width: 4; height: 1 }

                                // Status Pill
                                Rectangle {
                                    height: Style.space(20)
                                    width: statusText.implicitWidth + Style.space(12)
                                    radius: Style.radius(10)
                                    anchors.verticalCenter: parent.verticalCenter
                                    color: {
                                        var sc = modelData.status_code
                                        if (sc === "verified" || sc === "published" || sc === "listed") return Qt.rgba(0.2, 0.8, 0.4, 0.15)
                                        if (sc === "needs_fixes") return Qt.rgba(0.9, 0.3, 0.2, 0.15)
                                        if (sc === "review") return Qt.rgba(0.95, 0.6, 0.1, 0.15)
                                        return Qt.rgba(0.2, 0.5, 0.9, 0.15)
                                    }
                                    border.width: 1
                                    border.color: {
                                        var sc = modelData.status_code
                                        if (sc === "verified" || sc === "published" || sc === "listed") return "#2da44e"
                                        if (sc === "needs_fixes") return "#d1242f"
                                        if (sc === "review") return "#fbca04"
                                        return "#1d76db"
                                    }

                                    Text {
                                        id: statusText
                                        anchors.centerIn: parent
                                        text: modelData.status_text
                                        font.pixelSize: Style.font.caption - 1
                                        font.bold: true
                                        color: {
                                            var sc = modelData.status_code
                                            if (sc === "verified" || sc === "published" || sc === "listed") return "#3fb950"
                                            if (sc === "needs_fixes") return "#f85149"
                                            if (sc === "review") return "#d29922"
                                            return "#58a6ff"
                                        }
                                    }
                                }

                                Item { Layout.fillWidth: true; width: 10 }

                                // Issue Number link
                                Text {
                                    visible: modelData.issue_number !== null
                                    text: "#" + modelData.issue_number + " ↗"
                                    color: Theme.Color.accent
                                    font.pixelSize: Style.font.caption
                                    anchors.verticalCenter: parent.verticalCenter
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: if (modelData.issue_url) root.openUrl(modelData.issue_url)
                                    }
                                }
                            }

                            // Metrics Badges Row
                            Row {
                                width: parent.width
                                spacing: Style.space(16)

                                // Views
                                Row {
                                    spacing: Style.space(4)
                                    Text { text: "👁 Views:"; color: Theme.Color.foreground; opacity: 0.6; font.pixelSize: Style.font.caption }
                                    Text { text: String(modelData.views); color: Theme.Color.foreground; font.bold: true; font.pixelSize: Style.font.caption }
                                    Rectangle {
                                        visible: modelData.views_delta > 0
                                        height: Style.space(14)
                                        width: viewsDeltaText.implicitWidth + 6
                                        radius: 3
                                        color: Qt.rgba(Theme.Color.accent.r, Theme.Color.accent.g, Theme.Color.accent.b, 0.25)
                                        Text {
                                            id: viewsDeltaText
                                            anchors.centerIn: parent
                                            text: "+" + modelData.views_delta
                                            color: Theme.Color.accent
                                            font.pixelSize: Style.font.caption - 2
                                            font.bold: true
                                        }
                                    }
                                }

                                // Downloads
                                Row {
                                    spacing: Style.space(4)
                                    Text { text: "📥 Copies:"; color: Theme.Color.foreground; opacity: 0.6; font.pixelSize: Style.font.caption }
                                    Text { text: String(modelData.downloads); color: Theme.Color.foreground; font.bold: true; font.pixelSize: Style.font.caption }
                                    Rectangle {
                                        visible: modelData.downloads_delta > 0
                                        height: Style.space(14)
                                        width: dlDeltaText.implicitWidth + 6
                                        radius: 3
                                        color: Qt.rgba(Theme.Color.accent.r, Theme.Color.accent.g, Theme.Color.accent.b, 0.25)
                                        Text {
                                            id: dlDeltaText
                                            anchors.centerIn: parent
                                            text: "+" + modelData.downloads_delta
                                            color: Theme.Color.accent
                                            font.pixelSize: Style.font.caption - 2
                                            font.bold: true
                                        }
                                    }
                                }

                                // Hearts
                                Row {
                                    spacing: Style.space(4)
                                    Text { text: "❤️ Hearts:"; color: Theme.Color.foreground; opacity: 0.6; font.pixelSize: Style.font.caption }
                                    Text { text: String(modelData.hearts); color: Theme.Color.foreground; font.bold: true; font.pixelSize: Style.font.caption }
                                }

                                // Stars
                                Row {
                                    spacing: Style.space(4)
                                    Text { text: "⭐ GH Stars:"; color: Theme.Color.foreground; opacity: 0.6; font.pixelSize: Style.font.caption }
                                    Text { text: String(modelData.stars); color: Theme.Color.foreground; font.bold: true; font.pixelSize: Style.font.caption }
                                }
                            }

                            // Quick Link Buttons
                            Row {
                                width: parent.width
                                spacing: Style.space(8)

                                Ui.Button {
                                    implicitHeight: Style.space(22)
                                    text: "🛒 Marketplace"
                                    fontSize: Style.font.caption - 1
                                    bordered: true
                                    focusable: true
                                    onClicked: root.openUrl(modelData.marketplace_url)
                                }

                                Ui.Button {
                                    implicitHeight: Style.space(22)
                                    text: "🐙 GitHub Repo"
                                    fontSize: Style.font.caption - 1
                                    bordered: true
                                    focusable: true
                                    onClicked: root.openUrl(modelData.repo_url)
                                }

                                Ui.Button {
                                    visible: modelData.issue_url !== null
                                    implicitHeight: Style.space(22)
                                    text: "📋 Marketplace Issue"
                                    fontSize: Style.font.caption - 1
                                    bordered: true
                                    focusable: true
                                    onClicked: if (modelData.issue_url) root.openUrl(modelData.issue_url)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
