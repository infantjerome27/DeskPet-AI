import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools
from brain import Brain
from tools import ReminderService


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(tools, "get_data_dir",
                                    return_value=self.tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.brain = Brain(launcher=lambda x: None, opener=lambda x: None,
                           reminders=ReminderService())

    def test_speak_with_runner(self):
        said = []
        tools.speak("hello there", runner=said.append)
        self.assertEqual(said, ["hello there"])

    def test_speak_escapes_quotes(self):
        said = []
        tools.speak("it's fine", runner=said.append)
        self.assertEqual(said, ["it's fine"])

    def test_listen_with_runner(self):
        self.assertEqual(tools.listen(runner=lambda: "open notepad"),
                         "open notepad")

    def test_species_commands(self):
        reply, mood = self.brain.handle("be a cat")
        self.assertEqual(self.brain.settings_changed.get("pet_species"), "cat")
        self.assertEqual(mood, "happy")
        reply, _ = self.brain.handle("be a puppy")
        self.assertEqual(self.brain.settings_changed.get("pet_species"), "puppy")
        reply, _ = self.brain.handle("be a muse")
        self.assertEqual(self.brain.settings_changed.get("pet_species"), "muse")
        self.assertIn("Muse", reply)
        reply, _ = self.brain.handle("be a real dog")
        self.assertEqual(self.brain.settings_changed.get("pet_species"), "real_dog")
        self.assertIn("border collie", reply)

    def test_voice_and_autonomy_toggles(self):
        _, _ = self.brain.handle("turn voice off")
        self.assertIs(self.brain.settings_changed.get("voice"), False)
        _, _ = self.brain.handle("autonomy off")
        self.assertIs(self.brain.settings_changed.get("autonomy"), False)

    def test_say_command_is_honest_off_windows(self):
        reply, mood = self.brain.handle("say hello")
        if os.name != "nt":
            self.assertIn("only works on Windows", reply)
        else:
            self.assertEqual(mood, "speaking")

    def test_good_boy_reaction(self):
        reply, mood = self.brain.handle("good boy!")
        self.assertEqual(mood, "love")


if __name__ == "__main__":
    unittest.main()
