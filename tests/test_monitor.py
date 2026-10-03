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

if __name__ == "__main__":
    unittest.main()
