import os
import stat
import tempfile
import unittest
from pathlib import Path

from gitbot.state import MAX_DELIVERIES, State


class DedupTests(unittest.TestCase):
    def test_seen_returns_true_on_repeat(self):
        st = State()
        self.assertFalse(st.seen("d1"))
        self.assertTrue(st.seen("d1"))
        self.assertFalse(st.seen("d2"))

    def test_empty_delivery_never_deduped(self):
        st = State()
        self.assertFalse(st.seen(""))
        self.assertFalse(st.seen(""))

    def test_ring_is_bounded(self):
        st = State()
        for i in range(MAX_DELIVERIES + 500):
            st.seen(f"d{i}")
        self.assertLessEqual(len(st.deliveries), MAX_DELIVERIES)
        self.assertFalse(st.seen("d0"))  # oldest evicted, so not seen anymore


class PrMessageTests(unittest.TestCase):
    def test_remember_and_lookup(self):
        st = State()
        st.remember_pr("NON-OS/x", 12, 555)
        self.assertEqual(st.pr_message("NON-OS/x", 12), 555)
        self.assertIsNone(st.pr_message("NON-OS/x", 13))


class PersistenceTests(unittest.TestCase):
    def test_roundtrip_and_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "sub" / "state.json"
            st = State()
            st.seen("d1")
            st.remember_pr("NON-OS/x", 12, 555)
            st.save(path)
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
            back = State.load(path)
            self.assertTrue(back.seen("d1"))
            self.assertEqual(back.pr_message("NON-OS/x", 12), 555)

    def test_corrupt_file_starts_fresh(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "state.json"
            path.write_text("{ not json")
            st = State.load(path)
            self.assertEqual(len(st.deliveries), 0)
