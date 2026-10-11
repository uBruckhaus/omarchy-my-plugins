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
- **🚫 Published Only**:
  - Only plugins with marketplace stats or a `[Plugin]`/`[Verify]` marketplace issue are listed; locally installed, unpublished plugins (e.g. Pellet Stove) are hidden.
- **📦 Version Display**:
  - Each plugin card shows its current version from the installed manifest.
  - When the latest GitHub release differs, it is shown alongside (e.g. `v0.3.0 · GH v0.3.3`) so installed-vs-published drift is visible at a glance.
- **🎯 One-Click Deep Links**:
  - Jump directly to the plugin's Marketplace detail page (`https://plugins.omarchy.org/plugin.html?id=<plugin-id>`).
  - Open the GitHub repository.
  - Track review/submission progress directly in GitHub Marketplace verification issues (e.g. #9889 for Simple Recipes, #9826 for Workspace Presets).
- **🔒 Omarchy Security Baseline**:
  - Non-truncating lock file acquisition (`os.O_NOFOLLOW | os.O_CREAT | os.O_RDWR`, mode `0600`).
  - Secure `$XDG_RUNTIME_DIR` ownership and permissions verification.
  - Explicit argument vector (`argv`) subprocesses — no shell interpolation.
  - Zero background daemons: runs on-demand through Quickshell events.

---

## Which plugins are shown

Set your **GitHub account** (click the `@account ✎` badge in the popup): the owner of your plugin
repositories, e.g. `uBruckhaus` for `github.com/uBruckhaus/omarchy-theme-manager`. My Plugins lists
every plugin in the marketplace catalog whose repository belongs to that account, so any plugin
developer can use it. Leave the field empty to use the account `gh` is logged into.

Data sources: the marketplace catalog (`site/catalog.json` of `omacom/omarchy-plugin-marketplace`,
cached and refreshed at most hourly with ETag), the marketplace stats API (views, downloads, hearts),
GitHub (live stars) and your marketplace issues (review status). Every download has a size cap and
an overall deadline.

## History

Each refresh stores one snapshot per day (views, downloads, hearts and stars for every plugin) in
`~/.local/state/omarchy/my-plugins/history.json`, kept for 400 days. The **History** card shows the
gains per day (30 days), week (12 weeks) or month (12 months) for one plugin or all of them; hover a
bar for its value and running total. The marketplace keeps no history itself, so the chart starts on
the day My Plugins first runs.

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

# Set the GitHub account whose plugins are shown (empty: use the gh login)
python3 monitor.py --set-author uBruckhaus

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
