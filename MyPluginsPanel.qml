import QtQuick
import QtQuick.Controls as Controls
import Quickshell
import "native/Commons"
import "native/Ui" as Ui
import "I18n.js" as I18n

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
    property bool showHistory: false
    // Settings page (gear in the header). Back with the button, Backspace or Esc.
    property bool settingsOpen: false
    readonly property string lang: hostWidget ? hostWidget.lang : "en"
    readonly property string languageSetting: hostWidget ? hostWidget.languageSetting : "auto"
    readonly property string systemLang: hostWidget ? hostWidget.systemLang : "en"
    function t(key, args) { return I18n.tr(lang, key, args) }
    function tn(key, n, args) { return I18n.trn(lang, key, n, args) }
    onSettingsOpenChanged: { panelScroll.contentY = 0; if (settingsOpen) showHistory = false; content.forceActiveFocus() }
    // Without an account there is nothing to show: start on the settings page.
    onNeedsAccountChanged: if (needsAccount) settingsOpen = true
    function back() { if (settingsOpen) settingsOpen = false; else showHistory = false; content.forceActiveFocus() }
    property bool confirmClearHistory: false
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
    signal clearHistoryRequested(string plugin, string metric, string range)
    signal pasteRequested()
    function pasteIntoAccount(text) { accountField.insert(text) }

    function reloadHistory() { historyRequested(historyPlugin, historyMetric, historyRange) }
    onOpenedChanged: if (opened) { reloadHistory(); if (needsAccount) settingsOpen = true } else { showHistory = false; settingsOpen = false }
    onShowHistoryChanged: { panelScroll.contentY = 0; confirmClearHistory = false; if (showHistory) reloadHistory() }

    function formatTime(isoString) {
        if (!isoString) return t("never")
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
                // Esc and Backspace leave the history or settings page first (text fields keep their own Backspace).
                Keys.onEscapePressed: { if (root.showHistory || root.settingsOpen) root.back(); else root.close() }
                Keys.onPressed: function(event) {
                    if (event.key === Qt.Key_Backspace && (root.showHistory || root.settingsOpen)) { root.back(); event.accepted = true }
                }

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
                                        text: root.author ? "@" + root.author + " ✎" : root.t("setAccount") + " ✎"
                                        color: Color.accent
                                        font.family: Style.font.family
                                        font.pixelSize: Style.font.caption - 1
                                        font.bold: true
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: root.settingsOpen = true }
                                }
                                }
                            }
                            Text { textFormat: Text.PlainText;
                                text: root.t("subtitle")
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
                            text: root.isQuerying ? root.t("checking") : "↻ " + root.t("refresh")
                            fontSize: Style.font.caption
                            bordered: true
                            focusable: true
                            enabled: !root.isQuerying
                            onClicked: root.refreshRequested()
                        }

                        Ui.Button {
                            visible: !root.settingsOpen
                            implicitHeight: Style.space(26)
                            text: "\udb81\udc93"
                            fontSize: Style.font.caption
                            bordered: true
                            focusable: true
                            tooltipText: root.t("settings")
                            onClicked: root.settingsOpen = true
                        }
                    }
                }

                // Settings page: language, check interval, GitHub account.
                Column {
                    width: parent.width
                    spacing: Style.space(12)
                    visible: root.settingsOpen
                    Row {
                        spacing: Style.space(12)
                        Ui.Button { focusable: true; bordered: true; iconText: "\udb80\udc4d"; text: root.t("back") + " · \u232b"; tooltipText: root.t("backTip"); onClicked: root.back(); anchors.verticalCenter: parent.verticalCenter }
                        Text { textFormat: Text.PlainText; text: root.t("settings").toUpperCase(); color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.caption; font.bold: true; font.letterSpacing: 1; anchors.verticalCenter: parent.verticalCenter }
                    }
                    Ui.PanelSeparator { width: parent.width }
                    Row {
                        spacing: Style.space(10)
                        Text { id: languageLabel; textFormat: Text.PlainText; width: Style.space(90); text: root.t("language"); color: Color.foreground; opacity: 0.8; font.family: Style.font.family; font.pixelSize: Style.font.caption; anchors.verticalCenter: parent.verticalCenter }
                        CompactDropdown {
                            id: languagePicker
                            anchors.verticalCenter: parent.verticalCenter
                            showLabel: false
                            // Wide enough for the longest option, plus padding and the chevron.
                            width: fitWidth
                            fontSize: Style.font.caption
                            rowHeight: languageLabel.implicitHeight + Style.space(6)
                            popupRowHeight: languageLabel.implicitHeight + Style.space(8)
                            options: [{ value: "auto", label: root.t("systemLanguage", [I18n.languageName(root.systemLang)]) }]
                                .concat(I18n.LANGUAGES.map(function(l) { return { value: l.code, label: l.name } }))
                            value: root.languageSetting
                            // Picking cuts the value binding inside the dropdown; restore it.
                            onChanged: function(picked) {
                                if (root.hostWidget) root.hostWidget.setLanguage(picked)
                                languagePicker.value = Qt.binding(function() { return root.languageSetting })
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
                                    text: root.t("interval")
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

                        }
                    }
                    // GitHub account whose marketplace plugins are shown
                    Rectangle {
                        width: parent.width
                        height: accountColumn.implicitHeight + Style.space(16)
                        radius: (Style.cornerRadius > 0 ? Style.cornerRadius : 6)
                        color: Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.08)
                        border.width: 1
                        border.color: Color.accent
                        Column {
                            id: accountColumn
                            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: Style.space(8)
                            spacing: Style.space(6)
                            Text { textFormat: Text.PlainText; width: parent.width; text: root.t("githubAccount"); color: Color.accent; font.family: Style.font.family; font.pixelSize: Style.font.body; font.bold: true }
                            Text { width: parent.width; wrapMode: Text.Wrap; textFormat: Text.PlainText; text: root.t("accountHelp"); color: Color.foreground; opacity: 0.8; font.family: Style.font.family; font.pixelSize: Style.font.caption }
                            Row {
                                width: parent.width; spacing: Style.space(6)
                                Ui.TextField { id: accountField; pasteHandler: function(field) { root.pasteRequested() }; width: parent.width - saveAccount.width - Style.space(6); text: root.author; placeholderText: root.t("accountPlaceholder"); onAccepted: root.accountSubmitted(text.trim()) }
                                Ui.Button { id: saveAccount; focusable: true; bordered: true; text: root.t("save"); onClicked: root.accountSubmitted(accountField.text.trim()) }
                            }
                            Text { width: parent.width; visible: root.author !== "" && root.accountSource !== "" && root.accountSource !== "settings"; wrapMode: Text.Wrap; textFormat: Text.PlainText; text: root.t("usingDetected", [root.author, root.accountSource]); color: Color.foreground; opacity: 0.8; font.family: Style.font.family; font.pixelSize: Style.font.caption }
                            Text { width: parent.width; visible: root.accountMessage !== ""; wrapMode: Text.Wrap; textFormat: Text.PlainText; text: root.hostWidget ? root.hostWidget.msgText(root.accountMessage) : root.accountMessage; color: Color.accent; font.family: Style.font.family; font.pixelSize: Style.font.caption }
                        }
                    }

                }

                // Changes Notification Banner (if changes detected)
                // Main page
                Column {
                    width: parent.width
                    spacing: Style.space(12)
                    visible: !root.showHistory && !root.settingsOpen
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
                                        text: root.t("newUpdates")
                                        color: Color.accent
                                        font.pixelSize: Style.font.body
                                        anchors.verticalCenter: parent.verticalCenter
                                    }
                                }

                                Ui.Button {
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    implicitHeight: Style.space(22)
                                    text: "✓ " + root.t("markRead")
                                    fontSize: Style.font.caption
                                    bordered: true
                                    focusable: true
                                    onClicked: root.acknowledgeRequested()
                                }
                            }

                            Text { textFormat: Text.PlainText;
                                width: parent.width
                                text: root.changesSummary !== "" ? root.changesSummary : root.t("metricsUpdated")
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
                                    text: "👁 " + root.t("views")
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
                                    text: "📥 " + root.t("downloads")
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
                                    text: "❤️ " + root.t("hearts")
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
                                    text: "⭐ " + root.t("ghStars")
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

                    Text { textFormat: Text.PlainText; anchors.right: parent.right
                        text: root.t("updatedAt", [root.formatTime(root.lastUpdatedText)]); color: Color.foreground; opacity: 0.55; font.pixelSize: Style.font.caption }
                    Ui.Button { focusable: true; width: parent.width; bordered: true; text: "📈  " + root.t("historyButton"); onClicked: root.showHistory = true }

                    // History of views, downloads, hearts and stars

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
                                text: root.t("sort")
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
                                    { value: "views", label: "👁 " + root.t("views") },
                                    { value: "downloads", label: "📥 " + root.t("downloads") },
                                    { value: "hearts", label: "❤️ " + root.t("hearts") },
                                    { value: "stars", label: "⭐ " + root.t("githubStars") },
                                    { value: "name", label: "🔤 " + root.t("sortName") },
                                    { value: "date", label: "📅 " + root.t("sortDate") }
                                ]
                                onChanged: function(v) { root.sortChanged(v, root.sortOrder) }
                            }

                            Ui.Dropdown {
                                id: sortOrderDropdown
                                showLabel: false
                                width: Style.space(120)
                                value: root.sortOrder
                                options: [
                                    { value: "desc", label: "↓ " + root.t("descending") },
                                    { value: "asc", label: "↑ " + root.t("ascending") }
                                ]
                                onChanged: function(v) { root.sortChanged(root.sortBy, v) }
                            }
                        }
                    }

                    // Section Divider
                    Ui.PanelSectionHeader {
                        text: root.t("publishedBy", [root.author || "?", root.plugins.length])
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
                                text: root.t("colPublished").toUpperCase()
                                color: Color.foreground
                                opacity: 0.5
                                font.family: Style.font.family
                                font.pixelSize: Style.font.caption - 1
                                font.bold: true
                            }

                            Text { textFormat: Text.PlainText;
                                width: Style.space(150)
                                text: root.t("colPlugin").toUpperCase()
                                color: Color.foreground
                                opacity: 0.5
                                font.family: Style.font.family
                                font.pixelSize: Style.font.caption - 1
                                font.bold: true
                            }

                            Text { textFormat: Text.PlainText;
                                text: root.t("colStatus").toUpperCase()
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
                                                text: root.hostWidget ? root.hostWidget.statusName(modelData.status_code, modelData.status_text) : modelData.status_text
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
                                        Text { textFormat: Text.PlainText; text: "📦 " + root.t("ver") + ":"; color: Color.foreground; opacity: 0.6; font.pixelSize: Style.font.caption }
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
                                        Text { textFormat: Text.PlainText; text: "👁 " + root.t("views") + ":"; color: Color.foreground; opacity: 0.6; font.pixelSize: Style.font.caption }
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
                                        Text { textFormat: Text.PlainText; text: "📥 " + root.t("copies") + ":"; color: Color.foreground; opacity: 0.6; font.pixelSize: Style.font.caption }
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
                                        Text { textFormat: Text.PlainText; text: "❤️ " + root.t("hearts") + ":"; color: Color.foreground; opacity: 0.6; font.pixelSize: Style.font.caption }
                                        Text { textFormat: Text.PlainText; text: String(modelData.hearts); color: Color.foreground; font.bold: true; font.pixelSize: Style.font.caption }
                                    }

                                    // Stars
                                    Row {
                                        spacing: Style.space(4)
                                        Text { textFormat: Text.PlainText; text: "⭐ " + root.t("ghStars") + ":"; color: Color.foreground; opacity: 0.6; font.pixelSize: Style.font.caption }
                                        Text { textFormat: Text.PlainText; text: String(modelData.stars); color: Color.foreground; font.bold: true; font.pixelSize: Style.font.caption }
                                    }
                                }

                                // Quick Link Buttons
                                Row {
                                    width: parent.width
                                    spacing: Style.space(8)

                                    Ui.Button {
                                        implicitHeight: Style.space(22)
                                        text: "🛒 " + root.t("marketplace")
                                        fontSize: Style.font.caption - 1
                                        bordered: true
                                        focusable: true
                                        onClicked: root.openUrl(modelData.marketplace_url)
                                    }

                                    Ui.Button {
                                        implicitHeight: Style.space(22)
                                        text: "🐙 " + root.t("githubRepo")
                                        fontSize: Style.font.caption - 1
                                        bordered: true
                                        focusable: true
                                        onClicked: root.openUrl(modelData.repo_url)
                                    }

                                    Ui.Button {
                                        visible: modelData.issue_url !== null
                                        implicitHeight: Style.space(22)
                                        text: "📋 " + root.t("marketplaceIssue")
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
                // History page
                Column {
                    width: parent.width
                    spacing: Style.space(12)
                    visible: root.showHistory && !root.settingsOpen
                    Row {
                        spacing: Style.space(12)
                        Ui.Button { focusable: true; bordered: true; iconText: "\udb80\udc4d"; text: root.t("back") + " · \u232b"; tooltipText: root.t("backTip"); onClicked: root.back(); anchors.verticalCenter: parent.verticalCenter }
                        Text { textFormat: Text.PlainText; text: root.t("history").toUpperCase(); color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.caption; font.bold: true; font.letterSpacing: 1; anchors.verticalCenter: parent.verticalCenter }
                    }
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
                                Text { textFormat: Text.PlainText; text: "📈 " + root.t("history"); color: Color.accent; font.family: Style.font.family; font.pixelSize: Style.font.body; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                                Text { textFormat: Text.PlainText; anchors.verticalCenter: parent.verticalCenter; color: Color.foreground; opacity: 0.75; font.family: Style.font.family; font.pixelSize: Style.font.caption
                                       text: root.hoveredBar >= 0 && root.historyValues[root.hoveredBar] !== null
                                             ? root.t("hoverValue", [(root.history.labels || [])[root.hoveredBar], root.historyValues[root.hoveredBar], (root.history.totals || [])[root.hoveredBar]])
                                             : root.t("inRange", [root.historyGain]) }
                            }
                            Row {
                                width: parent.width; spacing: Style.space(6)
                                Ui.Dropdown { showLabel: false; width: (parent.width - Style.space(12)) / 3; value: root.historyMetric
                                    options: [{value: "views", label: "👁 " + root.t("views")}, {value: "downloads", label: "📥 " + root.t("downloads")}, {value: "hearts", label: "❤️ " + root.t("hearts")}, {value: "stars", label: "⭐ " + root.t("stars")}]
                                    onChanged: function(v) { root.historyMetric = v; root.reloadHistory() } }
                                Ui.Dropdown { showLabel: false; width: (parent.width - Style.space(12)) / 3; value: root.historyRange
                                    options: [{value: "daily", label: root.t("daily")}, {value: "weekly", label: root.t("weekly")}, {value: "monthly", label: root.t("monthly")}]
                                    onChanged: function(v) { root.historyRange = v; root.reloadHistory() } }
                                Ui.Dropdown { showLabel: false; width: (parent.width - Style.space(12)) / 3; value: root.historyPlugin
                                    options: [{value: "all", label: root.t("allPlugins")}].concat(root.plugins.map(function(p) { return {value: p.id, label: p.name} }))
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
                                   text: root.history.first_day ? root.t(root.historyRange === "daily" ? "gainsDay" : root.historyRange === "weekly" ? "gainsWeek" : "gainsMonth", [root.history.first_day])
                                                                : root.t("historyStarts") }
                        }
                    }
                    // Clear history, with an in-place confirmation
                    Ui.Button { focusable: true; visible: !root.confirmClearHistory; bordered: true; text: "🗑  " + root.t("clearHistory"); onClicked: root.confirmClearHistory = true }
                    Rectangle {
                        width: parent.width
                        visible: root.confirmClearHistory
                        height: visible ? confirmColumn.implicitHeight + Style.space(16) : 0
                        radius: (Style.cornerRadius > 0 ? Style.cornerRadius : 6)
                        color: Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.10)
                        border.width: 1
                        border.color: Color.accent
                        Column {
                            id: confirmColumn
                            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: Style.space(8)
                            spacing: Style.space(6)
                            Text { textFormat: Text.PlainText; width: parent.width; wrapMode: Text.Wrap; color: Color.foreground; font.family: Style.font.family; font.pixelSize: Style.font.caption
                                   text: root.history.first_day ? root.t("confirmClearSince", [root.history.first_day]) : root.t("confirmClear") }
                            Row {
                                spacing: Style.space(6)
                                Ui.Button { focusable: true; bordered: true; text: root.t("deleteHistory"); onClicked: { root.confirmClearHistory = false; root.clearHistoryRequested(root.historyPlugin, root.historyMetric, root.historyRange) } }
                                Ui.Button { focusable: true; bordered: true; text: root.t("cancel"); onClicked: root.confirmClearHistory = false }
                            }
                        }
                    }
                }
            }
        }
    }
}
