import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))
import monitor


def record(i, owner="uBruckhaus"):
    return {"id": f"ubruckhaus.p{i}", "name": f"P{i}", "repo": f"https://github.com/{owner}/p{i}",
            "description": "d", "listedAt": "2026-10-01"}


class CatalogBounds(unittest.TestCase):
    def fetch(self, entries):
        body = json.dumps({"plugins": entries}).encode()
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(monitor, "http_get", return_value=(200, body, None)):
            start = time.monotonic()
            catalog = monitor.fetch_catalog(Path(tmp), now=1000.0)
            cached = monitor.fetch_catalog(Path(tmp), now=1001.0)
            return catalog, cached, time.monotonic() - start

    def test_duplicate_records_give_one_card(self):
        # A catalog endpoint repeating the same small record 200,000 times (well under 64 MiB).
        catalog, cached, took = self.fetch([record(1)] * 200_000)
        self.assertEqual(len(catalog), 1)
        self.assertEqual(len(cached), 1)
        self.assertEqual(len(monitor.discover_plugins("uBruckhaus", catalog)), 1)
        self.assertLess(took, 5)

    def test_many_distinct_records_capped(self):
        catalog, _cached, _took = self.fetch([record(i) for i in range(50_000)])
        self.assertEqual(len(catalog), monitor.MAX_CATALOG_PLUGINS)
        found = monitor.discover_plugins("uBruckhaus", catalog)
        self.assertEqual(len(found), monitor.MAX_TRACKED_PLUGINS)
        self.assertEqual(len({p["id"] for p in found}), len(found))

    def test_discover_dedupes_unfiltered_input(self):
        found = monitor.discover_plugins("uBruckhaus", [record(1), record(1), record(2, "someone")] * 1000)
        self.assertEqual([p["id"] for p in found], ["ubruckhaus.p1"])

    def test_long_strings_and_odd_values_cut(self):
        entry = dict(record(1), description="x" * 5_000_000, name=["not", "text"], stars={"a": 1})
        catalog, _cached, _took = self.fetch([entry, "junk", {"id": 5}, {"id": ""}])
        self.assertEqual(len(catalog), 1)
        self.assertEqual(len(catalog[0]["description"]), monitor.MAX_FIELD_CHARS)
        self.assertIsNone(catalog[0]["name"])
        self.assertIsNone(catalog[0]["stars"])


if __name__ == "__main__":
    unittest.main()
