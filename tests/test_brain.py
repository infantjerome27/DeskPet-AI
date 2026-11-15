import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain import Brain
from tools import ReminderService


class BrainTests(unittest.TestCase):
    def setUp(self):
        self.launched = []
        self.opened = []
        self.brain = Brain(launcher=self.launched.append,
                           opener=self.opened.append,
                           reminders=ReminderService())

    def test_greeting(self):
        reply, mood = self.brain.handle("hello")
        self.assertIn("Hello", reply)
        self.assertEqual(mood, "happy")

    def test_remember_name(self):
        reply, mood = self.brain.handle("my name is Priya")
        self.assertEqual(self.brain.user_name, "Priya")
        self.assertIn("Priya", reply)
        reply, _ = self.brain.handle("hello")
        self.assertIn("Priya", reply)

    def test_calculator(self):
        reply, _ = self.brain.handle("calculate 12 * 8 + 5")
        self.assertIn("101", reply)

    def test_calculator_rejects_code(self):
        reply, mood = self.brain.handle("calculate __import__('os').system('x')")
        self.assertNotIn("Traceback", reply)
        self.assertEqual(mood, "sad")

    def test_time_and_date(self):
        reply, _ = self.brain.handle("what time is it")
        self.assertIn(":", reply)
        reply, _ = self.brain.handle("what is today's date")
        self.assertIn("202", reply)

    def test_open_app_uses_launcher(self):
        reply, mood = self.brain.handle("open notepad")
        self.assertEqual(self.launched, ["notepad"])
        self.assertEqual(mood, "happy")

    def test_web_search_uses_opener(self):
        reply, _ = self.brain.handle("search the web for cute cats")
        self.assertTrue(self.opened)
        self.assertIn("cute+cats", self.opened[0])

    def test_delete_needs_confirmation(self):
        reply, mood = self.brain.handle("delete somefile.txt")
        self.assertIn("Are you sure", reply)
        self.assertEqual(mood, "waiting")
        reply, _ = self.brain.handle("no")
        self.assertIn("won't delete", reply)

    def test_unknown_is_honest(self):
        reply, mood = self.brain.handle("book me a flight to the moon")
        self.assertIn("don't know how", reply)
        self.assertIn("help", reply)

    def test_help_lists_commands(self):
        reply, _ = self.brain.handle("help")
        self.assertIn("open notepad", reply.lower())
        self.assertIn("calculate", reply.lower())


if __name__ == "__main__":
    unittest.main()
