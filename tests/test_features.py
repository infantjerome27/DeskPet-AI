import csv
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools
from brain import Brain
from docs import read_document_text
from tools import ReminderService


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # Isolate settings/notes into the temp dir.
        patcher = mock.patch.object(tools, "get_data_dir",
                                    return_value=self.tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.brain = Brain(launcher=lambda x: None,
                           opener=lambda x: None,
                           reminders=ReminderService())

    def test_create_document_and_read_it_back(self):
        path = os.path.join(self.tmp.name, "Report.docx")
        reply, mood = self.brain.handle(
            f'create document {path} title "My Report" heading "Intro" '
            'paragraph "Hello world" bullet "First point"')
        self.assertEqual(mood, "celebrating")
        self.assertTrue(os.path.exists(path))
        text = read_document_text(path)
        self.assertIn("My Report", text)
        self.assertIn("Hello world", text)
        reply, _ = self.brain.handle(f"read document {path}")
        self.assertIn("Hello world", reply)

    def test_append_to_document(self):
        path = os.path.join(self.tmp.name, "Doc.docx")
        self.brain.handle(f'create document {path} paragraph "Original"')
        reply, _ = self.brain.handle(
            f'add to document {path} paragraph "Added later"')
        self.assertIn("Added", reply)
        self.assertIn("Added later", read_document_text(path))

    def test_convert_txt_to_docx(self):
        src = os.path.join(self.tmp.name, "notes.txt")
        with open(src, "w") as f:
            f.write("# My Notes\n- buy milk\n- call home\n")
        reply, mood = self.brain.handle(f"convert {src} to docx")
        self.assertEqual(mood, "celebrating")
        dest = os.path.join(self.tmp.name, "notes.docx")
        self.assertTrue(os.path.exists(dest))
        self.assertIn("buy milk", read_document_text(dest))

    def test_create_spreadsheet(self):
        path = os.path.join(self.tmp.name, "Data.csv")
        reply, mood = self.brain.handle(
            f'create spreadsheet {path} headers "Name,Age" rows "Asha,20" "Ravi,21"')
        self.assertEqual(mood, "celebrating")
        with open(path, newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0], ["Name", "Age"])
        self.assertEqual(rows[2], ["Ravi", "21"])

    def test_file_powers(self):
        a = os.path.join(self.tmp.name, "a.txt")
        with open(a, "w") as f:
            f.write("hello world")
        reply, _ = self.brain.handle(f"copy {a} to {self.tmp.name}/b.txt")
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, "b.txt")))
        reply, _ = self.brain.handle(f"file info {a}")
        self.assertIn("file", reply)
        reply, _ = self.brain.handle(f"summarize file {a}")
        self.assertIn("2 words", reply)
        reply, _ = self.brain.handle(f"create folder {self.tmp.name}/Photos")
        self.assertTrue(os.path.isdir(os.path.join(self.tmp.name, "Photos")))
        reply, _ = self.brain.handle(f"rename {a} to renamed.txt")
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, "renamed.txt")))

    def test_settings(self):
        reply, _ = self.brain.handle("set pet color to blue")
        self.assertEqual(self.brain.settings_changed.get("pet_color"), "#A8D8FF")
        reply, _ = self.brain.handle("set pet color to chartreuse")
        self.assertIn("colours", reply)
        reply, _ = self.brain.handle("set pet name to Max")
        self.assertEqual(self.brain.settings_changed.get("pet_name"), "Max")
        reply, _ = self.brain.handle("show settings")
        self.assertIn("Max", reply)
        reply, _ = self.brain.handle("reset settings")
        self.assertEqual(self.brain.settings_changed.get("pet_name"), "Buddy")


if __name__ == "__main__":
    unittest.main()
