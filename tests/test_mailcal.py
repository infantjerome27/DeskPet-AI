import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import read_calendar_file, read_email_file


EML = """From: Amma <amma@example.com>
To: me@example.com
Subject: Lunch on Sunday
Date: Sun, 25 Oct 2026 10:00:00 +0530
Content-Type: text/plain; charset="utf-8"

Come home for lunch on Sunday!
"""

ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:20261029T090000Z
SUMMARY:Team meeting
LOCATION:Office
END:VEVENT
BEGIN:VEVENT
DTSTART:20261028T080000Z
SUMMARY:Morning walk
END:VEVENT
END:VCALENDAR
"""


class MailCalTests(unittest.TestCase):
    def test_read_eml(self):
        with tempfile.NamedTemporaryFile("w", suffix=".eml",
                                         delete=False) as f:
            f.write(EML)
            path = f.name
        try:
            mail = read_email_file(path)
            self.assertEqual(mail["subject"], "Lunch on Sunday")
            self.assertIn("amma@example.com", mail["from"])
            self.assertIn("Come home for lunch", mail["body"])
        finally:
            os.unlink(path)

    def test_read_ics_sorted(self):
        with tempfile.NamedTemporaryFile("w", suffix=".ics",
                                         delete=False) as f:
            f.write(ICS)
            path = f.name
        try:
            events = read_calendar_file(path)
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["summary"], "Morning walk")
            self.assertEqual(events[1]["location"], "Office")
        finally:
            os.unlink(path)

    def test_missing_file_is_honest(self):
        from tools import ToolError
        with self.assertRaises(ToolError):
            read_email_file("/tmp/does-not-exist-xyz.eml")


if __name__ == "__main__":
    unittest.main()
