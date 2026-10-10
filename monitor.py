#!/usr/bin/env python3
"""
My Plugins - Omarchy Plugin Marketplace & GitHub Monitor
Author: uBruckhaus
Local plugin to monitor marketplace metrics (views, downloads/copies, hearts),
GitHub stars, and publication/verification status for author's plugins.
"""

import sys
import os
import stat
import json
import fcntl
import urllib.request
import urllib.error
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager

DEFAULT_AUTHOR = "ubruckhaus"

# Sortable fields for the plugin list and their display labels
SORT_FIELDS = ["views", "downloads", "hearts", "stars", "name", "date"]
SORT_ORDERS = ["asc", "desc"]
DEFAULT_SORT_BY = "views"
DEFAULT_SORT_ORDER = "desc"

DEFAULT_PLUGINS = [
    {
        "name": "Launch & Bind",
        "id": "ubruckhaus.simple-launcher-for-fools",
        "repo_name": "omarchy-simple-launcher-for-fools",
        "display_icon": "rocket",
        "publish_date": "2026-09-27"
    },
    {
        "name": "Workspace Presets",
        "id": "ubruckhaus.simple-tile",
        "repo_name": "omarchy-simple-tile",
        "display_icon": "tile",
        "publish_date": "2026-09-28"
    },
    {
        "name": "Video Trans",
        "id": "ubruckhaus.video-trans",
        "repo_name": "omarchy-video-trans",
        "display_icon": "video",
        "publish_date": "2026-10-01"
    },
    {
        "name": "Simple Reader",
        "id": "ubruckhaus.simple-reader",
        "repo_name": "omarchy-simple-reader",
        "display_icon": "reader",
        "publish_date": "2026-10-01"
    },
    {
        "name": "Simple Recipes",
        "id": "ubruckhaus.simple-recipes",
        "repo_name": "omarchy-simple-recipes",
        "display_icon": "recipes",
        "publish_date": "2026-10-03"
    }
]

def get_runtime_dir():
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        runtime_path = Path(runtime)
        try:
            st = runtime_path.lstat()
            if runtime_path.is_symlink():
                raise RuntimeError(f"unsafe symlinked XDG_RUNTIME_DIR: {runtime_path}")
            if not stat.S_ISDIR(st.st_mode):
                raise RuntimeError(f"XDG_RUNTIME_DIR is not a directory: {runtime_path}")
            if st.st_uid != os.getuid():
                raise RuntimeError(f"XDG_RUNTIME_DIR not owned by current user: {runtime_path}")
            if st.st_mode & 0o022 != 0:
                raise RuntimeError(f"insecure permissions on XDG_RUNTIME_DIR: {runtime_path}")
            return runtime_path
        except FileNotFoundError:
            pass

    fallback = Path(f"/tmp/omarchy-my-plugins-{os.getuid()}")
    try:
        st = fallback.lstat()
        if fallback.is_symlink():
            raise RuntimeError(f"unsafe pre-existing symlinked runtime directory: {fallback}")
        if not stat.S_ISDIR(st.st_mode):
            raise RuntimeError(f"unsafe pre-existing runtime path is not a directory: {fallback}")
        if st.st_uid != os.getuid():
            raise RuntimeError(f"unsafe runtime directory ownership: {fallback}")
        if st.st_mode & 0o077 != 0:
            raise RuntimeError(f"unsafe runtime directory permissions: {fallback}")
        return fallback
    except FileNotFoundError:
        fallback.mkdir(mode=0o700, exist_ok=False)
        return fallback

@contextmanager
def runtime_lock(lock_name="my_plugins.lock"):
    runtime_dir = get_runtime_dir()
    lock_path = runtime_dir / lock_name

    try:
        st = lock_path.lstat()
        if lock_path.is_symlink():
            raise RuntimeError(f"unsafe pre-existing symlink: {lock_path}")
        if not stat.S_ISREG(st.st_mode):
            raise RuntimeError(f"lock path is not a regular file: {lock_path}")
        if st.st_uid != os.getuid():
            raise RuntimeError(f"unsafe lock file ownership: {lock_path}")
    except FileNotFoundError:
        pass

    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(lock_path), flags, 0o600)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid():
            raise RuntimeError(f"invalid lock file descriptor: {lock_path}")
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
    finally:
        os.close(fd)

def get_state_dir():
    state_home = os.environ.get("XDG_STATE_HOME")
    if state_home:
        base = Path(state_home)
    else:
        base = Path.home() / ".local" / "state"
    d = base / "omarchy" / "my-plugins"
    d.mkdir(parents=True, exist_ok=True)
    return d

def get_config_dir():
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if config_home:
        base = Path(config_home)
    else:
        base = Path.home() / ".config"
    d = base / "omarchy" / "plugins" / "ubruckhaus.my-plugins"
    d.mkdir(parents=True, exist_ok=True)
    return d

def load_config():
    cfg_file = get_config_dir() / "config.json"
    if cfg_file.is_file():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "author" not in data:
                    data["author"] = DEFAULT_AUTHOR
                if data.get("sort_by") not in SORT_FIELDS:
                    data["sort_by"] = DEFAULT_SORT_BY
                if data.get("sort_order") not in SORT_ORDERS:
                    data["sort_order"] = DEFAULT_SORT_ORDER
                return data
        except Exception:
            pass
    return {
        "author": DEFAULT_AUTHOR,
        "interval_minutes": 5,
        "sort_by": DEFAULT_SORT_BY,
        "sort_order": DEFAULT_SORT_ORDER,
        "plugins": DEFAULT_PLUGINS
    }

def save_config(cfg):
    cfg_file = get_config_dir() / "config.json"
    with runtime_lock("my_plugins_cfg.lock"):
        tmp_file = cfg_file.with_suffix(".tmp")
        flags = os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(str(tmp_file), flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp_file, cfg_file)

def load_json_file(path, fallback=None):
    if not path.is_file():
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback

def save_json_file(path, data):
    tmp = path.with_suffix(".tmp")
    flags = os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(tmp), flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

def fetch_marketplace_stats(author=DEFAULT_AUTHOR):
    url = "https://api.omarchyplugins.com/v1/stats"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "OmarchyMyPlugins/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            all_plugins = data.get("plugins", {})
            prefix = author.lower() + "."
            author_stats = {k: v for k, v in all_plugins.items() if k.lower().startswith(prefix)}
            return author_stats if author_stats else all_plugins
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to fetch marketplace stats for author '{author}': {e}\n")
        return {}

def fetch_marketplace_issues(author=DEFAULT_AUTHOR):
    try:
        res = subprocess.run(
            ["gh", "issue", "list", "--repo", "omacom/omarchy-plugin-marketplace", "--author", author, "--state", "all", "--json", "number,title,state,labels,createdAt,closedAt,updatedAt,url"],
            capture_output=True,
            text=True,
            timeout=6
        )
        if res.returncode == 0:
            return json.loads(res.stdout)
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to fetch marketplace issues for author '{author}': {e}\n")
    return []

def fetch_github_releases(author=DEFAULT_AUTHOR, repo_names=None):
    """Latest release tag per repository: {repo_name: tagName}.

    Repos without releases (or unreachable) are simply omitted.
    """
    releases = {}
    if not repo_names:
        return releases
    for rname in repo_names:
        if not rname:
            continue
        try:
            res = subprocess.run(
                ["gh", "release", "view", "--repo", f"{author}/{rname}", "--json", "tagName"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if res.returncode == 0:
                tag = (json.loads(res.stdout).get("tagName") or "").strip()
                if tag:
                    releases[rname] = tag
        except Exception:
            pass
    return releases

def resolve_version(local_version, release_tag):
    """Prefer the local (installed) version, fall back to the release tag."""
    local = str(local_version or "").strip()
    release = str(release_tag or "").strip()
    if release[:1] in ("v", "V"):
        release = release[1:]
    return local or release

def fetch_github_repos(author=DEFAULT_AUTHOR):
    try:
        res = subprocess.run(
            ["gh", "repo", "list", author, "--json", "name,description,stargazerCount,url,createdAt,pushedAt"],
            capture_output=True,
            text=True,
            timeout=6
        )
        if res.returncode == 0:
            repos_list = json.loads(res.stdout)
            return {r["name"]: r for r in repos_list}
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to fetch github repos for author '{author}': {e}\n")
    return {}

def discover_plugins_by_author(author=DEFAULT_AUTHOR, repos=None, issues=None, stats=None):
    discovered = {}

    # Seed with DEFAULT_PLUGINS matching this author
    for p in DEFAULT_PLUGINS:
        if p["id"].lower().startswith(author.lower() + ".") or author.lower() in p["id"].lower():
            discovered[p["id"]] = dict(p)

    # 1. Local installed plugins in ~/.config/omarchy/plugins/
    p_dir = Path.home() / ".config" / "omarchy" / "plugins"
    if p_dir.is_dir():
        for d in p_dir.iterdir():
            if d.is_dir() and not d.name.endswith(".my-plugins"):
                mf = d / "manifest.json"
                if mf.is_file():
                    try:
                        with open(mf, "r", encoding="utf-8") as f:
                            m = json.load(f)
                        pid = m.get("id", "")
                        p_auth = m.get("author", "").lower()
                        if p_auth == author.lower() or "uwe bruckhaus" in p_auth or pid.lower().startswith(author.lower() + "."):
                            name = m.get("name", "")
                            icon = "plugin"
                            nl = name.lower()
                            if "launcher" in nl: icon = "rocket"
                            elif "tile" in nl: icon = "tile"
                            elif "video" in nl: icon = "video"
                            elif "reader" in nl: icon = "reader"
                            elif "recipe" in nl: icon = "recipes"

                            clean_suffix = d.name.replace(f"{author}.", "")
                            repo_name = f"omarchy-{clean_suffix}"
                            mf_version = m.get("version", "")
                            if pid not in discovered:
                                discovered[pid] = {
                                    "id": pid,
                                    "name": name,
                                    "repo_name": repo_name,
                                    "display_icon": icon,
                                    "description": m.get("description", ""),
                                    "version": mf_version
                                }
                            else:
                                # The installed manifest is authoritative for display names (renames)
                                if name:
                                    discovered[pid]["name"] = name
                                if not discovered[pid].get("description"):
                                    discovered[pid]["description"] = m.get("description", "")
                                if not discovered[pid].get("version"):
                                    discovered[pid]["version"] = mf_version
                    except Exception:
                        pass

    # 2. GitHub repos for author
    if repos:
        for rname, r in repos.items():
            if rname in ("omarchy-my-plugins", "my-plugins"):
                continue
            clean_name = rname.replace("omarchy-", "")
            matched_pid = None
            for pid, pdata in discovered.items():
                if pdata.get("repo_name") == rname or clean_name in pid:
                    matched_pid = pid
                    break
            if not matched_pid:
                matched_pid = f"{author}.{clean_name}"
                pname = clean_name.replace("-", " ").title()
                icon = "plugin"
                nl = pname.lower()
                if "launcher" in nl: icon = "rocket"
                elif "tile" in nl: icon = "tile"
                elif "video" in nl: icon = "video"
                elif "reader" in nl: icon = "reader"
                elif "recipe" in nl: icon = "recipes"

                discovered[matched_pid] = {
                    "id": matched_pid,
                    "name": pname,
                    "repo_name": rname,
                    "display_icon": icon,
                    "description": r.get("description", "")
                }
            if r.get("description") and not discovered[matched_pid].get("description"):
                discovered[matched_pid]["description"] = r.get("description")

    # 3. Stats keys for author
    if stats:
        for pid in stats.keys():
            if pid not in discovered and pid.lower().startswith(author.lower() + "."):
                clean_name = pid.replace(f"{author}.", "")
                pname = clean_name.replace("-", " ").title()
                discovered[pid] = {
                    "id": pid,
                    "name": pname,
                    "repo_name": f"omarchy-{clean_name}",
                    "display_icon": "plugin"
                }

    # Only list published plugins: known defaults, marketplace stats, or a marketplace issue.
    # Local-only plugins (installed but never submitted) are skipped.
    default_ids = {p["id"] for p in DEFAULT_PLUGINS}
    stats_ids = set(stats.keys()) if stats else set()
    result = [
        p for p in discovered.values()
        if p["id"] in default_ids or p["id"] in stats_ids or has_marketplace_issue(p, issues or [])
    ]
    result.sort(key=lambda x: x.get("publish_date") or "9999")
    return result

def has_marketplace_issue(plugin_dict, issues):
    pname_lower = plugin_dict.get("name", "").lower()
    pid = plugin_dict.get("id", "")
    clean_id = pid.split(".")[-1].lower() if "." in pid else pid.lower()
    for i in issues:
        title_lower = i.get("title", "").lower()
        if (pname_lower and pname_lower in title_lower) or (clean_id and clean_id in title_lower):
            return True
    return False

def determine_publish_date(plugin_dict, issues):
    if plugin_dict.get("publish_date"):
        return plugin_dict["publish_date"]

    known_dates = {
        "ubruckhaus.simple-launcher-for-fools": "2026-09-27",
        "ubruckhaus.simple-tile": "2026-09-28",
        "ubruckhaus.video-trans": "2026-10-01",
        "ubruckhaus.simple-reader": "2026-10-01",
        "ubruckhaus.simple-recipes": "2026-10-03",
    }
    pid = plugin_dict.get("id", "")
    if pid in known_dates:
        return known_dates[pid]

    pname_lower = plugin_dict.get("name", "").lower()
    clean_id = pid.split(".")[-1].lower() if pid and "." in pid else (pid.lower() if pid else "")
    repo_clean = plugin_dict.get("repo_name", "").replace("omarchy-", "").lower()

    matching = []
    for i in issues:
        title_lower = i.get("title", "").lower()
        if (pname_lower and pname_lower in title_lower) or \
           (clean_id and clean_id in title_lower) or \
           (repo_clean and repo_clean in title_lower):
            matching.append(i)

    if matching:
        matching.sort(key=lambda x: x.get("createdAt", ""))
        earliest = matching[0]
        if earliest.get("closedAt"):
            return earliest["closedAt"][:10]
        if earliest.get("createdAt"):
            return earliest["createdAt"][:10]

    return ""

def determine_status(plugin_or_name, issues):
    if isinstance(plugin_or_name, dict):
        pname = plugin_or_name.get("name", "")
        pid = plugin_or_name.get("id", "")
        repo_name = plugin_or_name.get("repo_name", "")
    else:
        pname = str(plugin_or_name)
        pid = ""
        repo_name = ""

    matching = []
    pname_lower = pname.lower()
    clean_id = pid.split(".")[-1].lower() if pid and "." in pid else pid.lower()
    rname_clean = repo_name.replace("omarchy-", "").lower()

    for i in issues:
        title_lower = i.get("title", "").lower()
        if (pname_lower and pname_lower in title_lower) or \
           (clean_id and clean_id in title_lower) or \
           (rname_clean and rname_clean in title_lower):
            matching.append(i)

    if not matching:
        return "Published", "published", None, None

    # Latest issue
    latest = matching[0]
    labels = [l.get("name", "") for l in latest.get("labels", [])]
    is_open = latest.get("state") == "OPEN"
    iss_num = latest.get("number")
    iss_url = latest.get("url")

    if "listed" in labels or "approved-and-verified" in labels:
        return "Listed & Verified", "verified", iss_num, iss_url
    if "needs-fixes" in labels:
        return "Review: Needs Fixes", "needs_fixes", iss_num, iss_url
    if "security-review-required" in labels:
        return "Security Review", "review", iss_num, iss_url
    if "validated" in labels and is_open:
        return "Validated (Pending)", "pending", iss_num, iss_url
    if is_open:
        return "Submission Open", "open", iss_num, iss_url

    return "Listed", "listed", iss_num, iss_url

def query_metrics(author=None):
    state_dir = get_state_dir()
    snapshot_file = state_dir / "snapshot.json"
    ack_file = state_dir / "acknowledged.json"

    cfg = load_config()
    author = (author or cfg.get("author", DEFAULT_AUTHOR)).strip()
    interval = cfg.get("interval_minutes", 5)

    stats = fetch_marketplace_stats(author=author)
    issues = fetch_marketplace_issues(author=author)
    repos = fetch_github_repos(author=author)

    tracked = discover_plugins_by_author(author=author, repos=repos, issues=issues, stats=stats)
    releases = fetch_github_releases(
        author=author,
        repo_names=[p.get("repo_name", "") for p in tracked]
    )

    # Load baseline acknowledged state
    ack_state = load_json_file(ack_file, fallback={})
    ack_plugins = ack_state.get("plugins_map", {})

    plugins_result = []
    total_views = 0
    total_downloads = 0
    total_hearts = 0
    total_stars = 0

    has_changes = False
    changes_list = []
    plugins_map = {}

    for p in tracked:
        pid = p["id"]
        pname = p["name"]
        repo_name = p.get("repo_name", "")
        icon = p.get("display_icon", "plugin")

        st = stats.get(pid, {"views": 0, "copies": 0, "hearts": 0})
        views = int(st.get("views", 0))
        downloads = int(st.get("copies", 0))
        hearts = int(st.get("hearts", 0))

        rp = repos.get(repo_name, {})
        stars = int(rp.get("stargazerCount", 0))
        repo_url = rp.get("url", f"https://github.com/{author}/{repo_name}")
        description = p.get("description") or rp.get("description", "")

        release_tag = releases.get(repo_name, "")
        release_version = release_tag[1:] if release_tag[:1] in ("v", "V") else release_tag
        local_version = str(p.get("version", "") or "").strip()
        version = local_version or release_version

        status_text, status_code, issue_num, issue_url = determine_status(p, issues)
        publish_date = determine_publish_date(p, issues)

        total_views += views
        total_downloads += downloads
        total_hearts += hearts
        total_stars += stars

        ack_p = ack_plugins.get(pid, {})
        ack_views = ack_p.get("views", views)
        ack_downloads = ack_p.get("downloads", downloads)
        ack_hearts = ack_p.get("hearts", hearts)
        ack_stars = ack_p.get("stars", stars)
        ack_status = ack_p.get("status_text", status_text)

        views_delta = max(0, views - ack_views)
        downloads_delta = max(0, downloads - ack_downloads)
        hearts_delta = max(0, hearts - ack_hearts)
        stars_delta = max(0, stars - ack_stars)
        status_changed = status_text != ack_status

        item_has_change = (views_delta > 0 or downloads_delta > 0 or hearts_delta > 0 or stars_delta > 0 or status_changed)
        if item_has_change:
            has_changes = True
            delta_parts = []
            if views_delta > 0: delta_parts.append(f"+{views_delta} views")
            if downloads_delta > 0: delta_parts.append(f"+{downloads_delta} dl")
            if hearts_delta > 0: delta_parts.append(f"+{hearts_delta} ❤️")
            if stars_delta > 0: delta_parts.append(f"+{stars_delta} ⭐")
            if status_changed: delta_parts.append(f"status: {status_text}")
            changes_list.append(f"{pname}: {', '.join(delta_parts)}")

        record = {
            "id": pid,
            "name": pname,
            "repo_name": repo_name,
            "display_icon": icon,
            "publish_date": publish_date,
            "version": version,
            "local_version": local_version,
            "release_version": release_version,
            "views": views,
            "views_delta": views_delta,
            "downloads": downloads,
            "downloads_delta": downloads_delta,
            "hearts": hearts,
            "hearts_delta": hearts_delta,
            "stars": stars,
            "stars_delta": stars_delta,
            "status_text": status_text,
            "status_code": status_code,
            "status_changed": status_changed,
            "has_changes": item_has_change,
            "issue_number": issue_num,
            "issue_url": issue_url,
            "repo_url": repo_url,
            "marketplace_url": f"https://plugins.omarchy.org/plugin.html?id={pid}",
            "description": description
        }
        plugins_result.append(record)
        plugins_map[pid] = {
            "views": views,
            "downloads": downloads,
            "hearts": hearts,
            "stars": stars,
            "status_text": status_text
        }

    now_iso = datetime.now(timezone.utc).isoformat()
    changes_summary = "; ".join(changes_list) if changes_list else ""

    cfg_sort_by = cfg.get("sort_by", DEFAULT_SORT_BY)
    cfg_sort_order = cfg.get("sort_order", DEFAULT_SORT_ORDER)
    plugins_result = sort_plugins(plugins_result, cfg_sort_by, cfg_sort_order)

    result = {
        "status": "ok",
        "author": author,
        "last_updated": now_iso,
        "interval_minutes": interval,
        "has_changes": has_changes,
        "changes_summary": changes_summary,
        "total_views": total_views,
        "total_downloads": total_downloads,
        "total_hearts": total_hearts,
        "total_stars": total_stars,
        "sort_by": cfg_sort_by,
        "sort_order": cfg_sort_order,
        "plugins": plugins_result,
        "plugins_map": plugins_map
    }

    # If ack_file didn't exist, this is first run - initialize acknowledged baseline
    if not ack_file.is_file():
        result["has_changes"] = False
        result["changes_summary"] = ""
        for p in result["plugins"]:
            p["has_changes"] = False
            p["views_delta"] = 0
            p["downloads_delta"] = 0
            p["hearts_delta"] = 0
            p["stars_delta"] = 0
            p["status_changed"] = False
        save_json_file(ack_file, {
            "acknowledged_at": now_iso,
            "plugins_map": plugins_map
        })

    save_json_file(snapshot_file, result)
    return result

def acknowledge_changes(author=None):
    state_dir = get_state_dir()
    snapshot_file = state_dir / "snapshot.json"
    ack_file = state_dir / "acknowledged.json"

    data = load_json_file(snapshot_file)
    if not data:
        data = query_metrics(author=author)

    plugins_map = data.get("plugins_map", {})
    now_iso = datetime.now(timezone.utc).isoformat()
    save_json_file(ack_file, {
        "acknowledged_at": now_iso,
        "plugins_map": plugins_map
    })

    # Clear changes from snapshot
    data["has_changes"] = False
    data["changes_summary"] = ""
    for p in data.get("plugins", []):
        p["has_changes"] = False
        p["views_delta"] = 0
        p["downloads_delta"] = 0
        p["hearts_delta"] = 0
        p["stars_delta"] = 0
        p["status_changed"] = False

    data = apply_sort(data)
    save_json_file(snapshot_file, data)
    return data

def get_current_status(author=None):
    state_dir = get_state_dir()
    snapshot_file = state_dir / "snapshot.json"
    data = load_json_file(snapshot_file)
    if not data:
        return query_metrics(author=author)
    # Re-apply the current sort configuration so cached snapshots
    # always follow the configured order, even if sorted earlier.
    return apply_sort(data)

def sort_plugins(plugins, sort_by=DEFAULT_SORT_BY, sort_order=DEFAULT_SORT_ORDER):
    """Return a new list of plugin records sorted by `sort_by`/`sort_order`.

    Fields: views, downloads, hearts, stars, name, date (publish date).
    Ties always keep a deterministic ascending-name order (stable sort).
    """
    if sort_by not in SORT_FIELDS:
        sort_by = DEFAULT_SORT_BY
    if sort_order not in SORT_ORDERS:
        sort_order = DEFAULT_SORT_ORDER
    reverse = (sort_order == "desc")

    def tiebreak(p):
        return ((p.get("name") or "").lower(), p.get("id") or "")

    if sort_by == "name":
        keyfn = lambda p: (p.get("name") or "").lower()
    elif sort_by == "date":
        keyfn = lambda p: p.get("publish_date") or ""
    else:
        def keyfn(p):
            try:
                return int(p.get(sort_by) or 0)
            except (TypeError, ValueError):
                return 0

    ordered = sorted(plugins, key=tiebreak)
    return sorted(ordered, key=keyfn, reverse=reverse)

def apply_sort(data):
    """Sort the plugins list of a result dict in place using current config."""
    if not isinstance(data, dict) or not isinstance(data.get("plugins"), list):
        return data
    cfg = load_config()
    sort_by = cfg.get("sort_by") or data.get("sort_by") or DEFAULT_SORT_BY
    sort_order = cfg.get("sort_order") or data.get("sort_order") or DEFAULT_SORT_ORDER
    data["plugins"] = sort_plugins(data["plugins"], sort_by, sort_order)
    data["sort_by"] = sort_by
    data["sort_order"] = sort_order
    return data

def set_sort(sort_by=None, sort_order=None):
    cfg = load_config()
    if sort_by is not None:
        s = str(sort_by).strip().lower()
        if s not in SORT_FIELDS:
            return {"status": "error", "message": f"invalid sort_by '{sort_by}' (choose from: {', '.join(SORT_FIELDS)})"}
        cfg["sort_by"] = s
    if sort_order is not None:
        o = str(sort_order).strip().lower()
        if o not in SORT_ORDERS:
            return {"status": "error", "message": f"invalid sort_order '{sort_order}' (choose from: {', '.join(SORT_ORDERS)})"}
        cfg["sort_order"] = o
    save_config(cfg)
    return {"status": "ok", "sort_by": cfg["sort_by"], "sort_order": cfg["sort_order"]}

def set_interval(minutes):
    try:
        m = int(minutes)
        if m < 1: m = 1
        if m > 1440: m = 1440
        cfg = load_config()
        cfg["interval_minutes"] = m
        save_config(cfg)
        return {"status": "ok", "interval_minutes": m}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def set_author(author):
    try:
        a = str(author).strip()
        if not a:
            return {"status": "error", "message": "empty author"}
        cfg = load_config()
        cfg["author"] = a
        save_config(cfg)
        return {"status": "ok", "author": a}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def open_url(url):
    if not url or not (url.startswith("https://") or url.startswith("http://")):
        return {"status": "error", "message": "invalid url"}
    try:
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def handle_request(req):
    cmd = req.get("command", "")
    author = req.get("author")
    if cmd == "query":
        return query_metrics(author=author)
    elif cmd == "status":
        return get_current_status(author=author)
    elif cmd == "acknowledge":
        return acknowledge_changes(author=author)
    elif cmd == "configure":
        settings = req.get("settings", {})
        if "interval_minutes" in settings:
            set_interval(settings["interval_minutes"])
        if "author" in settings:
            set_author(settings["author"])
        if "sort_by" in settings or "sort_order" in settings:
            res = set_sort(settings.get("sort_by"), settings.get("sort_order"))
            if res.get("status") != "ok":
                return res
        return get_current_status(author=settings.get("author"))
    elif cmd == "set_sort":
        res = set_sort(req.get("sort_by"), req.get("sort_order"))
        if res.get("status") != "ok":
            return res
        return get_current_status(author=author)
    elif cmd == "set_author":
        if "author" in req:
            set_author(req["author"])
        return query_metrics(author=req.get("author"))
    elif cmd == "open_url":
        return open_url(req.get("url", ""))
    else:
        return {"status": "error", "message": f"unknown command '{cmd}'"}

def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        author = None
        if "--author" in sys.argv:
            idx = sys.argv.index("--author")
            if idx + 1 < len(sys.argv):
                author = sys.argv[idx + 1]

        if arg == "--query":
            res = query_metrics(author=author)
            print(json.dumps(res, indent=2))
        elif arg == "--status":
            res = get_current_status(author=author)
            print(json.dumps(res, indent=2))
        elif arg == "--acknowledge":
            res = acknowledge_changes(author=author)
            print(json.dumps(res, indent=2))
        elif arg == "--set-interval" and len(sys.argv) > 2:
            res = set_interval(sys.argv[2])
            print(json.dumps(res, indent=2))
        elif arg == "--set-author" and len(sys.argv) > 2:
            res = set_author(sys.argv[2])
            print(json.dumps(res, indent=2))
        elif arg == "--set-sort" and len(sys.argv) > 3:
            res = set_sort(sys.argv[2], sys.argv[3])
            print(json.dumps(res, indent=2))
        elif arg == "--open" and len(sys.argv) > 2:
            res = open_url(sys.argv[2])
            print(json.dumps(res, indent=2))
        elif arg == "--author" and len(sys.argv) > 2:
            res = query_metrics(author=sys.argv[2])
            print(json.dumps(res, indent=2))
        else:
            print("Usage: monitor.py [--query [--author <name>] | --status | --acknowledge | --set-interval <min> | --set-author <name> | --set-sort <field> <asc|desc> | --open <url>]")
            print(f"  sort <field> one of: {', '.join(SORT_FIELDS)}")
        return

    # Stdin JSON mode (used by Quickshell Process)
    line = sys.stdin.readline()
    if line:
        try:
            req = json.loads(line)
            res = handle_request(req)
            print(json.dumps(res))
        except Exception as e:
            print(json.dumps({"status": "error", "message": str(e)}))

if __name__ == "__main__":
    main()
