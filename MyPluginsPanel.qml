import QtQuick
import QtQuick.Controls as Controls
import Quickshell
import "native/Commons"
import "native/Ui" as Ui

Ui.Panel {
    id: root
    moduleName: "ubruckhaus.my-plugins"
    manageIpc: false

    property var anchorItem: null
    property var hostWidget: null

    property string author: ""
    property bool needsAccount: false
    property string accountMessage: ""
    property string accountSource: ""
    property bool editAccount: false
    property var history: ({})
    property string historyMetric: "views"
    property string historyRange: "daily"
    property string historyPlugin: "all"
    readonly property var historyValues: history.values || []
    readonly property real historyMax: Math.max.apply(null, [1].concat(historyValues.filter(function(v) { return v !== null })))
    readonly property int historyGain: historyValues.reduce(function(sum, v) { return sum + (v || 0) }, 0)
    property int hoveredBar: -1
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
    property string sortBy: "views"
    property string sortOrder: "desc"

    signal refreshRequested()
    signal acknowledgeRequested()
    signal intervalSelected(int minutes)
    signal sortChanged(string sortBy, string sortOrder)
    signal openUrl(string url)
    signal accountSubmitted(string name)
    signal historyRequested(string plugin, string metric, string range)

    function reloadHistory() { historyRequested(historyPlugin, historyMetric, historyRange) }
    onOpenedChanged: if (opened) reloadHistory()

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

    // A layer surface that takes the keyboard; the xdg-popup PopupCard never receives typing.
    Ui.KeyboardPanel {
        id: popup
        focusTarget: content
        bar: root.bar
        anchorItem: root.anchorItem
        owner: root.hostWidget || root
        open: root.opened
        contentWidth: fittedContentWidth(Style.space(540))
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

                        Text { textFormat: Text.PlainText;
                            text: "🛍️"
                            font.pixelSize: Style.font.title
                        }

                        Column {
                            Row {
                                spacing: Style.space(6)
                                Text { textFormat: Text.PlainText;
                                    text: "My Plugins"
                                    color: Color.accent
                                    font.family: Style.font.family
                                    font.pixelSize: Style.font.title
                                    font.bold: true
                                }
                                Rectangle {
                                    height: Style.space(16)
                                    width: authorBadgeText.implicitWidth + Style.space(8)
                                    radius: Style.space(8)
                                    color: Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.15)
                                    anchors.verticalCenter: parent.verticalCenter
                                    Text { textFormat: Text.PlainText;
                                        id: authorBadgeText
                                        anchors.centerIn: parent
                                        text: root.author ? "@" + root.author + " ✎" : "set account ✎"
                                        color: Color.accent
                                        font.family: Style.font.family
                                        font.pixelSize: Style.font.caption - 1
                                        font.bold: true
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.editAccount = !root.editAccount }
                                }
                                }
                            }
                            Text { textFormat: Text.PlainText;
                                text: "Omarchy Marketplace & GitHub Monitor"
                                color: Color.foreground
                                opacity: 0.6
                                font.family: Style.font.family
                                font.pixelSize: Style.font.caption
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
                    radius: (Style.cornerRadius > 0 ? Style.cornerRadius : 6)
                    visible: root.hasChanges
                    color: Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.12)
                    border.width: 1
                    border.color: Color.accent

                    Column {
                        id: bannerCol
                        anchors.fill: parent
                        anchors.margins: Style.space(8)
                        spacing: Style.space(4)

                        Item {
                            width: parent.width
                            height: Style.space(26)

                            Row {
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: Style.space(6)

                                Text { textFormat: Text.PlainText;
                                    text: "⚡"
                                    font.pixelSize: Style.font.body
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Text { textFormat: Text.PlainText;
                                    text: "New updates detected!"
                                    color: Color.accent
                                    font.pixelSize: Style.font.body
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                            }

                            Ui.Button {
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                implicitHeight: Style.space(22)
                                text: "✓ Mark as Read"
                                fontSize: Style.font.caption
                                bordered: true
                                focusable: true
                                onClicked: root.acknowledgeRequested()
                            }
                        }

                        Text { textFormat: Text.PlainText;
                            width: parent.width
                            text: root.changesSummary !== "" ? root.changesSummary : "Metrics or status updated in latest query."
                            color: Color.foreground
                            font.family: Style.font.family
                            font.pixelSize: Style.font.caption
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
                        radius: (Style.cornerRadius > 0 ? Style.cornerRadius : 6)
                        color: Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.07)
                        border.width: 1
                        border.color: Color.popups.border

                        Column {
                            anchors.centerIn: parent
                            spacing: Style.space(2)
                            Text { textFormat: Text.PlainText;
                                text: "👁 Views"
                                color: Color.foreground
                                opacity: 0.65
                                font.pixelSize: Style.font.caption
                                anchors.horizontalCenter: parent.horizontalCenter
                            }
                            Text { textFormat: Text.PlainText;
                                text: String(root.totalViews)
                                color: Color.foreground
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
                        radius: (Style.cornerRadius > 0 ? Style.cornerRadius : 6)
                        color: Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.07)
                        border.width: 1
                        border.color: Color.popups.border

                        Column {
                            anchors.centerIn: parent
                            spacing: Style.space(2)
                            Text { textFormat: Text.PlainText;
                                text: "📥 Downloads"
                                color: Color.foreground
                                opacity: 0.65
                                font.pixelSize: Style.font.caption
                                anchors.horizontalCenter: parent.horizontalCenter
                            }
                            Text { textFormat: Text.PlainText;
                                text: String(root.totalDownloads)
                                color: Color.foreground
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
                        radius: (Style.cornerRadius > 0 ? Style.cornerRadius : 6)
                        color: Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.07)
                        border.width: 1
                        border.color: Color.popups.border

                        Column {
                            anchors.centerIn: parent
                            spacing: Style.space(2)
                            Text { textFormat: Text.PlainText;
                                text: "❤️ Hearts"
                                color: Color.foreground
                                opacity: 0.65
                                font.pixelSize: Style.font.caption
                                anchors.horizontalCenter: parent.horizontalCenter
                            }
                            Text { textFormat: Text.PlainText;
                                text: String(root.totalHearts)
                                color: Color.foreground
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
                        radius: (Style.cornerRadius > 0 ? Style.cornerRadius : 6)
                        color: Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.07)
                        border.width: 1
                        border.color: Color.popups.border

                        Column {
                            anchors.centerIn: parent
                            spacing: Style.space(2)
                            Text { textFormat: Text.PlainText;
                                text: "⭐ GH Stars"
                                color: Color.foreground
                                opacity: 0.65
                                font.pixelSize: Style.font.caption
                                anchors.horizontalCenter: parent.horizontalCenter
                            }
                            Text { textFormat: Text.PlainText;
                                text: String(root.totalStars)
                                color: Color.foreground
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
                    radius: (Style.cornerRadius > 0 ? Style.cornerRadius : 6)
                    color: Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.05)
                    border.width: 1
                    border.color: Color.popups.border

                    Item {
                        anchors.fill: parent
                        anchors.margins: Style.space(6)

                        Row {
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: Style.space(6)

                            Text { textFormat: Text.PlainText;
                                text: "Interval:"
                                color: Color.foreground
                                opacity: 0.8
                                font.pixelSize: Style.font.caption
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
                        }

                        Text { textFormat: Text.PlainText;
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Updated: " + root.formatTime(root.lastUpdatedText)
                            color: Color.foreground
                            opacity: 0.55
                            font.pixelSize: Style.font.caption
                        }
                    }
                }

                // GitHub account whose marketplace plugins are shown
                Rectangle {
                    width: parent.width
                    visible: root.editAccount || root.needsAccount
                    height: visible ? accountColumn.implicitHeight + Style.space(16) : 0
                    radius: (Style.cornerRadius > 0 ? Style.cornerRadius : 6)
                    color: Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.08)
                    border.width: 1
                    border.color: Color.accent
                    Column {
                        id: accountColumn
                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: Style.space(8)
                        spacing: Style.space(6)
                        Text { textFormat: Text.PlainText; width: parent.width; text: "GitHub account"; color: Color.accent; font.family: Style.font.family; font.pixelSize: Style.font.body; font.bold: true }
                        Text { width: parent.width; wrapMode: Text.Wrap; textFormat: Text.PlainText; text: "Plugins are found in the marketplace catalog by repository owner: for github.com/uBruckhaus/omarchy-theme-manager the account is uBruckhaus. Leave it empty to use the account gh is logged into."; color: Color.foreground; opacity: 0.8; font.family: Style.font.family; font.pixelSize: Style.font.caption }
                        Row {
                            width: parent.width; spacing: Style.space(6)
                            Ui.TextField { id: accountField; width: parent.width - saveAccount.width - Style.space(6); text: root.author; placeholderText: "GitHub account, e.g. uBruckhaus"; onAccepted: root.accountSubmitted(text.trim()) }
                            Ui.Button { id: saveAccount; focusable: true; bordered: true; text: "Save"; onClicked: { root.accountSubmitted(accountField.text.trim()); root.editAccount = false } }
                        }
                        Text { width: parent.width; visible: root.author !== "" && root.accountSource !== "" && root.accountSource !== "settings"; wrapMode: Text.Wrap; textFormat: Text.PlainText; text: "Using @" + root.author + ", detected from " + root.accountSource + " on this computer. Save to keep it, or enter another account."; color: Color.foreground; opacity: 0.8; font.family: Style.font.family; font.pixelSize: Style.font.caption }
                        Text { width: parent.width; visible: root.accountMessage !== ""; wrapMode: Text.Wrap; textFormat: Text.PlainText; text: root.accountMessage; color: Color.accent; font.family: Style.font.family; font.pixelSize: Style.font.caption }
                    }
                }

                // History of views, downloads, hearts and stars
                Rectangle {
                    width: parent.width
                    height: historyColumn.implicitHeight + Style.space(16)
                    radius: (Style.cornerRadius > 0 ? Style.cornerRadius : 6)
                    color: Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.05)
                    border.width: 1
                    border.color: Color.popups.border
                    Column {
                        id: historyColumn
                        anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: Style.space(10)
                        spacing: Style.space(8)
                        Row {
                            width: parent.width; spacing: Style.space(8)
                            Text { textFormat: Text.PlainText; text: "📈 History"; color: Color.accent; font.family: Style.font.family; font.pixelSize: Style.font.body; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                            Text { textFormat: Text.PlainText; anchors.verticalCenter: parent.verticalCenter; color: Color.foreground; opacity: 0.75; font.family: Style.font.family; font.pixelSize: Style.font.caption
                                   text: root.hoveredBar >= 0 && root.historyValues[root.hoveredBar] !== null
                                         ? (root.history.labels || [])[root.hoveredBar] + ": +" + root.historyValues[root.hoveredBar] + " (" + (root.history.totals || [])[root.hoveredBar] + " total)"
                                         : "+" + root.historyGain + " in this range" }
                        }
                        Row {
                            width: parent.width; spacing: Style.space(6)
                            Ui.Dropdown { showLabel: false; width: (parent.width - Style.space(12)) / 3; value: root.historyMetric
                                options: [{value: "views", label: "👁 Views"}, {value: "downloads", label: "📥 Downloads"}, {value: "hearts", label: "❤️ Hearts"}, {value: "stars", label: "⭐ Stars"}]
                                onChanged: function(v) { root.historyMetric = v; root.reloadHistory() } }
                            Ui.Dropdown { showLabel: false; width: (parent.width - Style.space(12)) / 3; value: root.historyRange
                                options: [{value: "daily", label: "Daily · 30 days"}, {value: "weekly", label: "Weekly · 12 weeks"}, {value: "monthly", label: "Monthly · 12 months"}]
                                onChanged: function(v) { root.historyRange = v; root.reloadHistory() } }
                            Ui.Dropdown { showLabel: false; width: (parent.width - Style.space(12)) / 3; value: root.historyPlugin
                                options: [{value: "all", label: "All plugins"}].concat(root.plugins.map(function(p) { return {value: p.id, label: p.name} }))
                                onChanged: function(v) { root.historyPlugin = v; root.reloadHistory() } }
                        }
                        Item {
                            id: chart
                            width: parent.width; height: Style.space(110)
                            readonly property int count: Math.max(1, root.historyValues.length)
                            readonly property real slot: width / count
                            Rectangle { anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom; height: 1; color: Color.foreground; opacity: 0.25 }
                            Repeater {
                                model: root.historyValues
                                Rectangle {
                                    required property var modelData
                                    required property int index
                                    x: index * chart.slot + chart.slot * 0.15
                                    width: Math.max(2, chart.slot * 0.7)
                                    height: modelData === null ? 2 : Math.max(modelData > 0 ? 3 : 1, (chart.height - Style.space(14)) * modelData / root.historyMax)
                                    anchors.bottom: parent.bottom
                                    radius: Math.min(3, width / 2)
                                    color: modelData === null ? Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.15)
                                                              : (root.hoveredBar === index ? Color.foreground : Color.accent)
                                    Text { textFormat: Text.PlainText; visible: modelData !== null && modelData > 0 && chart.count <= 12; anchors.bottom: parent.top; anchors.horizontalCenter: parent.horizontalCenter
                                           text: modelData; color: Color.foreground; opacity: 0.8; font.family: Style.font.family; font.pixelSize: Style.font.caption - 1 }
                                    MouseArea { anchors.fill: parent; anchors.topMargin: -chart.height; hoverEnabled: true
                                                onEntered: root.hoveredBar = index; onExited: if (root.hoveredBar === index) root.hoveredBar = -1 }
                                }
                            }
                        }
                        Item {
                            width: parent.width; height: Style.space(14)
                            Repeater {
                                model: root.history.labels || []
                                Text { textFormat: Text.PlainText; required property var modelData; required property int index
                                       visible: chart.count <= 12 || index % 5 === (chart.count - 1) % 5
                                       x: index * chart.slot + chart.slot / 2 - width / 2
                                       text: modelData; color: Color.foreground; opacity: 0.6; font.family: Style.font.family; font.pixelSize: Style.font.caption - 1 }
                            }
                        }
                        Text { width: parent.width; wrapMode: Text.Wrap; textFormat: Text.PlainText; color: Color.foreground; opacity: 0.6; font.family: Style.font.family; font.pixelSize: Style.font.caption - 1
                               text: root.history.first_day ? "Gains per " + (root.historyRange === "daily" ? "day" : root.historyRange === "weekly" ? "week" : "month") + ". Recorded since " + root.history.first_day + "; the marketplace keeps no history, so earlier periods stay empty."
                                                            : "History starts with the first refresh: one snapshot per day is kept for 400 days." }
                    }
                }

                // Sort Configuration Strip
                Rectangle {
                    width: parent.width
                    height: sortRow.implicitHeight + Style.space(16)
                    radius: (Style.cornerRadius > 0 ? Style.cornerRadius : 6)
                    color: Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.05)
                    border.width: 1
                    border.color: Color.popups.border

                    Row {
                        id: sortRow
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        anchors.leftMargin: Style.space(10)
                        anchors.rightMargin: Style.space(10)
                        spacing: Style.space(10)

                        Text { textFormat: Text.PlainText;
                            text: "Sort:"
                            color: Color.foreground
                            opacity: 0.8
                            font.pixelSize: Style.font.caption
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Ui.Dropdown {
                            id: sortByDropdown
                            showLabel: false
                            width: Style.space(150)
                            value: root.sortBy
                            options: [
                                { value: "views", label: "👁 Views" },
                                { value: "downloads", label: "📥 Downloads" },
                                { value: "hearts", label: "❤️ Hearts" },
                                { value: "stars", label: "⭐ GitHub Stars" },
                                { value: "name", label: "🔤 Name" },
                                { value: "date", label: "📅 Publish Date" }
                            ]
                            onChanged: function(v) { root.sortChanged(v, root.sortOrder) }
                        }

                        Ui.Dropdown {
                            id: sortOrderDropdown
                            showLabel: false
                            width: Style.space(120)
                            value: root.sortOrder
                            options: [
                                { value: "desc", label: "↓ Descending" },
                                { value: "asc", label: "↑ Ascending" }
                            ]
                            onChanged: function(v) { root.sortChanged(root.sortBy, v) }
                        }
                    }
                }

                // Section Divider
                Ui.PanelSectionHeader {
                    text: "Published Plugins by @" + (root.author || "?") + " (" + root.plugins.length + ")"
                }

                // Table Column Headers
                Item {
                    width: parent.width
                    height: Style.space(18)

                    Row {
                        anchors.fill: parent
                        anchors.leftMargin: Style.space(10)
                        anchors.rightMargin: Style.space(10)
                        spacing: Style.space(8)

                        Text { textFormat: Text.PlainText;
                            width: Style.space(92)
                            text: "PUBLISHED"
                            color: Color.foreground
                            opacity: 0.5
                            font.family: Style.font.family
                            font.pixelSize: Style.font.caption - 1
                            font.bold: true
                        }

                        Text { textFormat: Text.PlainText;
                            width: Style.space(150)
                            text: "PLUGIN"
                            color: Color.foreground
                            opacity: 0.5
                            font.family: Style.font.family
                            font.pixelSize: Style.font.caption - 1
                            font.bold: true
                        }

                        Text { textFormat: Text.PlainText;
                            text: "STATUS / VERIFICATION"
                            color: Color.foreground
                            opacity: 0.5
                            font.family: Style.font.family
                            font.pixelSize: Style.font.caption - 1
                            font.bold: true
                        }
                    }
                }

                // Plugins List Repeater
                Repeater {
                    model: root.plugins
                    delegate: Rectangle {
                        width: parent.width
                        height: cardColumn.implicitHeight + Style.space(16)
                        radius: (Style.cornerRadius > 0 ? Style.cornerRadius : 6)
                        color: Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.06)
                        border.width: 1
                        border.color: modelData.has_changes ? Color.accent : Color.popups.border

                        Column {
                            id: cardColumn
                            anchors.fill: parent
                            anchors.margins: Style.space(10)
                            spacing: Style.space(8)

                            // Plugin Title + Status Row
                            Item {
                                width: parent.width
                                height: Style.space(22)

                                Row {
                                    anchors.left: parent.left
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: Style.space(8)

                                    // First Column: Publish Date Badge
                                    Rectangle {
                                        width: Style.space(92)
                                        height: Style.space(22)
                                        radius: (Style.cornerRadius > 0 ? Style.cornerRadius : 4)
                                        color: Qt.rgba(Color.foreground.r, Color.foreground.g, Color.foreground.b, 0.08)
                                        border.width: 1
                                        border.color: Color.popups.border

                                        Row {
                                            anchors.centerIn: parent
                                            spacing: Style.space(4)
                                            Text { textFormat: Text.PlainText;
                                                text: "📅"
                                                font.pixelSize: Style.font.caption - 2
                                            }
                                            Text { textFormat: Text.PlainText;
                                                text: modelData.publish_date || "—"
                                                color: Color.foreground
                                                font.family: Style.font.family
                                                font.pixelSize: Style.font.caption
                                                font.bold: true
                                            }
                                        }
                                    }

                                    // Second Column: Plugin Icon & Name
                                    Item {
                                        width: Style.space(150)
                                        height: parent.height

                                        Row {
                                            anchors.left: parent.left
                                            anchors.verticalCenter: parent.verticalCenter
                                            spacing: Style.space(6)

                                            Text { textFormat: Text.PlainText;
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
                                            }

                                            Text { textFormat: Text.PlainText;
                                                text: modelData.name
                                                color: Color.foreground
                                                font.family: Style.font.family
                                                font.pixelSize: Style.font.body
                                                font.bold: true
                                                elide: Text.ElideRight
                                                width: Style.space(120)
                                            }
                                        }
                                    }

                                    // Third Column: Status Pill
                                    Rectangle {
                                        height: Style.space(20)
                                        width: statusText.implicitWidth + Style.space(12)
                                        radius: (Style.cornerRadius > 0 ? Style.cornerRadius : 10)
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

                                        Text { textFormat: Text.PlainText;
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
                                }

                                // Issue Number link
                                Text { textFormat: Text.PlainText;
                                    visible: modelData.issue_number !== null
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "#" + modelData.issue_number + " ↗"
                                    color: Color.accent
                                    font.pixelSize: Style.font.caption
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
                                spacing: Style.space(14)

                                // Version: installed version, with the published
                                // GitHub release alongside when it differs.
                                Row {
                                    spacing: Style.space(4)
                                    Text { textFormat: Text.PlainText; text: "📦 Ver:"; color: Color.foreground; opacity: 0.6; font.pixelSize: Style.font.caption }
                                    Text { textFormat: Text.PlainText;
                                        text: {
                                            var v = modelData.local_version || modelData.release_version || ""
                                            if (v === "") return "—"
                                            var out = "v" + v
                                            if (modelData.local_version !== "" && modelData.release_version !== "" && modelData.local_version !== modelData.release_version) {
                                                out += " · GH v" + modelData.release_version
                                            }
                                            return out
                                        }
                                        color: Color.foreground
                                        font.bold: true
                                        font.pixelSize: Style.font.caption
                                    }
                                }

                                // Views
                                Row {
                                    spacing: Style.space(4)
                                    Text { textFormat: Text.PlainText; text: "👁 Views:"; color: Color.foreground; opacity: 0.6; font.pixelSize: Style.font.caption }
                                    Text { textFormat: Text.PlainText; text: String(modelData.views); color: Color.foreground; font.bold: true; font.pixelSize: Style.font.caption }
                                    Rectangle {
                                        visible: modelData.views_delta > 0
                                        height: Style.space(14)
                                        width: viewsDeltaText.implicitWidth + 6
                                        radius: 3
                                        color: Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.25)
                                        Text { textFormat: Text.PlainText;
                                            id: viewsDeltaText
                                            anchors.centerIn: parent
                                            text: "+" + modelData.views_delta
                                            color: Color.accent
                                            font.pixelSize: Style.font.caption - 2
                                            font.bold: true
                                        }
                                    }
                                }

                                // Downloads
                                Row {
                                    spacing: Style.space(4)
                                    Text { textFormat: Text.PlainText; text: "📥 Copies:"; color: Color.foreground; opacity: 0.6; font.pixelSize: Style.font.caption }
                                    Text { textFormat: Text.PlainText; text: String(modelData.downloads); color: Color.foreground; font.bold: true; font.pixelSize: Style.font.caption }
                                    Rectangle {
                                        visible: modelData.downloads_delta > 0
                                        height: Style.space(14)
                                        width: dlDeltaText.implicitWidth + 6
                                        radius: 3
                                        color: Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.25)
                                        Text { textFormat: Text.PlainText;
                                            id: dlDeltaText
                                            anchors.centerIn: parent
                                            text: "+" + modelData.downloads_delta
                                            color: Color.accent
                                            font.pixelSize: Style.font.caption - 2
                                            font.bold: true
                                        }
                                    }
                                }

                                // Hearts
                                Row {
                                    spacing: Style.space(4)
                                    Text { textFormat: Text.PlainText; text: "❤️ Hearts:"; color: Color.foreground; opacity: 0.6; font.pixelSize: Style.font.caption }
                                    Text { textFormat: Text.PlainText; text: String(modelData.hearts); color: Color.foreground; font.bold: true; font.pixelSize: Style.font.caption }
                                }

                                // Stars
                                Row {
                                    spacing: Style.space(4)
                                    Text { textFormat: Text.PlainText; text: "⭐ GH Stars:"; color: Color.foreground; opacity: 0.6; font.pixelSize: Style.font.caption }
                                    Text { textFormat: Text.PlainText; text: String(modelData.stars); color: Color.foreground; font.bold: true; font.pixelSize: Style.font.caption }
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
