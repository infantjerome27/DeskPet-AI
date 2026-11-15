import csv
import http.server
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from functools import partial
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools
from brain import Brain
from docs import read_document_text
from office import (build_presentation, build_spreadsheet, read_pdf_text,
                    read_spreadsheet_rows)
from tools import ReminderService


def make_brain(tmp):
    patcher = mock.patch.object(tools, "get_data_dir", return_value=tmp)
    patcher.start()
    brain = Brain(launcher=lambda x: None, opener=lambda x: None,
                  reminders=ReminderService())
    return brain, patcher


class OfficeTests(unittest.TestCase):
    def test_xlsx_round_trip_with_formula(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "Data.xlsx")
            build_spreadsheet(["Name", "Score"],
                              [["Asha", 90], ["Ravi", "=SUM(B2:B3)"]], path)
            rows = read_spreadsheet_rows(path)
            self.assertEqual(rows[0], ["Name", "Score"])
            self.assertEqual(rows[1], ["Asha", "90"])
            self.assertEqual(rows[2][1], "=SUM(B2:B3)")

    @unittest.skipUnless(shutil.which("soffice"), "LibreOffice not available")
    def test_pptx_converts_in_libreoffice(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "Deck.pptx")
            build_presentation([("Quarterly Report", []),
                                ("Sales", ["Up 20%", "New regions"])], path)
            subprocess.run(["soffice", "--headless", "--convert-to", "pdf",
                            "--outdir", tmp, path],
                           check=True, capture_output=True, timeout=120)
            pdf = os.path.join(tmp, "Deck.pdf")
            self.assertTrue(os.path.exists(pdf))
            self.assertIn("Quarterly Report", read_pdf_text(pdf))
            self.assertIn("New regions", read_pdf_text(pdf))

    @unittest.skipUnless(shutil.which("soffice"), "LibreOffice not available")
    def test_pdf_text_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            txt = os.path.join(tmp, "note.txt")
            with open(txt, "w") as f:
                f.write("Hello PDF world, this is a test document.")
            subprocess.run(["soffice", "--headless", "--convert-to", "pdf",
                            "--outdir", tmp, txt],
                           check=True, capture_output=True, timeout=120)
            pdf = os.path.join(tmp, "note.pdf")
            self.assertIn("Hello PDF world", read_pdf_text(pdf))


class PowerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.brain, self.patcher = make_brain(self.tmp.name)
        self.addCleanup(self.patcher.stop)

    def test_bulk_rename_with_confirmation(self):
        folder = os.path.join(self.tmp.name, "Photos")
        os.makedirs(folder)
        for name in ("IMG_1.jpg", "IMG_2.jpg", "other.txt"):
            open(os.path.join(folder, name), "w").close()
        reply, _ = self.brain.handle(f'bulk rename in {folder} "IMG_" to "Trip_"')
        self.assertIn("2 files", reply)
        self.assertTrue(os.path.exists(os.path.join(folder, "IMG_1.jpg")))
        reply, _ = self.brain.handle("yes")
        self.assertIn("Renamed 2 files", reply)
        self.assertTrue(os.path.exists(os.path.join(folder, "Trip_1.jpg")))
        self.assertTrue(os.path.exists(os.path.join(folder, "other.txt")))

    def test_cleanup_reports(self):
        big = os.path.join(self.tmp.name, "big.bin")
        with open(big, "wb") as f:
            f.write(b"x" * 5000)
        dup1 = os.path.join(self.tmp.name, "d1.txt")
        dup2 = os.path.join(self.tmp.name, "d2.txt")
        for p in (dup1, dup2):
            with open(p, "w") as f:
                f.write("same content")
        open(os.path.join(self.tmp.name, "junk.tmp"), "w").close()
        reply, _ = self.brain.handle(f"large files in {self.tmp.name}")
        self.assertIn("big.bin", reply)
        reply, _ = self.brain.handle(f"duplicate files in {self.tmp.name}")
        self.assertIn("d1.txt", reply)
        reply, _ = self.brain.handle(f"temp files in {self.tmp.name}")
        self.assertIn("junk.tmp", reply)

    def test_clean_and_pivot_csv(self):
        path = os.path.join(self.tmp.name, "data.csv")
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Dept", "Salary"])
            writer.writerow([" Sales ", "100"])
            writer.writerow(["Sales", "100"])
            writer.writerow(["Eng", "200"])
            writer.writerow([])
        reply, _ = self.brain.handle(f"clean csv {path}")
        self.assertIn("5 rows in, 3 rows out", reply)
        reply, _ = self.brain.handle(f"pivot {path} by Dept sum Salary")
        self.assertIn("Sales", reply)
        self.assertIn("Eng", reply)

    def test_create_excel_and_presentation_via_brain(self):
        xlsx = os.path.join(self.tmp.name, "Data.xlsx")
        reply, mood = self.brain.handle(
            f'create excel {xlsx} headers "Name,Score" rows "Asha,90" "Ravi,80"')
        self.assertEqual(mood, "celebrating")
        self.assertEqual(read_spreadsheet_rows(xlsx)[1], ["Asha", "90"])
        pptx = os.path.join(self.tmp.name, "Deck.pptx")
        reply, mood = self.brain.handle(
            f'create presentation {pptx} title "Report" slides '
            '"Intro" "Point one" ; "Next" "More"')
        self.assertEqual(mood, "celebrating")
        self.assertTrue(os.path.exists(pptx))

    def test_search_inside_office_files(self):
        docx = os.path.join(self.tmp.name, "Report.docx")
        self.brain.handle(f'create document {docx} paragraph "zebra crossing"')
        hits = tools.search_files("zebra", self.tmp.name)
        self.assertIn(docx, hits)
        hits = tools.search_files("definitely-not-here", self.tmp.name)
        self.assertEqual(hits, [])

    def test_run_and_check_python(self):
        script = os.path.join(self.tmp.name, "hello.py")
        with open(script, "w") as f:
            f.write("print('hello from script')\n")
        reply, _ = self.brain.handle(f"run python {script}")
        self.assertIn("hello from script", reply)
        reply, _ = self.brain.handle(f"check python {script}")
        self.assertIn("no syntax errors", reply)
        bad = os.path.join(self.tmp.name, "bad.py")
        with open(bad, "w") as f:
            f.write("def broken(:\n")
        reply, _ = self.brain.handle(f"check python {bad}")
        self.assertIn("Syntax problem", reply)

    def test_sqlite_select_only(self):
        db = os.path.join(self.tmp.name, "shop.db")
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE products (name TEXT, price REAL)")
        conn.execute("INSERT INTO products VALUES ('Pen', 10)")
        conn.commit()
        conn.close()
        reply, _ = self.brain.handle(
            f'query database {db} SELECT name FROM products')
        self.assertIn("Pen", reply)
        reply, _ = self.brain.handle(
            f'query database {db} DELETE FROM products')
        self.assertIn("only run SELECT", reply)

    def test_http_get_local_server(self):
        handler = partial(http.server.SimpleHTTPRequestHandler,
                          directory=self.tmp.name)
        server = http.server.HTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with open(os.path.join(self.tmp.name, "page.txt"), "w") as f:
                f.write("local server hello")
            port = server.server_address[1]
            reply, _ = self.brain.handle(f"http get http://127.0.0.1:{port}/page.txt")
            self.assertIn("local server hello", reply)
        finally:
            server.shutdown()

    def test_workflow_chaining(self):
        a = os.path.join(self.tmp.name, "a.txt")
        b = os.path.join(self.tmp.name, "b.txt")
        reply, _ = self.brain.handle(
            f"create file {a} with hello workflow then copy {a} to {b} then read {b}")
        self.assertIn("Created", reply)
        self.assertIn("Copied", reply)
        self.assertIn("hello workflow", reply)

    def test_facts_and_redact_and_clipboard(self):
        reply, _ = self.brain.handle("remember that my favourite colour is blue")
        self.assertIn("Remembered", reply)
        reply, _ = self.brain.handle("what do you remember")
        self.assertIn("favourite colour is blue", reply)
        src = os.path.join(self.tmp.name, "notes.txt")
        with open(src, "w") as f:
            f.write("my password is hunter2 and my secret code is 42")
        reply, _ = self.brain.handle(
            f'redact file {src} words "password,secret"')
        self.assertIn("Redacted", reply)
        with open(src) as f:
            self.assertIn("hunter2", f.read())  # original untouched
        reply, _ = self.brain.handle("copy hello clipboard test to clipboard")
        self.assertIn("Copied", reply)
        reply, _ = self.brain.handle("show clipboard")
        self.assertIn("hello clipboard test", reply)

    def test_screenshot_with_fake_grabber(self):
        path = os.path.join(self.tmp.name, "shot.png")

        def fake_grabber(dest):
            with open(dest, "wb") as f:
                f.write(b"fake-png")

        out = tools.take_screenshot(path, grabber=fake_grabber)
        self.assertEqual(out, path)
        self.assertTrue(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
