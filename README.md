# My Plugins — Omarchy Plugin Marketplace Monitor

A bar widget for Omarchy plugin developers. It finds your published plugins in the
[Omarchy Plugin Marketplace](https://plugins.omarchy.org/) by your GitHub account and shows their
views, downloads, hearts and GitHub stars, their review status, and a daily, weekly or monthly
history chart. A pulsing dot on the bar icon tells you when something changed.

## Languages and settings

The interface is built in in eight languages: English, German (Deutsch), French (Français), Spanish (Español), Italian (Italiano), Portuguese (Português), Dutch (Nederlands) and Polish (Polski). It follows the system language (`LC_ALL`, `LC_MESSAGES`, `LANG`) and falls back to English. To pick another one, open the **gear (⚙)** at the top right of the panel → **Language**. The translations ship with the plugin: nothing is downloaded or generated, and the plugin makes no extra requests for them. The choice is stored in the widget's own entry in `~/.config/omarchy/shell.json` (`"language"`); **System (…)** removes it again.

The settings page opens from the gear and closes with **← Back**, Backspace or Esc. It also holds the **check interval** and the **GitHub account** whose plugins are shown, which used to be in the main panel. The history page has the same **← Back** header.

The **ⓘ** button beside the gear opens an **Information** page with a card for each of the author's other plugins in the Omarchy Plugin Marketplace, with a short description in the panel's language. A click on a card opens that plugin's marketplace page in the browser (a fixed `https://plugins.omarchy.org/plugin.html?id=…` address); nothing is downloaded. **← Back**, Backspace or Esc returns. The refresh button in the header is now a symbol (↻; an hourglass while a check runs), like the gear.

## Install

```sh
omarchy plugin add https://github.com/uBruckhaus/omarchy-my-plugins.git
omarchy plugin enable ubruckhaus.my-plugins
```

On first start My Plugins detects your GitHub account on this computer (the `gh` login, `git config
github.user`, a GitHub no-reply e-mail, or your installed plugin checkouts) and shows where it came
from; click the `@account ✎` badge to change it.

**Requirements:** `python3` (standard library only). Optional: the GitHub CLI `gh`, logged in, for
review status and live star counts; without it, stars come from the daily marketplace catalog and no
review status is shown.

## Remove

```sh
omarchy plugin disable ubruckhaus.my-plugins
omarchy plugin remove ubruckhaus.my-plugins
rm -r ~/.config/omarchy/my-plugins ~/.local/state/omarchy/my-plugins   # settings, cache and history (optional)
```

## Privacy and network

My Plugins only reads public data: the marketplace catalog
(`raw.githubusercontent.com/omacom/omarchy-plugin-marketplace/main/site/catalog.json`, cached and
re-checked at most hourly), the marketplace stats API (`api.omarchyplugins.com/v1/stats`) and, through
your own `gh` login, your repositories and your marketplace issues. Every download and helper output has
a size cap and an overall deadline, redirects are refused, and links open only for `github.com` and
`plugins.omarchy.org`. Nothing is sent anywhere; settings, the catalog cache and the history stay in
`~/.config/omarchy/my-plugins` and `~/.local/state/omarchy/my-plugins`.

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
  - Only plugins listed in the marketplace catalog under your GitHub account are shown.
- **📦 Version Display**:
  - Each plugin card shows the version currently published in the marketplace.
- **🎯 One-Click Deep Links**:
  - Jump directly to the plugin's Marketplace detail page (`https://plugins.omarchy.org/plugin.html?id=<plugin-id>`).
  - Open the GitHub repository.
  - Open the plugin's latest marketplace issue to follow a review.
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
`~/.local/state/omarchy/my-plugins/history.json`, kept for 400 days. The **📈 History** page (button on the main page; Backspace or Back returns) shows the
gains per day (30 days), week (12 weeks) or month (12 months) for one plugin or all of them; hover a
bar for its value and running total. The marketplace keeps no history itself, so the chart starts on
the day My Plugins first runs.

## Bar Icon & Controls

- **Left-Click Bar Icon**: Toggles the stats panel open or closed.
- **Right-Click Bar Icon**: Triggers an immediate refresh query.
- **Bar Icon Dot**: Appears and pulses in `Color.accent` whenever new views, downloads, stars, or status updates occur since the last check.
- **Mark as Read**: Clicking "✓ Mark as Read" in the panel or opening the panel acknowledges recent updates and resets the icon badge.
- **Panel Height**: Drag the grip on the panel edge away from the bar to make the panel taller or shorter (the width stays fixed). The height is remembered; double-click the grip to fit the content again.

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
