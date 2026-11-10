# My Plugins — Omarchy Plugin Marketplace Monitor

A bar widget for Omarchy plugin developers. It finds your published plugins in the
[Omarchy Plugin Marketplace](https://plugins.omarchy.org/) by your GitHub account and shows their
views, downloads, hearts and GitHub stars, their review status, and a daily, weekly or monthly
history chart. A pulsing dot on the bar icon tells you when something changed.

## Languages and settings

The interface is built in in eight languages: English, German (Deutsch), French (Français), Spanish (Español), Italian (Italiano), Portuguese (Português), Dutch (Nederlands) and Polish (Polski). It follows the system language (`LC_ALL`, `LC_MESSAGES`, `LANG`) and falls back to English. To pick another one, open the **gear (⚙)** at the top right of the panel → **Language**. The translations ship with the plugin: nothing is downloaded or generated, and the plugin makes no extra requests for them. The choice is stored in the widget's own entry in `~/.config/omarchy/shell.json` (`"language"`); **System (…)** removes it again.

The settings page opens from the gear and closes with **← Back**, Backspace or Esc. Besides **Language** it has:

- **Corners:** *Like windows (… px)* (the default) follows Hyprland's window rounding (`decoration:rounding`, as the shell reads it), *Slightly rounded (6 px)*, *Rounded (12 px)* or *Square*. This panel draws its own frame, so the setting rounds all of it: the frame, tool tips, drop-down lists and the cards (banner, totals, sort, history, settings and plugin cards) at the full radius; buttons, drop-downs, the account field, the publish date badge and the note field at most 8 px; the +views/+downloads badges and the chart's bars at most 4 px; the account chip, the status pill, switches and the resize grip round, or square in *Square*. Only the bar icon keeps its own drawing. Stored as `"corners"` in the widget's entry in `~/.config/omarchy/shell.json`; *Like windows* removes it again.
- **F12 saves a screenshot** (on by default; stored as `"screenshotKey": false` when switched off, see below).
- The **check interval** and the **GitHub account** whose plugins are shown, which used to be in the main panel.

The history page has the same **← Back** header.

### F12: a screenshot of the panel, with a note

While the panel is open, **F12** (without Ctrl, Shift, Alt or Super) saves a picture of the panel, for telling what is wrong with it, as in the author's GTK apps:

- **Only on F12.** Nothing is captured at any other time, and only the panel itself: Qt draws the panel's own content into the picture (`grabToImage`). No screen capture tool runs, nothing else on the screen is in it, and nothing is uploaded or sent anywhere.
- **Where:** `~/Pictures/My Plugins/my-plugins-<date>-<time>.png` (the pictures folder from `~/.config/user-dirs.dirs` when it is set there). A panel then names the file and asks **What is wrong? (optional)**; **Enter** or **Done** saves the text next to the picture as a `.txt` with the same name (at most 4000 characters; no text, no file), **Esc** skips it, and closing the panel keeps what was typed.
- **Private files:** the folder is made `0700` when missing and only used when it is a real folder (not a link) of yours that no one else can write to; pictures and notes are new `0600` files, never written through a link or over an existing file (`-2`, `-3` … are added instead), and a picture that cannot be written completely is removed again.
- **How:** the panel first writes the picture into its own folder `$XDG_RUNTIME_DIR/ubruckhaus.my-plugins-shot/` (`0700`, in memory; used only when `$XDG_RUNTIME_DIR` itself is a real folder of yours that no one else can write to; a picture left there by a save that never ran is removed when the panel loads, or before the next screenshot, once it is two minutes old). `shot_save.py` (Python standard library) is then started with a fixed argument list, never through a shell: `cleanup <plugin id>` (when the panel loads), `prepare <plugin id>`, `save <picture> "My Plugins"` (checks that the picture is a regular file of yours in that folder, at most 32 MiB and a PNG, copies it as above and removes it), and `note <picture> "My Plugins"` with the note on its standard input. Each call answers with one line of JSON. A new F12 waits until the note before it is written.
- **Off:** switch **F12 saves a screenshot** off on the settings page; F12 then does nothing in this panel.

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
review status, live star counts and plugins kept in your GitHub organizations; without it, stars come
from the daily marketplace catalog, only repositories of the account itself count, and there is no
review status: catalog entries marked verified show *Listed & Verified*, all others *Published*.

## Remove

```sh
omarchy plugin disable ubruckhaus.my-plugins
omarchy plugin remove ubruckhaus.my-plugins
rm -r ~/.config/omarchy/my-plugins ~/.local/state/omarchy/my-plugins   # settings, cache and history (optional)
```

Screenshots you took with F12 stay in `~/Pictures/My Plugins/` until you delete them.

## Privacy and network

My Plugins reads only: the marketplace catalog
(`raw.githubusercontent.com/omacom/omarchy-plugin-marketplace/main/site/catalog.json`, cached and
re-checked at most hourly), the marketplace stats API (`api.omarchyplugins.com/v1/stats`) and, through
your own `gh` login, the repository list (name, description, stars; up to 300, private ones
included) of each account or organization that holds one of your listed plugins, your marketplace issues and the
list of GitHub organizations you belong to (`gh api user/orgs`, which can include private memberships;
it is only used to match catalog entries and is not stored). Every download and helper output has
a size cap and an overall deadline, redirects are refused, and links open only for `github.com` and
`plugins.omarchy.org`. Nothing is sent anywhere; settings, the catalog cache and the history stay in
`~/.config/omarchy/my-plugins` and `~/.local/state/omarchy/my-plugins`. F12 pictures and notes (see above) stay in `~/Pictures/My Plugins/`.

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
  - Only plugins listed in the marketplace catalog whose repository belongs to your GitHub account (or,
    with `gh` logged into it, to one of its organizations) are shown.
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
When `gh` is logged into that same account, plugins in repositories of the GitHub organizations
it belongs to count too (e.g. `github.com/maprisma/omarchy-maprisma-launcher`), read with
`gh api user/orgs`. The review status of every card comes from marketplace issues opened by your
account (and the catalog's verified mark when there is none); a review started by another member
of the organization is not shown.

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

`PanelShot.qml`, `shot_save.py` (with `tests/test_shot_save.py`), `corners.js`, `KeyTextField.qml`, `CompactDropdown.qml` and the shared texts in `I18n.js` come from the author's shared plugin kit and are the same in his other panels. The vendored controls in `native/` take their corners from the **Corners** setting (see `native/README.md`).

---

## License

MIT License (c) 2026 Uwe Bruckhaus
