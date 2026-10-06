# My Plugins — Omarchy Plugin Marketplace Monitor

A native Omarchy desktop shell bar widget and panel that monitors your published Omarchy plugins. Tracks live marketplace engagement metrics (views, command-copy downloads, hearts), GitHub repository stars, and publication/verification review statuses from the official [Omarchy Plugin Marketplace](https://plugins.omarchy.org/).

> [!NOTE]
> **Private Plugin**: This is a local author-monitoring plugin created specifically for your workflow. It is **not** published to the marketplace.

---

## Features

- **📊 Live Engagement Metrics**:
  - **Marketplace Views**: Exact page views for each listed plugin via `api.omarchyplugins.com`.
  - **Downloads (Command Copies)**: Successful install command copies from the marketplace directory.
  - **Hearts**: Anonymous marketplace reactions.
  - **GitHub Stars**: Real-time stargazer counts from your GitHub repositories.
- **⚡ Status & Change Detection**:
  - Automatically compares queries against your last acknowledged snapshot.
  - Indicates changes with a distinct pulsing theme-accent dot on the bar icon.
  - Bar tooltip displays real-time change summaries (e.g. `▲ +15 views, +2 downloads`).
  - Panel highlights new activity with delta pills and an acknowledgment action.
- **⏱ Configurable Query Interval**:
  - Query frequency configurable in minutes: `1m`, `2m`, `5m`, `10m`, `15m`, `30m`, `60m`.
  - Default: **5 minutes**.
  - Adjust anytime directly from the panel or CLI.
- **↕ Sortable Plugin List**:
  - Sort the plugin list by **Views**, **Downloads**, **Hearts**, **GitHub Stars**, **Name**, or **Publish Date**.
  - Each with **Ascending** or **Descending** order.
  - Default: **Views, Descending**.
  - Adjust anytime directly from the panel dropdowns or CLI.
- **📦 Version Display**:
  - Each plugin card shows its current version from the installed manifest.
  - When the latest GitHub release differs, it is shown alongside (e.g. `v0.3.0 · GH v0.3.3`) so installed-vs-published drift is visible at a glance.
- **🎯 One-Click Deep Links**:
  - Jump directly to the Marketplace listing (`https://plugins.omarchy.org/#<plugin>`).
  - Open the GitHub repository.
  - Track review/submission progress directly in GitHub Marketplace verification issues (e.g. #9889 for Simple Recipes, #9826 for Simple Tile).
- **🔒 Omarchy Security Baseline**:
  - Non-truncating lock file acquisition (`os.O_NOFOLLOW | os.O_CREAT | os.O_RDWR`, mode `0600`).
  - Secure `$XDG_RUNTIME_DIR` ownership and permissions verification.
  - Explicit argument vector (`argv`) subprocesses — no shell interpolation.
  - Zero background daemons: runs on-demand through Quickshell events.

---

## Monitored Plugins Matrix

| Plugin | ID | Default Category | Repository | Initial Publication State |
| :--- | :--- | :--- | :--- | :--- |
| **Simple Launcher** | `ubruckhaus.simple-launcher-for-fools` | Desktop | `uBruckhaus/omarchy-simple-launcher-for-fools` | Listed & Verified (Issue #8539) |
| **Simple Tile** | `ubruckhaus.simple-tile` | Desktop | `uBruckhaus/omarchy-simple-tile` | Listed & Verified (Issue #9826) |
| **Video Trans** | `ubruckhaus.video-trans` | Media | `uBruckhaus/omarchy-video-trans` | Listed & Verified (Issue #9467) |
| **Simple Reader** | `ubruckhaus.simple-reader` | Accessibility | `uBruckhaus/omarchy-simple-reader` | Listed & Verified (Issue #9489) |
| **Simple Recipes** | `ubruckhaus.simple-recipes` | Productivity | `uBruckhaus/omarchy-simple-recipes` | Review: Needs Fixes (Issue #9889) |

---

## Bar Icon & Controls

- **Left-Click Bar Icon**: Toggles the stats panel open or closed.
- **Right-Click Bar Icon**: Triggers an immediate refresh query.
- **Bar Icon Dot**: Appears and pulses in `Color.accent` whenever new views, downloads, stars, or status updates occur since the last check.
- **Mark as Read**: Clicking "✓ Mark as Read" in the panel or opening the panel acknowledges recent updates and resets the icon badge.

---

## CLI Usage

The backend helper can be executed directly from terminal:

```bash
# Perform immediate query and output formatted JSON
python3 monitor.py --query

# Read cached status without re-querying
python3 monitor.py --status

# Acknowledge current deltas / clear changes
python3 monitor.py --acknowledge

# Change polling interval (e.g. to 10 minutes)
python3 monitor.py --set-interval 10

# Change plugin list sorting (field: views|downloads|hearts|stars|name|date, order: asc|desc)
python3 monitor.py --set-sort views desc
```

The default sort order is **views, descending** — the plugin list is always ordered by the configured field.

---

## Running Unit Tests

```bash
python3 -m unittest discover -s tests -v
```

---

## License

MIT License (c) 2026 Uwe Bruckhaus
