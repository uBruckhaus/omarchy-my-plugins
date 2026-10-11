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
import re
import time
import zlib
from pathlib import Path
from datetime import date, datetime, timedelta, timezone
from contextlib import contextmanager

DEFAULT_AUTHOR = ""  # empty: use the GitHub account gh is logged into

# Sortable fields for the plugin list and their display labels
SORT_FIELDS = ["views", "downloads", "hearts", "stars", "name", "date"]
SORT_ORDERS = ["asc", "desc"]
DEFAULT_SORT_BY = "views"
DEFAULT_SORT_ORDER = "desc"


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
    # Plugin directories are watched for code reloads. Settings must live
    # outside them, otherwise changing a preference destroys the open panel.
    d = base / "omarchy" / "my-plugins"
    d.mkdir(parents=True, exist_ok=True)
    return d

def load_config():
    cfg_file = get_config_dir() / "config.json"
    if not cfg_file.is_file():
        # Keep existing preferences until the first save writes the new path.
        cfg_file = get_config_dir().parent / "plugins" / "ubruckhaus.my-plugins" / "config.json"
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
        "plugins": []
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

STATS_URL = "https://api.omarchyplugins.com/v1/stats"
CATALOG_URL = "https://raw.githubusercontent.com/omacom/omarchy-plugin-marketplace/main/site/catalog.json"
CATALOG_MAX_AGE = 3600          # refresh the cached catalog at most hourly (ETag makes it cheap)
CATALOG_LIMIT = 64 * 1024 * 1024
STATS_LIMIT = 8 * 1024 * 1024
ACCOUNT_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
REPO_RE = re.compile(r"^https://github\.com/([A-Za-z0-9-]{1,39})/([A-Za-z0-9._-]{1,100})/?$")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def run_bounded(args, limit=2 * 1024 * 1024, timeout=10):
    """Run a helper (gh, git) with an output cap and one overall deadline: (returncode, text)."""
    deadline = time.monotonic() + timeout
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    chunks, size = [], 0
    try:
        os.set_blocking(proc.stdout.fileno(), False)
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError(f"{args[0]} took too long")
            try:
                chunk = os.read(proc.stdout.fileno(), 65536)
            except BlockingIOError:
                time.sleep(0.02)
                continue
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                raise ValueError(f"{args[0]} output too large")
            chunks.append(chunk)
        return proc.wait(timeout=max(0.1, deadline - time.monotonic())), b"".join(chunks).decode("utf-8", "replace")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        proc.stdout.close()


def http_get(url, limit, timeout=20, etag=None):
    """GET with a byte cap and one overall deadline. Returns (status, body, etag);
    status 304 means the cached copy is current. Raises ValueError on oversize/slow replies."""
    deadline = time.monotonic() + timeout
    headers = {"User-Agent": "OmarchyMyPlugins/1.2", "Accept-Encoding": "gzip"}
    if etag:
        headers["If-None-Match"] = etag
    req = urllib.request.Request(url, headers=headers)
    try:
        resp = urllib.request.build_opener(_NoRedirect()).open(req, timeout=min(10, timeout))
    except urllib.error.HTTPError as error:
        if error.code == 304:
            return 304, b"", etag
        raise
    with resp:
        if int(resp.headers.get("Content-Length") or 0) > limit:
            raise ValueError("reply too large")
        chunks, size = [], 0
        while True:
            if time.monotonic() > deadline:
                raise ValueError("reply took too long")
            chunk = resp.read1(256 * 1024)  # returns what has arrived, so the deadline is checked often
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                raise ValueError("reply too large")
            chunks.append(chunk)
        body = b"".join(chunks)
        if resp.headers.get("Content-Encoding") == "gzip":
            decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
            body = decoder.decompress(body, limit + 1)
            if len(body) > limit or decoder.unconsumed_tail:
                raise ValueError("reply too large")
        return resp.status, body, resp.headers.get("ETag")


def valid_account(account):
    return isinstance(account, str) and bool(ACCOUNT_RE.match(account))


def gh_login():
    """The GitHub account gh is logged into, used when no account is configured."""
    try:
        code, out = run_bounded(["gh", "api", "user", "--jq", ".login"], limit=4096, timeout=6)
        login = out.strip()[:64] if code == 0 else ""
        return login if valid_account(login) else ""
    except Exception:
        return ""


def read_small(path, limit=64 * 1024):
    try:
        with open(path, "rb") as f:
            return f.read(limit).decode("utf-8", "replace")
    except OSError:
        return ""


def gh_config_user():
    """The github.com user from gh's local config, without a network call."""
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    text = read_small(Path(os.environ.get("GH_CONFIG_DIR") or config_home / "gh") / "hosts.yml")
    block = re.search(r"(?ms)^github\.com:\s*$(.*?)(?=^\S|\Z)", text)
    match = re.search(r"(?m)^\s+user:\s*([A-Za-z0-9-]+)\s*$", block.group(1)) if block else None
    return match.group(1) if match and valid_account(match.group(1)) else ""


def git_config(key):
    try:
        code, out = run_bounded(["git", "config", "--global", "--get", key], limit=4096, timeout=3)
        return out.strip()[:256] if code == 0 else ""
    except Exception:
        return ""


def noreply_user(email):
    match = re.match(r"^(?:\d+\+)?([A-Za-z0-9-]{1,39})@users\.noreply\.github\.com$", email or "")
    return match.group(1) if match else ""


def plugin_checkout_owners():
    """Owners of installed plugin checkouts whose plugin ID prefix is the owner (one's own plugins)."""
    owners = {}
    root = Path.home() / ".config" / "omarchy" / "plugins"
    for directory in sorted(root.iterdir()) if root.is_dir() else []:
        if "." not in directory.name:
            continue
        text = read_small(directory / ".git" / "config")
        match = re.search(r"url\s*=\s*(?:https://github\.com/|git@github\.com:)([A-Za-z0-9-]{1,39})/", text)
        if match and match.group(1).lower() == directory.name.split(".")[0]:
            owners[match.group(1)] = owners.get(match.group(1), 0) + 1
    return sorted(owners, key=lambda o: -owners[o])


def detect_account(catalog=None):
    """Find the GitHub account on this computer for first setup: (account, source).
    Prefers a candidate that owns listed plugins when the catalog is known."""
    candidates = []
    def add(login, source):
        if valid_account(login) and login.lower() not in {c[0].lower() for c in candidates}:
            candidates.append((login, source))
    add(gh_config_user(), "gh")
    if not candidates:
        add(gh_login(), "gh")
    add(git_config("github.user"), "git config github.user")
    add(noreply_user(git_config("user.email")), "git e-mail")
    for owner in plugin_checkout_owners():
        add(owner, "installed plugins")
    if catalog:
        owners = {repo_owner(e.get("repo"))[0].lower() for e in catalog if repo_owner(e.get("repo"))[0]}
        for login, source in candidates:
            if login.lower() in owners:
                return login, source
    return candidates[0] if candidates else ("", "")


def resolve_account(cfg, override=None, catalog=None):
    """Configured GitHub account (owner of the plugin repositories), else one detected on this computer."""
    account, _source = resolve_account_with_source(cfg, override, catalog)
    return account


def resolve_account_with_source(cfg, override=None, catalog=None):
    for candidate in (override, cfg.get("author")):
        if candidate and valid_account(str(candidate).strip()):
            return str(candidate).strip(), "settings"
    return detect_account(catalog)


def repo_owner(url):
    match = REPO_RE.match(str(url or "").removesuffix(".git"))
    return (match.group(1), match.group(2)) if match else (None, None)


def fetch_marketplace_stats():
    """{plugin id: {views, copies, hearts}} for every listed plugin."""
    try:
        _status, body, _etag = http_get(STATS_URL, STATS_LIMIT, timeout=15)
        plugins = json.loads(body.decode("utf-8")).get("plugins", {})
        return plugins if isinstance(plugins, dict) else {}
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to fetch marketplace stats: {e}\n")
        return {}


CATALOG_FIELDS = ("id", "name", "author", "repo", "version", "stars", "listedAt", "verificationStatus", "description")


def fetch_catalog(state_dir=None, now=None):
    """Listed plugins from the marketplace catalog, cached (with ETag) in the state directory."""
    state_dir = state_dir or get_state_dir()
    cache_file = state_dir / "catalog.json"
    cache = load_json_file(cache_file, fallback={}) or {}
    now = now if now is not None else time.time()
    if cache.get("plugins") and now - float(cache.get("fetched_at", 0)) < CATALOG_MAX_AGE:
        return cache["plugins"]
    try:
        status, body, etag = http_get(CATALOG_URL, CATALOG_LIMIT, timeout=60, etag=cache.get("etag") if cache.get("plugins") else None)
        if status == 304:
            cache["fetched_at"] = now
        else:
            data = json.loads(body.decode("utf-8"))
            entries = data.get("plugins", []) if isinstance(data, dict) else []
            plugins = []
            for entry in entries if isinstance(entries, list) else []:
                if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                    plugins.append({k: entry.get(k) for k in CATALOG_FIELDS})
            cache = {"etag": etag, "fetched_at": now, "plugins": plugins}
        save_json_file(cache_file, cache)
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to fetch marketplace catalog: {e}\n")
    return cache.get("plugins", [])


def fetch_marketplace_issues(account):
    try:
        code, out = run_bounded(
            ["gh", "issue", "list", "--repo", "omacom/omarchy-plugin-marketplace", "--author", account, "--state", "all",
             "--limit", "200", "--json", "number,title,body,state,labels,createdAt,closedAt,updatedAt,url"],
            limit=16 * 1024 * 1024, timeout=20)
        if code == 0:
            issues = json.loads(out)
            return issues if isinstance(issues, list) else []
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to fetch marketplace issues for '{account}': {e}\n")
    return []


def fetch_github_repos(account):
    """Live star counts: {repo name: {stargazerCount, url, description}} (the catalog refreshes daily)."""
    try:
        code, out = run_bounded(["gh", "repo", "list", account, "--limit", "300", "--json", "name,description,stargazerCount,url"],
                                limit=4 * 1024 * 1024, timeout=20)
        if code == 0:
            return {r["name"]: r for r in json.loads(out) if isinstance(r, dict) and isinstance(r.get("name"), str)}
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to fetch GitHub repos for '{account}': {e}\n")
    return {}


def discover_plugins(account, catalog, issues=None):
    """Plugins listed in the marketplace whose repository belongs to `account`."""
    wanted = account.lower()
    found = []
    for entry in catalog:
        owner, repo_name = repo_owner(entry.get("repo"))
        if not owner or owner.lower() != wanted:
            continue
        found.append({
            "id": entry["id"],
            "name": str(entry.get("name") or entry["id"]),
            "repo_name": repo_name,
            "repo_url": f"https://github.com/{owner}/{repo_name}",
            "display_icon": "plugin",
            "description": str(entry.get("description") or ""),
            "version": str(entry.get("version") or ""),
            "publish_date": str(entry.get("listedAt") or "")[:10],
            "catalog_stars": int(entry.get("stars") or 0),
            "verified": entry.get("verificationStatus") == "verified",
        })
    found.sort(key=lambda x: x.get("publish_date") or "9999")
    return found


def has_marketplace_issue(plugin_dict, issues):
    pname_lower = plugin_dict.get("name", "").lower()
    pid = plugin_dict.get("id", "")
    clean_id = pid.split(".")[-1].lower() if "." in pid else pid.lower()
    for i in issues:
        title_lower = i.get("title", "").lower()
        if (pname_lower and pname_lower in title_lower) or (clean_id and clean_id in title_lower):
            return True
    return False

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
        # [Verify] requests name the plugin ID in their body; titles may carry a newer display name.
        body_lower = str(i.get("body") or "")[:20000].lower()
        if (pid and pid.lower() in body_lower) or \
           (pname_lower and pname_lower in title_lower) or \
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
    interval = cfg.get("interval_minutes", 5)
    catalog = fetch_catalog(state_dir)
    author, account_source = resolve_account_with_source(cfg, author, catalog)
    if not author:
        return {"status": "error", "author": "", "needs_account": True, "plugins": [],
                "message": "Enter your GitHub account: the owner of your plugin repositories."}

    stats = fetch_marketplace_stats()
    issues = fetch_marketplace_issues(author)
    repos = fetch_github_repos(author)
    tracked = discover_plugins(author, catalog, issues)

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
        stars = int(rp.get("stargazerCount", p.get("catalog_stars", 0)) or 0)
        repo_url = p.get("repo_url")
        description = p.get("description") or rp.get("description", "")
        version = p.get("version", "")
        local_version = release_version = version

        status_text, status_code, issue_num, issue_url = determine_status(p, issues)
        if status_code == "published" and p.get("verified"):
            status_text, status_code = "Listed & Verified", "verified"
        publish_date = p.get("publish_date", "")

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
        "account_source": account_source,
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

    record_history(plugins_map, state_dir)
    save_json_file(snapshot_file, result)
    return result


HISTORY_DAYS = 400
METRICS = ("views", "downloads", "hearts", "stars")
RANGES = {"daily": 30, "weekly": 12, "monthly": 12}


def record_history(plugins_map, state_dir=None, today=None):
    """Keep one snapshot per day: {date: {plugin id: [views, downloads, hearts, stars]}}."""
    state_dir = state_dir or get_state_dir()
    path = state_dir / "history.json"
    history = load_json_file(path, fallback={}) or {}
    days = history.get("days") if isinstance(history.get("days"), dict) else {}
    day = (today or datetime.now().date()).isoformat()
    days[day] = {pid: [int(v.get(m, 0)) for m in METRICS] for pid, v in plugins_map.items()}
    for old in sorted(days)[:-HISTORY_DAYS]:
        del days[old]
    with runtime_lock("my_plugins_history.lock"):
        save_json_file(path, {"schema": 1, "days": days})


PASTE_TYPES = ("text/plain;charset=utf-8", "text/plain", "UTF8_STRING", "TEXT", "STRING")


def read_clipboard():
    """Explicit paste (Ctrl+V in the account field): plain text, at most 4 KiB within 2 s.
    The popup's text fields never read the clipboard by themselves."""
    try:
        code, offered = run_bounded(["wl-paste", "--list-types"], limit=4096, timeout=1)
        mime = next((t for t in PASTE_TYPES if t in offered.split()), None) if code == 0 else None
        if not mime:
            return {"status": "ok", "clipboard": ""}
        code, text = run_bounded(["wl-paste", "--no-newline", "--type", mime], limit=4096, timeout=2)
    except (OSError, ValueError, TimeoutError):
        return {"status": "error", "message": "Clipboard text is too long or did not answer in time."}
    text = text if code == 0 else ""
    return {"status": "ok", "clipboard": "".join(c for c in text if c >= " " and c != "\x7f")}


def clear_history(state_dir=None):
    """Delete all recorded daily snapshots (asked for with confirmation in the popup)."""
    path = (state_dir or get_state_dir()) / "history.json"
    with runtime_lock("my_plugins_history.lock"):
        path.unlink(missing_ok=True)
    return {"status": "ok"}


def history_series(plugin="all", metric="views", period="daily", state_dir=None, today=None):
    """Gains per day, ISO week or month for one plugin or all, from the daily snapshots.

    Periods without any snapshot so far have value None (history starts with the first refresh)."""
    if metric not in METRICS or period not in RANGES:
        return {"status": "error", "message": "unknown metric or range"}
    index = METRICS.index(metric)
    history = load_json_file((state_dir or get_state_dir()) / "history.json", fallback={}) or {}
    days = history.get("days") if isinstance(history.get("days"), dict) else {}

    def total(snapshot):
        values = [v[index] for pid, v in snapshot.items() if plugin in ("all", pid) and isinstance(v, list) and len(v) == 4]
        return sum(values) if values else None

    totals = {datetime.strptime(d, "%Y-%m-%d").date(): total(snap) for d, snap in days.items()}
    totals = {d: t for d, t in totals.items() if t is not None}
    today = today or datetime.now().date()

    def bucket_end(offset):
        if period == "daily":
            start = today - timedelta(days=offset)
            return start, start, start.strftime("%d.%m")
        if period == "weekly":
            monday = today - timedelta(days=today.weekday()) - timedelta(weeks=offset)
            return monday, monday + timedelta(days=6), "W" + monday.strftime("%V")
        year, month = today.year, today.month - offset
        while month < 1:
            month += 12
            year -= 1
        first = date(year, month, 1)
        last = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1))
        return first, last, first.strftime("%b")

    labels, values, ends = [], [], []
    count = RANGES[period]
    for offset in range(count - 1, -1, -1):
        first, last, label = bucket_end(offset)
        labels.append(label)
        inside = [d for d in totals if first <= d <= last]
        before = [d for d in totals if d < first]
        if not inside:
            values.append(None)
            ends.append(None)
            continue
        end_value = totals[max(inside)]
        start_value = totals[max(before)] if before else totals[min(inside)]
        values.append(max(0, end_value - start_value))
        ends.append(end_value)
    return {"status": "ok", "plugin": plugin, "metric": metric, "range": period,
            "labels": labels, "values": values, "totals": ends,
            "first_day": min(totals).isoformat() if totals else None}

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
        a = str(author or "").strip()
        if a == "":
            # Empty means: follow the account gh is logged into.
            cfg = load_config()
            cfg["author"] = ""
            save_config(cfg)
            return {"status": "ok", "author": detect_account()[0]}
        if not valid_account(a):
            return {"status": "error", "message": "Enter a GitHub account name (letters, digits and hyphens)."}
        cfg = load_config()
        cfg["author"] = a
        save_config(cfg)
        return {"status": "ok", "author": a}
    except Exception as e:
        return {"status": "error", "message": str(e)}

OPEN_HOSTS = ("github.com", "plugins.omarchy.org")


def open_url(url):
    """Open only https links to GitHub or the marketplace site (links come from catalog data)."""
    import urllib.parse
    parts = urllib.parse.urlsplit(str(url or ""))
    if parts.scheme != "https" or parts.hostname not in OPEN_HOSTS or parts.username or parts.password or len(str(url)) > 2048:
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
            res = set_author(settings["author"])
            if res.get("status") != "ok":
                return res
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
        res = set_author(req.get("author", ""))
        if res.get("status") != "ok":
            return res
        return query_metrics(author=res["author"] or None)
    elif cmd == "paste":
        return read_clipboard()
    elif cmd == "clear_history":
        clear_history()
        return history_series(str(req.get("plugin", "all")), str(req.get("metric", "views")), str(req.get("range", "daily")))
    elif cmd == "history":
        return history_series(str(req.get("plugin", "all")), str(req.get("metric", "views")), str(req.get("range", "daily")))
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
