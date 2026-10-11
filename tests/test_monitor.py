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
        self.assertEqual(cfg["plugins"], [])
        self.assertEqual(cfg["author"], "")  # empty: the gh login is used

    def test_set_interval(self):
        res = monitor.set_interval(15)
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["interval_minutes"], 15)

        cfg = monitor.load_config()
        self.assertEqual(cfg["interval_minutes"], 15)

    def test_sort_settings_migrate_outside_watched_plugin_directory(self):
        config_home = Path(os.environ["XDG_CONFIG_HOME"])
        legacy_file = config_home / "omarchy" / "plugins" / "ubruckhaus.my-plugins" / "config.json"
        legacy_file.parent.mkdir(parents=True)
        legacy = {"author": "example", "interval_minutes": 15,
                  "sort_by": "stars", "sort_order": "asc", "plugins": []}
        legacy_text = json.dumps(legacy)
        legacy_file.write_text(legacy_text)

        self.assertEqual(monitor.load_config(), legacy)
        self.assertEqual(monitor.set_sort("name", "desc")["status"], "ok")

        settings_file = config_home / "omarchy" / "my-plugins" / "config.json"
        self.assertTrue(settings_file.is_file())
        self.assertEqual(legacy_file.read_text(), legacy_text)
        saved = monitor.load_config()
        self.assertEqual(saved["sort_by"], "name")
        self.assertEqual(saved["sort_order"], "desc")
        self.assertEqual(saved["author"], "example")
        self.assertEqual(saved["interval_minutes"], 15)

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

        # Blank means: follow the gh login; names with spaces or slashes are refused.
        original = monitor.gh_login
        monitor.gh_login = lambda: "ghuser"
        try:
            blank = monitor.set_author("   ")
        finally:
            monitor.gh_login = original
        self.assertEqual((blank["status"], blank["author"]), ("ok", "ghuser"))
        self.assertEqual(monitor.load_config()["author"], "")
        self.assertEqual(monitor.set_author("a b")["status"], "error")

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
