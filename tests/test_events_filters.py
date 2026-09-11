import copy
import unittest

from gitbot import events, filters
from tests import fixtures


class PushParsing(unittest.TestCase):
    def test_default_branch_push(self):
        p = events.parse_push(fixtures.push())
        self.assertEqual(p.branch, "main")
        self.assertFalse(p.is_tag)
        self.assertFalse(p.is_new_branch)
        self.assertEqual(p.commits[0].author_login, "eKisNonos")

    def test_tag_push(self):
        p = events.parse_push(fixtures.push(ref="refs/tags/v0.9.2", commits=[]))
        self.assertTrue(p.is_tag)
        self.assertEqual(p.tag_name, "v0.9.2")

    def test_new_and_deleted_branch(self):
        self.assertTrue(events.parse_push(fixtures.push(before=fixtures.ZERO)).is_new_branch)
        self.assertTrue(events.parse_push(fixtures.push(after=fixtures.ZERO)).is_deleted_branch)


class PushFilter(unittest.TestCase):
    def test_only_default_branch(self):
        self.assertEqual(filters.decide_push(events.parse_push(fixtures.push()))[0], filters.POST)
        feature = events.parse_push(fixtures.push(ref="refs/heads/feature-x"))
        self.assertEqual(filters.decide_push(feature)[0], filters.SKIP)

    def test_branch_create_delete_skipped(self):
        self.assertEqual(filters.decide_push(events.parse_push(fixtures.push(before=fixtures.ZERO)))[0], filters.SKIP)
        self.assertEqual(filters.decide_push(events.parse_push(fixtures.push(after=fixtures.ZERO)))[0], filters.SKIP)

    def test_tag_posts(self):
        tag = events.parse_push(fixtures.push(ref="refs/tags/v0.9.2", commits=[]))
        self.assertEqual(filters.decide_push(tag)[0], filters.POST)

    def test_private_repo_skipped(self):
        repo = copy.deepcopy(fixtures.REPO)
        repo["private"] = True
        self.assertEqual(filters.decide_push(events.parse_push(fixtures.push(repo=repo)))[0], filters.SKIP)


class PullRequestFilter(unittest.TestCase):
    def test_actions(self):
        for action, expect in [("opened", filters.POST), ("closed", filters.EDIT),
                               ("reopened", filters.EDIT), ("synchronized", filters.EDIT),
                               ("edited", filters.EDIT), ("labeled", filters.SKIP),
                               ("review_requested", filters.SKIP)]:
            pr = events.parse_pull_request(fixtures.pull_request(action=action))
            self.assertEqual(filters.decide_pull_request(pr, skip_drafts=True)[0], expect, action)

    def test_draft_skipped_on_open(self):
        pr = events.parse_pull_request(fixtures.pull_request(title="WIP: not ready"))
        self.assertEqual(filters.decide_pull_request(pr, skip_drafts=True)[0], filters.SKIP)
        self.assertEqual(filters.decide_pull_request(pr, skip_drafts=False)[0], filters.POST)

    def test_gh_number(self):
        pr = events.parse_pull_request(fixtures.pull_request())
        self.assertEqual(pr.gh_number, "485")
        native = events.parse_pull_request(fixtures.pull_request(head_label="eKisNonos/repo:feature"))
        self.assertEqual(native.gh_number, "")


class ReleaseFilter(unittest.TestCase):
    def test_published_only(self):
        self.assertEqual(filters.decide_release(events.parse_release(fixtures.release()))[0], filters.POST)
        drafted = events.parse_release(fixtures.release(action="edited"))
        self.assertEqual(filters.decide_release(drafted)[0], filters.SKIP)
