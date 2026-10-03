pragma ComponentBehavior: Bound
import QtQuick
import Quickshell
import Quickshell.Io
import "native/Commons"
import qs.Commons as Theme
import "native/Ui" as Ui
import qs.Ui as ShellUi

ShellUi.BarWidget {
    id: root
    moduleName: "ubruckhaus.my-plugins"

    property bool opened: panel.opened
    property bool popoutSwitchClosing: panel.popoutSwitchClosing

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

    property var pendingRequests: []
    property var currentRequest: null

    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight

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
            if (data.status === "ok") {
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
            }
        } catch (e) {
            console.warn("My Plugins: Failed to parse backend response", e)
        }
    }

    function setIntervalMinutes(m) {
        root.intervalMinutes = m
        request({command: "configure", settings: {interval_minutes: m}})
    }

    function acknowledgeChanges() {
        root.hasChanges = false
        request({command: "acknowledge"})
    }

    function openExternalUrl(url) {
        request({command: "open_url", url: url})
    }

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
        plugins: root.plugins
        totalViews: root.totalViews
        totalDownloads: root.totalDownloads
        totalHearts: root.totalHearts
        totalStars: root.totalStars
        hasChanges: root.hasChanges
        changesSummary: root.changesSummary
        intervalMinutes: root.intervalMinutes
        lastUpdatedText: root.lastUpdatedText
        isQuerying: root.isQuerying

        onRefreshRequested: root.request({command: "query"})
        onAcknowledgeRequested: root.acknowledgeChanges()
        onIntervalSelected: function(m) { root.setIntervalMinutes(m) }
        onOpenUrl: function(url) { root.openExternalUrl(url) }
    }

    // Bar button
    ShellUi.BarIconButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        active: root.opened || root.hasChanges

        tooltipText: {
            var prefix = "My Plugins · Marketplace Monitor\n"
            if (root.hasChanges) {
                return prefix + "⚡ New updates detected!\n" + (root.changesSummary !== "" ? root.changesSummary : "Metrics changed") + "\nClick to open · Right-click to refresh"
            }
            var stats = root.totalViews + " views · " + root.totalDownloads + " downloads · " + root.totalStars + " stars\n"
            var timer = "Interval: " + root.intervalMinutes + "m · Click to open · Right-click to refresh"
            return prefix + stats + timer
        }

        iconComponent: Component {
            Item {
                id: iconContainer
                anchors.fill: parent

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
                    color: Theme.Color.accent
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
