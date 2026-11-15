import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools
from brain import Brain
from tools import ReminderService, ToolError


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(tools, "get_data_dir",
                                    return_value=self.tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.brain = Brain(launcher=lambda x: None, opener=lambda x: None,
                           reminders=ReminderService())

    def _set_confirm(self, mode):
        tools.save_settings({"confirm_mode": mode})

    def test_standard_mode_runs_python_directly(self):
        self._set_confirm("standard")
        path = os.path.join(self.tmp.name, "hello.py")
        with open(path, "w") as f:
            f.write("print('hi')\n")
        reply, mood = self.brain.handle(f"run python {path}")
        self.assertIn("Exit code 0", reply)
        self.assertEqual(mood, "celebrating")

    def test_strict_mode_asks_before_running(self):
        self._set_confirm("strict")
        path = os.path.join(self.tmp.name, "hello.py")
        with open(path, "w") as f:
            f.write("print('hi')\n")
        reply, mood = self.brain.handle(f"run python {path}")
        self.assertEqual(mood, "waiting")
        self.assertIn("Strict mode", reply)
        reply, mood = self.brain.handle("yes")
        self.assertIn("Exit code 0", reply)
        self.assertEqual(mood, "celebrating")

    def test_strict_mode_asks_before_overwrite(self):
        self._set_confirm("strict")
        path = os.path.join(self.tmp.name, "notes.txt")
        with open(path, "w") as f:
            f.write("old\n")
        reply, mood = self.brain.handle(f"create file {path} with new words")
        self.assertEqual(mood, "waiting")
        reply, _ = self.brain.handle("no")
        self.assertIn("leaving the existing file alone", reply)
        with open(path) as f:
            self.assertEqual(f.read(), "old\n")

    def test_power_action_needs_confirmation(self):
        reply, mood = self.brain.handle("sleep computer")
        self.assertEqual(mood, "waiting")
        reply, _ = self.brain.handle("no")
        self.assertIn("not touching the power", reply)

    def test_wifi_and_brightness_honest_off_windows(self):
        if os.name == "nt":
            self.skipTest("Windows-only behaviour differs")
        with self.assertRaises(ToolError):
            tools.wifi_toggle(True)
        with self.assertRaises(ToolError):
            tools.set_brightness(50)

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_git_commit_and_branch(self):
        repo = os.path.join(self.tmp.name, "repo")
        os.makedirs(repo)
        subprocess.run(["git", "init", "-q", repo], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.email", "t@t"],
                       check=True)
        subprocess.run(["git", "-C", repo, "config", "user.name", "T"],
                       check=True)
        with open(os.path.join(repo, "a.txt"), "w") as f:
            f.write("hi\n")
        reply, mood = self.brain.handle(
            f'git commit in {repo} message "first"')
        self.assertEqual(mood, "celebrating")
        reply, mood = self.brain.handle(f"git branch in {repo} feature-x")
        self.assertEqual(mood, "celebrating")
        self.assertIn("feature-x", reply)

    def test_run_script_python(self):
        path = os.path.join(self.tmp.name, "s.py")
        with open(path, "w") as f:
            f.write("print('script ran')\n")
        reply, mood = self.brain.handle(f"run script {path}")
        self.assertIn("script ran", reply)

    def test_recent_work_lists_creations(self):
        self._set_confirm("standard")
        path = os.path.join(self.tmp.name, "log.txt")
        self.brain.handle(f"create file {path} with hello")
        reply, _ = self.brain.handle("recent work")
        self.assertIn("create file", reply)
        self.assertIn("log.txt", reply)


if __name__ == "__main__":
    unittest.main()
