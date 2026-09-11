import unittest

from gitbot.alerts import Alerter


class AlerterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.sent = []

    async def send(self, chat_id, text):
        self.sent.append((chat_id, text))

    async def test_off_without_admin_chat(self):
        a = Alerter(self.send, admin_chat_id=0)
        await a.fault("x", "detail")
        self.assertEqual(self.sent, [])

    async def test_sends_and_throttles_per_fault(self):
        a = Alerter(self.send, admin_chat_id=42, cooldown=1000)
        await a.fault("telegram", "down")
        await a.fault("telegram", "still down")   # throttled
        await a.fault("signature", "bad")         # different fault, sent
        self.assertEqual(len(self.sent), 2)
        self.assertEqual(self.sent[0][0], 42)
        self.assertIn("telegram", self.sent[0][1])
        self.assertIn("signature", self.sent[1][1])

    async def test_delivery_failure_is_swallowed(self):
        async def boom(chat_id, text):
            raise RuntimeError("telegram unreachable")
        a = Alerter(boom, admin_chat_id=42)
        await a.fault("x", "detail")  # must not raise
