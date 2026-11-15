import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools
from brain import Brain
from tools import OFFICE_EXES, WINDOWS_APPS, ReminderService, resolve_path


class AppsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(tools, "get_data_dir",
                                    return_value=self.tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.launched = []
        self.opened = []

        def launcher(*args):
            self.launched.append(args)

        def opener(url):
            self.opened.append(url)

        self.brain = Brain(launcher=launcher, opener=opener,
                           reminders=ReminderService())

    def test_office_map_entries(self):
        self.assertEqual(WINDOWS_APPS["word"], "winword")
        self.assertEqual(WINDOWS_APPS["excel"], "excel")
        self.assertEqual(WINDOWS_APPS["powerpoint"], "powerpnt")
        self.assertEqual(WINDOWS_APPS["outlook"], "outlook")
        self.assertEqual(OFFICE_EXES["word"], "WINWORD.EXE")

    def test_open_office_app(self):
        reply, mood = self.brain.handle("open word")
        self.assertEqual(mood, "happy")
        self.assertIn("Opening word", reply)
        self.assertEqual(self.launched, [("word",)])

    def test_open_unknown_app_is_attempted(self):
        reply, _ = self.brain.handle("open photoshop")
        self.assertIn("Opening photoshop", reply)
        self.assertEqual(self.launched, [("photoshop",)])

    def test_open_copilot_and_office365_in_browser(self):
        reply, _ = self.brain.handle("open copilot")
        self.assertIn("browser", reply)
        self.assertEqual(self.opened, ["https://copilot.microsoft.com"])
        self.brain.handle("open office 365")
        self.assertEqual(self.opened[-1], "https://www.office.com")
        self.brain.handle("open teams")
        self.assertEqual(self.opened[-1], "https://teams.microsoft.com")

    def test_ask_copilot_copies_question_and_opens(self):
        reply, _ = self.brain.handle("ask copilot what is a pivot table")
        self.assertIn("paste it there", reply)
        self.assertEqual(self.opened, ["https://copilot.microsoft.com"])
        self.assertEqual(tools.clipboard_paste(), "what is a pivot table")

    def test_open_app_with_file(self):
        docx = os.path.join(self.tmp.name, "Report.docx")
        with open(docx, "w") as f:
            f.write("x")
        reply, mood = self.brain.handle(f"open word with {docx}")
        self.assertEqual(mood, "happy")
        self.assertEqual(self.launched, [("word", docx)])

    def test_open_file_uses_default_app(self):
        docx = os.path.join(self.tmp.name, "Report.docx")
        with open(docx, "w") as f:
            f.write("x")
        reply, _ = self.brain.handle(f"open file {docx}")
        self.assertIn("Opening", reply)
        self.assertEqual(self.launched, [(docx,)])

    def test_onedrive_path(self):
        self.assertTrue(resolve_path("onedrive").endswith("OneDrive"))
        self.assertTrue(resolve_path("OneDrive").endswith("OneDrive"))


if __name__ == "__main__":
    unittest.main()
