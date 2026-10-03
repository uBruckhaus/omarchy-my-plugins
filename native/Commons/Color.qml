pragma Singleton
import QtQuick
import qs.Commons as Shell

// Share the live Omarchy palette and surface borders; layout tokens stay local.
QtObject {
  readonly property color foreground: Shell.Color.foreground
  readonly property color background: Shell.Color.background
  readonly property color accent: Shell.Color.accent
  readonly property color urgent: Shell.Color.urgent
  readonly property color muted: Shell.Color.muted
  readonly property var shellValues: Shell.Color.shellValues
  readonly property QtObject bar: Shell.Color.bar
  readonly property QtObject popups: Shell.Color.popups
  readonly property QtObject tooltip: Shell.Color.tooltip
}
