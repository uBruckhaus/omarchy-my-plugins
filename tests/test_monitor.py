import unittest
import os
import sys
import json
import tempfile
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))
import monitor

class TestMonitor(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.orig_runtime = os.environ.get("XDG_RUNTIME_DIR")
        self.orig_state = os.environ.get("XDG_STATE_HOME")
        self.orig_config = os.environ.get("XDG_CONFIG_HOME")

        tmp_path = Path(self.tmp_dir.name)
        os.environ["XDG_RUNTIME_DIR"] = str(tmp_path / "runtime")
        os.environ["XDG_STATE_HOME"] = str(tmp_path / "state")
        os.environ["XDG_CONFIG_HOME"] = str(tmp_path / "config")
        (tmp_path / "runtime").mkdir(mode=0o700, exist_ok=True)
        (tmp_path / "state").mkdir(mode=0o700, exist_ok=True)
        (tmp_path / "config").mkdir(mode=0o700, exist_ok=True)

    def tearDown(self):
        if self.orig_runtime:
            os.environ["XDG_RUNTIME_DIR"] = self.orig_runtime
        else:
            os.environ.pop("XDG_RUNTIME_DIR", None)

        if self.orig_state:
            os.environ["XDG_STATE_HOME"] = self.orig_state
        else:
            os.environ.pop("XDG_STATE_HOME", None)

        if self.orig_config:
            os.environ["XDG_CONFIG_HOME"] = self.orig_config
        else:
            os.environ.pop("XDG_CONFIG_HOME", None)

        self.tmp_dir.cleanup()

    def test_runtime_lock(self):
        with monitor.runtime_lock("test.lock"):
            lock_path = monitor.get_runtime_dir() / "test.lock"
            self.assertTrue(lock_path.is_file())

    def test_default_config(self):
        cfg = monitor.load_config()
        self.assertEqual(cfg["interval_minutes"], 5)
        self.assertEqual(len(cfg["plugins"]), 5)

    def test_set_interval(self):
        res = monitor.set_interval(15)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["interval_minutes"], 15)

        cfg = monitor.load_config()
        self.assertEqual(cfg["interval_minutes"], 15)

    def test_status_determination(self):
        issues = [
            {
                "title": "[Plugin]: Simple Recipes",
                "state": "OPEN",
                "number": 9889,
                "url": "https://github.com/omacom/omarchy-plugin-marketplace/issues/9889",
                "labels": [{"name": "needs-fixes"}, {"name": "validated"}]
            },
            {
                "title": "[Plugin]: Simple Tile",
                "state": "CLOSED",
                "number": 9165,
                "url": "https://github.com/omacom/omarchy-plugin-marketplace/issues/9165",
                "labels": [{"name": "listed"}, {"name": "approved-and-verified"}]
            }
        ]

        st_text, st_code, num, url = monitor.determine_status("Simple Recipes", issues)
        self.assertEqual(st_text, "Review: Needs Fixes")
        self.assertEqual(st_code, "needs_fixes")
        self.assertEqual(num, 9889)

        st_text, st_code, num, url = monitor.determine_status("Simple Tile", issues)
        self.assertEqual(st_text, "Listed & Verified")
        self.assertEqual(st_code, "verified")
        self.assertEqual(num, 9165)

    def test_publish_date_determination(self):
        # 1. Configured explicitly
        p_explicit = {"name": "Custom", "id": "custom", "publish_date": "2026-05-01"}
        self.assertEqual(monitor.determine_publish_date(p_explicit, []), "2026-05-01")

        # 2. Known default plugin
        p_launcher = {"name": "Simple Launcher", "id": "ubruckhaus.simple-launcher-for-fools"}
        self.assertEqual(monitor.determine_publish_date(p_launcher, []), "2026-09-27")

        p_tile = {"name": "Simple Tile", "id": "ubruckhaus.simple-tile"}
        self.assertEqual(monitor.determine_publish_date(p_tile, []), "2026-09-28")

        p_recipes = {"name": "Simple Recipes", "id": "ubruckhaus.simple-recipes"}
        self.assertEqual(monitor.determine_publish_date(p_recipes, []), "2026-10-03")

        # 3. Dynamic lookup from marketplace issues
        issues = [
            {
                "title": "[Plugin]: Another Plugin",
                "createdAt": "2026-08-15T12:00:00Z",
                "closedAt": "2026-08-17T15:30:00Z"
            }
        ]
        p_dynamic = {"name": "Another Plugin", "id": "org.another.plugin"}
        self.assertEqual(monitor.determine_publish_date(p_dynamic, issues), "2026-08-17")

    def test_acknowledgement_flow(self):
        # Setup simulated snapshot with deltas
        state_dir = monitor.get_state_dir()
        snapshot_file = state_dir / "snapshot.json"
        ack_file = state_dir / "acknowledged.json"

        simulated_snapshot = {
            "status": "ok",
            "has_changes": True,
            "changes_summary": "Simple Launcher: +5 views",
            "plugins": [
                {
                    "id": "ubruckhaus.simple-launcher-for-fools",
                    "name": "Simple Launcher",
                    "views": 100,
                    "views_delta": 5,
                    "downloads": 10,
                    "downloads_delta": 0,
                    "hearts": 0,
                    "hearts_delta": 0,
                    "stars": 0,
                    "stars_delta": 0,
                    "has_changes": True
                }
            ],
            "plugins_map": {
                "ubruckhaus.simple-launcher-for-fools": {
                    "views": 100,
                    "downloads": 10,
                    "hearts": 0,
                    "stars": 0,
                    "status_text": "Listed & Verified"
                }
            }
        }
        monitor.save_json_file(snapshot_file, simulated_snapshot)

        # Now acknowledge
        res = monitor.acknowledge_changes()
        self.assertFalse(res["has_changes"])
        self.assertEqual(res["changes_summary"], "")
        self.assertEqual(res["plugins"][0]["views_delta"], 0)
        self.assertFalse(res["plugins"][0]["has_changes"])

        # Check acknowledged.json was created
        self.assertTrue(ack_file.is_file())
        ack_data = monitor.load_json_file(ack_file)
        self.assertIn("ubruckhaus.simple-launcher-for-fools", ack_data["plugins_map"])
        self.assertEqual(ack_data["plugins_map"]["ubruckhaus.simple-launcher-for-fools"]["views"], 100)

    def test_set_author(self):
        res = monitor.set_author("ubruckhaus")
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["author"], "ubruckhaus")

        cfg = monitor.load_config()
        self.assertEqual(cfg["author"], "ubruckhaus")

        err = monitor.set_author("   ")
        self.assertEqual(err["status"], "error")

    def test_discover_plugins_by_author(self):
        # 1. Discover for default author ubruckhaus
        plugins = monitor.discover_plugins_by_author(author="ubruckhaus")
        plugin_ids = [p["id"] for p in plugins]
        self.assertIn("ubruckhaus.simple-launcher-for-fools", plugin_ids)
        self.assertIn("ubruckhaus.simple-tile", plugin_ids)
        self.assertIn("ubruckhaus.simple-reader", plugin_ids)
        self.assertIn("ubruckhaus.simple-recipes", plugin_ids)
        self.assertIn("ubruckhaus.video-trans", plugin_ids)

        # 2. Discover for custom author with mock repos and stats
        mock_repos = {
            "omarchy-cool-tool": {"description": "A very cool tool"},
            "omarchy-my-plugins": {"description": "Should be ignored"}
        }
        mock_stats = {
            "someone.cool-tool": {"views": 42},
            "someone.awesome-bar": {"views": 10}
        }
        discovered_custom = monitor.discover_plugins_by_author(
            author="someone",
            repos=mock_repos,
            stats=mock_stats
        )
        custom_ids = [p["id"] for p in discovered_custom]
        self.assertIn("someone.cool-tool", custom_ids)
        self.assertIn("someone.awesome-bar", custom_ids)
        self.assertNotIn("someone.my-plugins", custom_ids)

    def test_sort_plugins(self):
        plugins = [
            {"id": "a.x", "name": "Alpha", "views": 5, "downloads": 100, "hearts": 1, "stars": 0, "publish_date": "2026-01-02"},
            {"id": "b.x", "name": "Beta", "views": 50, "downloads": 10, "hearts": 0, "stars": 9, "publish_date": "2026-01-01"},
            {"id": "c.x", "name": "Gamma", "views": 50, "downloads": 5, "hearts": 2, "stars": 1, "publish_date": "2026-01-03"}
        ]

        # views desc (default), ties broken by ascending name
        r = monitor.sort_plugins(plugins, "views", "desc")
        self.assertEqual([p["id"] for p in r], ["b.x", "c.x", "a.x"])

        # views asc
        r = monitor.sort_plugins(plugins, "views", "asc")
        self.assertEqual([p["id"] for p in r], ["a.x", "b.x", "c.x"])

        # downloads desc
        r = monitor.sort_plugins(plugins, "downloads", "desc")
        self.assertEqual([p["id"] for p in r], ["a.x", "b.x", "c.x"])

        # name desc
        r = monitor.sort_plugins(plugins, "name", "desc")
        self.assertEqual([p["name"] for p in r], ["Gamma", "Beta", "Alpha"])

        # date desc = newest first
        r = monitor.sort_plugins(plugins, "date", "desc")
        self.assertEqual([p["id"] for p in r], ["c.x", "a.x", "b.x"])

        # invalid field/order fall back to defaults (views desc)
        r = monitor.sort_plugins(plugins, "bogus", "sideways")
        self.assertEqual(r[0]["id"], "b.x")

    def test_set_sort(self):
        res = monitor.set_sort("downloads", "asc")
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["sort_by"], "downloads")
        self.assertEqual(res["sort_order"], "asc")

        cfg = monitor.load_config()
        self.assertEqual(cfg["sort_by"], "downloads")
        self.assertEqual(cfg["sort_order"], "asc")

        # invalid values rejected, config unchanged
        err = monitor.set_sort("bogus", None)
        self.assertEqual(err["status"], "error")
        err = monitor.set_sort(None, "sideways")
        self.assertEqual(err["status"], "error")

        cfg = monitor.load_config()
        self.assertEqual(cfg["sort_by"], "downloads")
        self.assertEqual(cfg["sort_order"], "asc")

    def test_resolve_version(self):
        self.assertEqual(monitor.resolve_version("0.8.0", "v0.8.0"), "0.8.0")
        self.assertEqual(monitor.resolve_version("", "v0.2.6"), "0.2.6")
        self.assertEqual(monitor.resolve_version("1.3.2", ""), "1.3.2")
        self.assertEqual(monitor.resolve_version("", ""), "")
        self.assertEqual(monitor.resolve_version("0.3.0", "v0.3.3"), "0.3.0")

    def test_handle_request_configure_sort(self):
        state_dir = monitor.get_state_dir()
        snapshot_file = state_dir / "snapshot.json"

        snapshot = {
            "status": "ok",
            "plugins": [
                {"id": "u.low", "name": "Low", "views": 3, "downloads": 9, "hearts": 0, "stars": 0, "publish_date": ""},
                {"id": "u.high", "name": "High", "views": 99, "downloads": 1, "hearts": 0, "stars": 0, "publish_date": ""}
            ],
            "plugins_map": {}
        }
        monitor.save_json_file(snapshot_file, snapshot)

        # configure via settings: downloads asc -> High (1) before Low (9)
        res = monitor.handle_request({
            "command": "configure",
            "settings": {"sort_by": "downloads", "sort_order": "asc"}
        })
        cfg = monitor.load_config()
        self.assertEqual(cfg["sort_by"], "downloads")
        self.assertEqual(cfg["sort_order"], "asc")
        self.assertEqual([p["id"] for p in res["plugins"]], ["u.high", "u.low"])
        self.assertEqual(res["sort_by"], "downloads")
        self.assertEqual(res["sort_order"], "asc")

        # dedicated set_sort command: views desc -> High (99) first
        res = monitor.handle_request({"command": "set_sort", "sort_by": "views", "sort_order": "desc"})
        self.assertEqual(res["status"], "ok")
        self.assertEqual([p["id"] for p in res["plugins"]], ["u.high", "u.low"])

        # invalid sort rejected
        res = monitor.handle_request({"command": "set_sort", "sort_by": "bogus"})
        self.assertEqual(res["status"], "error")

    def test_query_metrics_sorted_by_views_desc(self):
        stats = {
            "ubruckhaus.aaa": {"views": 5, "copies": 1, "hearts": 0},
            "ubruckhaus.bbb": {"views": 50, "copies": 2, "hearts": 0},
            "ubruckhaus.ccc": {"views": 500, "copies": 3, "hearts": 0}
        }
        orig_stats = monitor.fetch_marketplace_stats
        orig_issues = monitor.fetch_marketplace_issues
        orig_repos = monitor.fetch_github_repos
        orig_releases = monitor.fetch_github_releases
        monitor.fetch_marketplace_stats = lambda author=None: stats
        monitor.fetch_marketplace_issues = lambda author=None: []
        monitor.fetch_github_repos = lambda author=None: {}
        monitor.fetch_github_releases = lambda author=None, repo_names=None: {}
        try:
            res = monitor.query_metrics()
        finally:
            monitor.fetch_marketplace_stats = orig_stats
            monitor.fetch_marketplace_issues = orig_issues
            monitor.fetch_github_repos = orig_repos
            monitor.fetch_github_releases = orig_releases

        self.assertEqual(res["sort_by"], "views")
        self.assertEqual(res["sort_order"], "desc")

        our_views = [p["views"] for p in res["plugins"] if p["id"].startswith("ubruckhaus.")]
        self.assertEqual(our_views, sorted(our_views, reverse=True))

        # marketplace deep link filters the catalog to the plugin
        for p in res["plugins"]:
            self.assertTrue(
                p["marketplace_url"].startswith("https://plugins.omarchy.org/?plugin=" + p["id"])
            )

        # every plugin record now carries version fields
        for p in res["plugins"]:
            self.assertIn("version", p)
            self.assertIn("local_version", p)
            self.assertIn("release_version", p)

        # installed plugins picked up their manifest version
        by_id = {p["id"]: p for p in res["plugins"]}
        self.assertTrue(by_id["ubruckhaus.simple-tile"]["local_version"])

        # get_current_status re-sorts cached snapshot with same result
        res2 = monitor.get_current_status()
        self.assertEqual(res2["sort_by"], "views")
        self.assertEqual(res2["sort_order"], "desc")

    def test_handle_request_author_and_configure(self):
        # Test configure with author and interval
        res = monitor.handle_request({
            "command": "configure",
            "settings": {"author": "ubruckhaus", "interval_minutes": 10}
        })
        self.assertEqual(res["interval_minutes"], 10)
        self.assertEqual(res["author"], "ubruckhaus")

        cfg = monitor.load_config()
        self.assertEqual(cfg["author"], "ubruckhaus")
        self.assertEqual(cfg["interval_minutes"], 10)

if __name__ == "__main__":
    unittest.main()
