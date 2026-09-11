import unittest

from gitbot import events, render
from gitbot.authors import author_from_body
from tests import fixtures


class PushRender(unittest.TestCase):
    def test_shows_authors_not_pusher(self):
        p = events.parse_push(fixtures.push(pusher="nonos-sync"))
        out = render.render_push(p, max_commits=5, summary_chars=90)
        self.assertIn("eKisNonos", out)
        self.assertNotIn("nonos-sync", out)
        self.assertIn("nonos-micro-kernel", out)
        self.assertIn("main", out)

    def test_first_line_only_and_trim(self):
        long = "x" * 200 + "\nsecond line"
        p = events.parse_push(fixtures.push(commits=[fixtures.commit(long)]))
        out = render.render_push(p, max_commits=5, summary_chars=90)
        self.assertNotIn("second line", out)
        self.assertIn("…", out)

    def test_caps_commits_with_and_more(self):
        commits = [fixtures.commit(f"commit {i}") for i in range(9)]
        p = events.parse_push(fixtures.push(commits=commits, total=9))
        out = render.render_push(p, max_commits=5, summary_chars=90)
        self.assertEqual(out.count("· commit"), 5)
        self.assertIn("and 4 more", out)

    def test_multiple_authors_label(self):
        commits = [fixtures.commit("a", login="alice"), fixtures.commit("b", login="bob")]
        p = events.parse_push(fixtures.push(commits=commits, total=2))
        out = render.render_push(p, max_commits=5, summary_chars=90)
        self.assertIn("alice and bob", out)

    def test_html_escaped(self):
        p = events.parse_push(fixtures.push(commits=[fixtures.commit("fix <script> & stuff")]))
        out = render.render_push(p, max_commits=5, summary_chars=90)
        self.assertIn("&lt;script&gt;", out)
        self.assertNotIn("<script>", out)


class PullRequestRender(unittest.TestCase):
    def test_opened_and_merged_headline(self):
        opened = events.parse_pull_request(fixtures.pull_request(action="opened"))
        self.assertIn("Pull request opened", render.render_pull_request(opened, "eKisNonos"))
        merged = events.parse_pull_request(fixtures.pull_request(action="closed", merged=True, state="closed"))
        self.assertIn("Pull request merged", render.render_pull_request(merged, "eKisNonos"))
        closed = events.parse_pull_request(fixtures.pull_request(action="closed", merged=False, state="closed"))
        self.assertIn("Pull request closed", render.render_pull_request(closed, "eKisNonos"))

    def test_shows_gh_number_and_author(self):
        pr = events.parse_pull_request(fixtures.pull_request())
        out = render.render_pull_request(pr, "eKisNonos")
        self.assertIn("#12", out)
        self.assertIn("GitHub #485", out)
        self.assertIn("eKisNonos", out)


class ReleaseRender(unittest.TestCase):
    def test_release(self):
        out = render.render_release(events.parse_release(fixtures.release()))
        self.assertIn("Release published", out)
        self.assertIn("NONOS 0.9.2", out)
        self.assertIn("1 asset", out)


class AuthorExtraction(unittest.TestCase):
    def test_from_body(self):
        self.assertEqual(author_from_body("Opened on GitHub by eKisNonos as pull request 485."), "eKisNonos")
        self.assertEqual(author_from_body("no author here"), "")


class CaptionLimit(unittest.TestCase):
    def test_fit_caption_trims_to_limit(self):
        from gitbot.telegram import CAPTION_LIMIT, fit_caption
        short = "hello"
        self.assertEqual(fit_caption(short), short)
        long = "x" * 2000
        out = fit_caption(long)
        self.assertLessEqual(len(out), CAPTION_LIMIT)
        self.assertTrue(out.endswith("…"))
