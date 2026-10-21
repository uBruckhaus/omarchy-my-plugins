pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import "native/Commons"
import "native/Commons" as Commons
import "native/Ui" as Ui
import qs.Ui as ShellUi
import "I18n.js" as I18n

ShellUi.BarWidget {
    id: root
    moduleName: "ubruckhaus.my-plugins"

    property bool opened: panel.opened
    property bool popoutSwitchClosing: panel.popoutSwitchClosing

    // Interface language: the system's unless one is picked in the panel's
    // settings (stored in this widget's own shell.json entry).
    readonly property string systemLang: I18n.systemLanguage(Quickshell.env("LC_ALL"), Quickshell.env("LC_MESSAGES"), Quickshell.env("LANG"))
    readonly property string languageSetting: String(root.setting("language", "auto"))
    readonly property string lang: I18n.resolve(languageSetting, systemLang)
    function t(key, args) { return I18n.tr(lang, key, args) }
    function tn(key, n, args) { return I18n.trn(lang, key, n, args) }
    function setLanguage(code) {
      if (!root.bar || !root.bar.shell || typeof root.bar.shell.updateEntryInline !== "function") return
      var next = Object.assign({}, root.settings || {})
      if (code === "auto") delete next.language
      else next.language = code
      root.bar.shell.updateEntryInline(root.moduleName, next)
    }

    // Panel height dragged by the user (0 = fit the content); the width stays fixed.
    readonly property int panelHeight: Number(root.setting("panel_height", 0)) || 0
    function setPanelHeight(h) {
      if (!root.bar || !root.bar.shell || typeof root.bar.shell.updateEntryInline !== "function") return
      var next = Object.assign({}, root.settings || {})
      if (h > 0) next.panel_height = Math.round(h)
      else delete next.panel_height
      root.bar.shell.updateEntryInline(root.moduleName, next)
    }

    // A helper message code (translated here) or plain text from an older helper.
    function msgText(m) { return m && I18n.STRINGS.en[m] !== undefined ? t(m) : String(m || "") }
    function statusName(code, fallback) {
        var key = { published: "stPublished", verified: "stVerified", needs_fixes: "stNeedsFixes", review: "stReview",
                    pending: "stPending", open: "stOpen", listed: "stListed" }[code]
        return key ? t(key) : String(fallback || code || "")
    }
    // What changed since the last "Mark as read", built from the per-plugin deltas.
    readonly property string changesText: {
        var lines = []
        for (var i = 0; i < plugins.length; i++) {
            var p = plugins[i]
            if (!p.has_changes) continue
            var parts = []
            if (p.views_delta > 0) parts.push(t("chViews", [p.views_delta]))
            if (p.downloads_delta > 0) parts.push(t("chDownloads", [p.downloads_delta]))
            if (p.hearts_delta > 0) parts.push("+" + p.hearts_delta + " ❤️")
            if (p.stars_delta > 0) parts.push("+" + p.stars_delta + " ⭐")
            if (p.status_changed) parts.push(t("chStatus", [statusName(p.status_code, p.status_text)]))
            lines.push(p.name + ": " + parts.join(", "))
        }
        return lines.join("; ")
    }

    property string author: ""
    property bool needsAccount: false
    property string accountMessage: ""
    property string accountSource: ""
    property var history: ({})
    property var historyRequest: ({plugin: "all", metric: "views", range: "daily"})
    property int intervalMinutes: Math.max(1, Number(setting("intervalMinutes", 5)) || 5)
    property var plugins: []
    property int totalViews: 0
    property int totalDownloads: 0
    property int totalHearts: 0
    property int totalStars: 0
    property bool hasChanges: false
    property string changesSummary: ""
    property string lastUpdatedText: ""
    property bool isQuerying: false
    property string sortBy: "views"
    property string sortOrder: "desc"

    property var pendingRequests: []
    property var currentRequest: null

    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight

    IpcHandler {
        target: "ubruckhaus.my-plugins"
        function toggle(): void { root.togglePanel() }
        function open(): void { panel.open() }
        function close(): void { panel.close() }
        function refresh(): void { root.request({command: "query"}) }
        function acknowledge(): void { root.acknowledgeChanges() }
        function setAuthor(authorName: string): void { root.request({command: "set_author", author: authorName}) }
    }

    function helperScriptPath() {
        return decodeURIComponent(Qt.resolvedUrl("monitor.py").toString().replace(/^file:\/\//, ""))
    }

    function request(payload) {
        if (payload.command === "query") {
            isQuerying = true
        }
        pendingRequests = pendingRequests.concat([payload])
        processNextRequest()
    }

    function processNextRequest() {
        if (worker.running || pendingRequests.length === 0) return
        currentRequest = pendingRequests[0]
        pendingRequests = pendingRequests.slice(1)
        worker.running = true
    }

    function acceptResponse(text) {
        isQuerying = false
        try {
            var data = JSON.parse(text)
            if (data.needs_account) {
                root.needsAccount = true
                root.accountMessage = data.message_code || data.message || ""
                return
            }
            if (data.status === "error") {
                root.accountMessage = data.message_code || data.message || "requestFailed"
                return
            }
            if (currentRequest && currentRequest.command === "paste") {
                if (data.clipboard) panel.pasteIntoAccount(data.clipboard)
                return
            }
            if (data.status === "ok" && data.labels !== undefined) {
                root.history = data
                return
            }
            if (data.status === "ok" && data.plugins !== undefined) {
                root.needsAccount = false
                root.accountMessage = ""
                // New numbers arrived: refresh the chart for the current selection.
                if (panel.opened && currentRequest && currentRequest.command !== "history") Qt.callLater(root.requestHistory)
            }
            if (data.status === "ok") {
                if (data.author !== undefined) root.author = data.author
                if (data.account_source !== undefined) root.accountSource = data.account_source
                if (data.plugins !== undefined) root.plugins = data.plugins
                if (data.total_views !== undefined) root.totalViews = data.total_views
                if (data.total_downloads !== undefined) root.totalDownloads = data.total_downloads
                if (data.total_hearts !== undefined) root.totalHearts = data.total_hearts
                if (data.total_stars !== undefined) root.totalStars = data.total_stars
                if (data.has_changes !== undefined) root.hasChanges = data.has_changes
                if (data.changes_summary !== undefined) root.changesSummary = data.changes_summary
                if (data.last_updated !== undefined) root.lastUpdatedText = data.last_updated
                if (data.interval_minutes !== undefined && data.interval_minutes !== root.intervalMinutes) {
                    root.intervalMinutes = data.interval_minutes
                }
                if (data.sort_by !== undefined && data.sort_by !== root.sortBy) {
                    root.sortBy = data.sort_by
                }
                if (data.sort_order !== undefined && data.sort_order !== root.sortOrder) {
                    root.sortOrder = data.sort_order
                }
            }
        } catch (e) {
            console.warn("My Plugins: Failed to parse backend response", e)
        }
    }

    function setIntervalMinutes(m) {
        root.intervalMinutes = m
        request({command: "configure", settings: {interval_minutes: m}})
    }

    function setSort(by, order) {
        if (by) root.sortBy = by
        if (order) root.sortOrder = order
        request({command: "configure", settings: {sort_by: by, sort_order: order}})
    }

    function acknowledgeChanges() {
        root.hasChanges = false
        request({command: "acknowledge"})
    }

    function requestHistory(plugin, metric, range) {
        if (plugin !== undefined) root.historyRequest = {plugin: plugin, metric: metric, range: range}
        request(Object.assign({command: "history"}, root.historyRequest))
    }

    function setAccount(name) {
        root.accountMessage = ""
        request({command: "set_author", author: name})
    }

    function openExternalUrl(url) {
        request({command: "open_url", url: url})
    }

    // PopupCard (outside click) and the bar's popout coordinator call these
    // on the owner (this widget); without them panel.opened gets stuck true.
    function close() { panel.close() }
    function closeForPopoutSwitch() { panel.closeForPopoutSwitch() }

    function togglePanel() {
        if (panel.opened) {
            panel.close()
        } else {
            panel.open()
        }
    }

    Component.onCompleted: {
        // Initial quick status read
        request({command: "status"})
    }

    // Polling timer
    Timer {
        id: pollTimer
        interval: Math.max(1, root.intervalMinutes) * 60 * 1000
        repeat: true
        running: true
        onTriggered: {
            root.request({command: "query"})
        }
    }

    // Backend process
    Process {
        id: worker
        command: ["python3", root.helperScriptPath()]
        stdinEnabled: true
        onStarted: {
            if (root.currentRequest) {
                write(JSON.stringify(root.currentRequest) + "\n")
            }
        }
        stdout: StdioCollector {
            onStreamFinished: {
                root.acceptResponse(text)
            }
        }
        onExited: {
            Qt.callLater(root.processNextRequest)
        }
    }

    // Popup Panel
    MyPluginsPanel {
        id: panel
        bar: root.bar
        anchorItem: button
        hostWidget: root
        author: root.author
        plugins: root.plugins
        totalViews: root.totalViews
        totalDownloads: root.totalDownloads
        totalHearts: root.totalHearts
        totalStars: root.totalStars
        hasChanges: root.hasChanges
        changesSummary: root.changesText
        intervalMinutes: root.intervalMinutes
        lastUpdatedText: root.lastUpdatedText
        isQuerying: root.isQuerying
        sortBy: root.sortBy
        sortOrder: root.sortOrder
        needsAccount: root.needsAccount
        accountMessage: root.accountMessage
        accountSource: root.accountSource
        history: root.history

        onRefreshRequested: root.request({command: "query"})
        onAcknowledgeRequested: root.acknowledgeChanges()
        onIntervalSelected: function(m) { root.setIntervalMinutes(m) }
        onSortChanged: function(by, order) { root.setSort(by, order) }
        onOpenUrl: function(url) { root.openExternalUrl(url) }
        onAccountSubmitted: function(name) { root.setAccount(name) }
        onHistoryRequested: function(plugin, metric, range) { root.requestHistory(plugin, metric, range) }
        onPasteRequested: root.request({command: "paste"})
        onClearHistoryRequested: function(plugin, metric, range) { root.request({command: "clear_history", plugin: plugin, metric: metric, range: range}) }
    }

    // Bar button
    ShellUi.BarIconButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        active: root.opened || root.hasChanges

        tooltipText: {
            var prefix = "My Plugins · " + (root.author ? "@" + root.author : root.t("noAccount")) + " · " + root.t("marketplaceMonitor") + "\n"
            if (root.hasChanges) {
                return prefix + "⚡ " + root.t("newUpdates") + "\n" + (root.changesText !== "" ? root.changesText : root.t("metricsChanged")) + "\n" + root.t("clickOpenRefresh")
            }
            var stats = root.t("tipStats", [root.totalViews, root.totalDownloads, root.totalStars]) + "\n"
            var timer = root.t("tipInterval", [root.intervalMinutes]) + " · " + root.t("clickOpenRefresh")
            return prefix + stats + timer
        }

        iconComponent: Component {
            // No anchors: the bar sizes this item (Omarchy 4.5 loads it into an
            // unsized Loader, so filling the parent would leave a 0×0 canvas).
            Item {
                id: iconContainer

                Canvas {
                    id: iconCanvas
                    anchors.fill: parent
                    property color ink: button.foreground
                    property bool changesActive: root.hasChanges

                    onInkChanged: requestPaint()
                    onWidthChanged: requestPaint()
                    onHeightChanged: requestPaint()
                    onChangesActiveChanged: requestPaint()

                    onPaint: {
                        var ctx = getContext("2d")
                        ctx.reset()
                        ctx.scale(width / 24, height / 24)
                        ctx.strokeStyle = ink
                        ctx.fillStyle = ink
                        ctx.lineWidth = 1.6
                        ctx.lineCap = "round"
                        ctx.lineJoin = "round"

                        // Storefront / Plugin modular grid icon:
                        // Upper left tile
                        ctx.strokeRect(3.5, 4, 6.5, 6.5)
                        // Upper right tile
                        ctx.strokeRect(14, 4, 6.5, 6.5)
                        // Lower left tile
                        ctx.strokeRect(3.5, 13.5, 6.5, 6.5)
                        // Lower right tile (solid filled module)
                        ctx.fillRect(14, 13.5, 6.5, 6.5)

                        // Central connecting crosshairs
                        ctx.beginPath()
                        ctx.moveTo(10, 7.2)
                        ctx.lineTo(14, 7.2)
                        ctx.moveTo(7.2, 10.5)
                        ctx.lineTo(7.2, 13.5)
                        ctx.stroke()
                    }
                }

                // Change Notification Dot (Top-Right)
                Rectangle {
                    id: changeDot
                    visible: root.hasChanges
                    width: 7
                    height: 7
                    radius: 3.5
                    color: Commons.Color.accent
                    anchors.top: parent.top
                    anchors.right: parent.right
                    anchors.topMargin: 1
                    anchors.rightMargin: 1

                    // Subtle pulse animation to draw friendly attention
                    SequentialAnimation on opacity {
                        running: root.hasChanges
                        loops: Animation.Infinite
                        NumberAnimation { from: 1.0; to: 0.35; duration: 900; easing.type: Easing.InOutQuad }
                        NumberAnimation { from: 0.35; to: 1.0; duration: 900; easing.type: Easing.InOutQuad }
                    }
                }
            }
        }

        onPressed: function(mouseButton) {
            if (mouseButton === Qt.RightButton) {
                root.request({command: "query"})
            } else {
                root.togglePanel()
            }
        }
    }
}
