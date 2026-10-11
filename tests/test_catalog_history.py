import gzip
import http.server
import json
import os
import socketserver
import sys
import tempfile
import threading
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))
import monitor

CATALOG = [
    {"id": "ubruckhaus.alpha", "name": "Alpha", "author": "Uwe", "repo": "https://github.com/uBruckhaus/omarchy-alpha",
     "version": "1.0", "stars": 3, "listedAt": "2026-10-01T10:00:00Z", "verificationStatus": "verified", "description": "A"},
    {"id": "ubruckhaus.beta", "name": "Beta", "repo": "https://github.com/ubruckhaus/omarchy-beta.git",
     "version": "0.2", "stars": 0, "listedAt": "2026-09-01T10:00:00Z"},
    {"id": "other.gamma", "name": "Gamma", "repo": "https://github.com/someone/gamma", "listedAt": "2026-09-02"},
    {"id": "evil.delta", "name": "Delta", "repo": "https://evil.example/uBruckhaus/delta"},
    {"id": "evil.epsilon", "name": "Epsilon", "repo": "https://github.com/uBruckhaus/../x"},
]


class Isolated(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {"XDG_RUNTIME_DIR": str(base / "run"), "XDG_STATE_HOME": str(base / "state"),
                                           "XDG_CONFIG_HOME": str(base / "config")})
        self.env.start()
        (base / "run").mkdir(mode=0o700)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()


class DiscoveryTests(Isolated):
    def test_plugins_are_matched_by_repository_owner(self):
        found = monitor.discover_plugins("UBRUCKHAUS", CATALOG)
        self.assertEqual([p["id"] for p in found], ["ubruckhaus.beta", "ubruckhaus.alpha"])  # by listing date
        alpha = found[1]
        self.assertEqual((alpha["repo_name"], alpha["publish_date"], alpha["catalog_stars"]), ("omarchy-alpha", "2026-10-01", 3))
        self.assertTrue(alpha["verified"])
        self.assertEqual(found[0]["repo_name"], "omarchy-beta")
        self.assertEqual(monitor.discover_plugins("someone-else", CATALOG), [])

    def test_account_validation(self):
        for good in ("uBruckhaus", "a", "a-b-c", "x" * 39):
            self.assertTrue(monitor.valid_account(good), good)
        for bad in ("", "-start", "a b", "a/b", "x" * 40, "u;rm", "Uwe Bruckhaus", None):
            self.assertFalse(monitor.valid_account(bad), bad)
        self.assertEqual(monitor.set_author("bad name")["status"], "error")
        self.assertEqual(monitor.set_author("uBruckhaus")["author"], "uBruckhaus")
        with patch("monitor.gh_login", return_value="ghuser"):
            self.assertEqual(monitor.set_author("")["author"], "ghuser")
            self.assertEqual(monitor.resolve_account(monitor.load_config()), "ghuser")

    def test_missing_account_asks_for_one(self):
        with patch("monitor.detect_account", return_value=("", "")), patch("monitor.fetch_catalog", return_value=CATALOG):
            result = monitor.query_metrics()
        self.assertTrue(result["needs_account"])

    def test_status_matches_verify_issue_by_plugin_id(self):
        issues = [{"number": 7, "title": "[Verify]: New Name 2.0", "body": "### Plugin ID\n\nubruckhaus.alpha\n",
                   "state": "OPEN", "labels": [{"name": "security-review-required"}], "url": "u"}]
        status = monitor.determine_status({"name": "Alpha", "id": "ubruckhaus.alpha", "repo_name": "omarchy-alpha"}, issues)
        self.assertEqual(status[:3], ("Security Review", "review", 7))

    def test_query_uses_catalog_stats_and_records_history(self):
        stats = {"ubruckhaus.alpha": {"views": 10, "copies": 2, "hearts": 1}, "other.gamma": {"views": 99}}
        with patch("monitor.fetch_marketplace_stats", return_value=stats), patch("monitor.fetch_catalog", return_value=CATALOG), \
             patch("monitor.fetch_marketplace_issues", return_value=[]), patch("monitor.fetch_github_repos", return_value={}):
            result = monitor.query_metrics(author="uBruckhaus")
        self.assertEqual(result["total_views"], 10)
        self.assertEqual({p["id"] for p in result["plugins"]}, {"ubruckhaus.alpha", "ubruckhaus.beta"})
        alpha = next(p for p in result["plugins"] if p["id"] == "ubruckhaus.alpha")
        self.assertEqual((alpha["stars"], alpha["status_text"], alpha["version"]), (3, "Listed & Verified", "1.0"))
        history = json.loads((monitor.get_state_dir() / "history.json").read_text())
        self.assertEqual(list(history["days"].values())[0]["ubruckhaus.alpha"], [10, 2, 1, 3])


class DetectionTests(Isolated):
    def test_gh_hosts_file(self):
        gh = Path(os.environ["XDG_CONFIG_HOME"]) / "gh"
        gh.mkdir(parents=True)
        (gh / "hosts.yml").write_text("github.com:\n    git_protocol: https\n    users:\n        Some-User:\n    user: Some-User\n"
                                      "gitlab.example:\n    user: other\n")
        self.assertEqual(monitor.gh_config_user(), "Some-User")
        (gh / "hosts.yml").write_text("github.com:\n    user: bad;name\n")
        self.assertEqual(monitor.gh_config_user(), "")
        (gh / "hosts.yml").write_text("enterprise.example:\n    user: someone\n")
        self.assertEqual(monitor.gh_config_user(), "")

    def test_noreply_email(self):
        self.assertEqual(monitor.noreply_user("12345+uBruckhaus@users.noreply.github.com"), "uBruckhaus")
        self.assertEqual(monitor.noreply_user("uBruckhaus@users.noreply.github.com"), "uBruckhaus")
        for other in ("me@gmail.com", "x@users.noreply.github.com.evil", "", None):
            self.assertEqual(monitor.noreply_user(other), "")

    def test_installed_checkouts_count_only_own_plugin_ids(self):
        home = Path(self.tmp.name) / "home"
        def checkout(name, url):
            git = home / ".config/omarchy/plugins" / name / ".git"
            git.mkdir(parents=True)
            (git / "config").write_text(f'[remote "origin"]\n\turl = {url}\n')
        checkout("alice.one", "https://github.com/Alice/omarchy-one.git")
        checkout("alice.two", "git@github.com:Alice/omarchy-two.git")
        checkout("bob.three", "https://github.com/someone/three.git")   # someone else's plugin
        checkout("plain", "https://github.com/Plain/plain.git")         # no plugin ID
        with patch("pathlib.Path.home", return_value=home):
            self.assertEqual(monitor.plugin_checkout_owners(), ["Alice"])

    def test_detection_prefers_account_with_listed_plugins(self):
        with patch("monitor.gh_config_user", return_value="workaccount"), patch("monitor.git_config", return_value=""), \
             patch("monitor.plugin_checkout_owners", return_value=["uBruckhaus"]):
            self.assertEqual(monitor.detect_account(CATALOG), ("uBruckhaus", "installed plugins"))
            self.assertEqual(monitor.detect_account(), ("workaccount", "gh"))
        with patch("monitor.gh_config_user", return_value=""), patch("monitor.gh_login", return_value=""), \
             patch("monitor.git_config", return_value=""), patch("monitor.plugin_checkout_owners", return_value=[]):
            self.assertEqual(monitor.detect_account(CATALOG), ("", ""))


class HistoryTests(Isolated):
    def record(self, day, views, stars=0):
        monitor.record_history({"p.a": {"views": views, "downloads": 1, "hearts": 0, "stars": stars},
                                "p.b": {"views": 100, "downloads": 0, "hearts": 0, "stars": 0}}, today=day)

    def test_daily_gains_and_missing_days(self):
        self.record(date(2026, 10, 9), 10)
        self.record(date(2026, 10, 10), 15)
        self.record(date(2026, 10, 10), 18)   # same day: the latest snapshot wins
        self.record(date(2026, 10, 11), 25)
        series = monitor.history_series("p.a", "views", "daily", today=date(2026, 10, 11))
        self.assertEqual(len(series["labels"]), 30)
        self.assertEqual(series["values"][-3:], [0, 8, 7])
        self.assertEqual(series["totals"][-1], 25)
        self.assertIsNone(series["values"][0])           # before history started
        self.assertEqual(series["first_day"], "2026-10-09")
        everything = monitor.history_series("all", "views", "daily", today=date(2026, 10, 11))
        self.assertEqual(everything["totals"][-1], 125)

    def test_weekly_and_monthly_buckets(self):
        self.record(date(2026, 9, 28), 0)      # Monday, week 40
        self.record(date(2026, 10, 4), 30)     # Sunday, week 40
        self.record(date(2026, 10, 11), 50)    # Sunday, week 41
        weekly = monitor.history_series("p.a", "views", "weekly", today=date(2026, 10, 11))
        self.assertEqual(weekly["labels"][-2:], ["W40", "W41"])
        self.assertEqual(weekly["values"][-2:], [30, 20])
        monthly = monitor.history_series("p.a", "views", "monthly", today=date(2026, 10, 11))
        self.assertEqual(monthly["labels"][-2:], ["Sep", "Oct"])
        self.assertEqual(monthly["values"][-2:], [0, 50])

    def test_bad_requests_and_pruning(self):
        self.assertEqual(monitor.history_series("p.a", "rm -rf", "daily")["status"], "error")
        self.assertEqual(monitor.history_series("p.a", "views", "yearly")["status"], "error")
        for n in range(monitor.HISTORY_DAYS + 5):
            self.record(date.fromordinal(date(2025, 1, 1).toordinal() + n), n)
        days = json.loads((monitor.get_state_dir() / "history.json").read_text())["days"]
        self.assertEqual(len(days), monitor.HISTORY_DAYS)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


class HttpTests(unittest.TestCase):
    """http_get must cap size and time for hostile replies."""

    def serve(self, handler):
        server = Server(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}/"

    def test_oversized_and_endless_and_gzip_bomb(self):
        class Big(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_GET(self):
                if self.path == "/big":
                    self.send_response(200); self.send_header("Content-Length", str(10**9)); self.end_headers()
                elif self.path == "/endless":
                    self.send_response(200); self.end_headers()
                    try:
                        while True:
                            self.wfile.write(b"x" * 65536)
                    except Exception:
                        pass
                elif self.path == "/bomb":
                    body = gzip.compress(b"0" * (5 * 1024 * 1024))
                    self.send_response(200); self.send_header("Content-Encoding", "gzip")
                    self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
                elif self.path == "/etag":
                    if self.headers.get("If-None-Match") == '"v1"':
                        self.send_response(304); self.end_headers()
                    else:
                        self.send_response(200); self.send_header("ETag", '"v1"'); self.send_header("Content-Length", "2")
                        self.end_headers(); self.wfile.write(b"{}")
        base = self.serve(Big)
        for path in ("big", "endless", "bomb"):
            with self.assertRaises(ValueError, msg=path):
                monitor.http_get(base + path, 1024 * 1024, timeout=3)
        self.assertEqual(monitor.http_get(base + "etag", 1024)[0], 200)
        self.assertEqual(monitor.http_get(base + "etag", 1024, etag='"v1"')[0], 304)

    def test_slow_drip_hits_the_deadline(self):
        import time
        class Drip(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_GET(self):
                self.send_response(200); self.end_headers()
                try:
                    for _ in range(100):
                        self.wfile.write(b"x"); self.wfile.flush(); time.sleep(0.2)
                except Exception:
                    pass
        base = self.serve(Drip)
        start = time.monotonic()
        with self.assertRaises(ValueError):
            monitor.http_get(base, 1024 * 1024, timeout=2)
        self.assertLess(time.monotonic() - start, 6)


if __name__ == "__main__":
    unittest.main()


class SafeguardTests(unittest.TestCase):
    def test_bounded_runner_caps_output_and_time(self):
        import time
        self.assertEqual(monitor.run_bounded(["printf", "hello"], limit=100, timeout=5), (0, "hello"))
        with self.assertRaises(ValueError):
            monitor.run_bounded(["yes"], limit=64 * 1024, timeout=5)          # endless output
        start = time.monotonic()
        with self.assertRaises(TimeoutError):
            monitor.run_bounded(["sleep", "30"], limit=1024, timeout=1)       # never answers
        self.assertLess(time.monotonic() - start, 5)

    def test_only_github_and_marketplace_links_open(self):
        with patch("monitor.subprocess.Popen") as popen:
            for bad in ("http://github.com/x", "https://evil.example/x", "https://github.com.evil.example/",
                        "https://user:pw@github.com/x", "file:///etc/passwd", "javascript:alert(1)", "", None):
                self.assertEqual(monitor.open_url(bad)["status"], "error", bad)
            popen.assert_not_called()
            self.assertEqual(monitor.open_url("https://github.com/uBruckhaus/x")["status"], "ok")
            self.assertEqual(monitor.open_url("https://plugins.omarchy.org/plugin.html?id=a.b")["status"], "ok")

    def test_redirects_are_refused(self):
        class Redirect(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_GET(self):
                self.send_response(302); self.send_header("Location", "http://169.254.169.254/"); self.end_headers()
        server = Server(("127.0.0.1", 0), Redirect)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        with self.assertRaises(Exception):
            monitor.http_get(f"http://127.0.0.1:{server.server_address[1]}/", 1024, timeout=3)
