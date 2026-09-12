import asyncio
import unittest

from gitbot.batcher import CommitBatcher, merge
from gitbot.events import parse_push
from tests import fixtures


class MergeTests(unittest.TestCase):
    def test_combines_commits_and_range(self):
        p1 = parse_push(
            fixtures.push(before="a" * 40, after="b" * 40, commits=[fixtures.commit("one"), fixtures.commit("two")])
        )
        p2 = parse_push(fixtures.push(before="b" * 40, after="c" * 40, commits=[fixtures.commit("three")]))
        m = merge([p1, p2])
        self.assertEqual(m.total_commits, 3)
        self.assertEqual([c.message for c in m.commits], ["one", "two", "three"])
        self.assertEqual(m.before, "a" * 40)
        self.assertEqual(m.after, "c" * 40)
        self.assertIn("/compare/" + "a" * 40 + "..." + "c" * 40, m.compare_url)


class BatcherTests(unittest.IsolatedAsyncioTestCase):
    async def test_window_off_flushes_each_immediately(self):
        flushed = []
        b = CommitBatcher(0, lambda pushes: flushed.append(pushes))
        b.add(parse_push(fixtures.push()))
        b.add(parse_push(fixtures.push()))
        self.assertEqual(len(flushed), 2)
        self.assertTrue(all(len(f) == 1 for f in flushed))

    async def test_window_coalesces_same_branch(self):
        flushed = []
        b = CommitBatcher(0.02, lambda pushes: flushed.append(pushes))
        b.add(parse_push(fixtures.push(commits=[fixtures.commit("a")])))
        b.add(parse_push(fixtures.push(commits=[fixtures.commit("b")])))
        self.assertEqual(flushed, [])  # still held
        await asyncio.sleep(0.05)
        self.assertEqual(len(flushed), 1)
        self.assertEqual(len(flushed[0]), 2)

    async def test_flush_all_sends_pending(self):
        flushed = []
        b = CommitBatcher(10, lambda pushes: flushed.append(pushes))
        b.add(parse_push(fixtures.push()))
        b.flush_all()
        self.assertEqual(len(flushed), 1)
