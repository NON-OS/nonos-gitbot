import unittest

from gitbot.events import parse_push
from gitbot.merges import pr_numbers
from tests import fixtures


class PrNumberTests(unittest.TestCase):
    def _nums(self, *messages):
        push = parse_push(fixtures.push(commits=[fixtures.commit(m) for m in messages]))
        return pr_numbers(push.commits)

    def test_merge_commit(self):
        self.assertEqual(self._nums("Merge pull request #12 from eKisNonos/vault"), [12])

    def test_squash_suffix(self):
        self.assertEqual(self._nums("A key only this machine can derive (#485)"), [485])

    def test_plain_commit_has_none(self):
        self.assertEqual(self._nums("Directory records as one layout"), [])

    def test_multiple_and_deduped(self):
        nums = self._nums(
            "Merge pull request #12 from a/b",
            "unrelated commit",
            "squash it (#13)",
            "Merge pull request #12 from a/b",
        )
        self.assertEqual(nums, [12, 13])

    def test_only_subject_line_scanned(self):
        # A number in the body must not be treated as a merge.
        self.assertEqual(self._nums("real subject\n\nsee also (#99)"), [])
