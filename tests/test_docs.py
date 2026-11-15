import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docs import (append_to_document, build_document, read_document_blocks,
                  read_document_text, text_to_blocks)


class DocsTests(unittest.TestCase):
    def test_build_and_read_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "Report.docx")
            build_document([
                ("title", "My Report"),
                ("heading", "Intro"),
                ("paragraph", "Hello world"),
                ("bullet", "First point"),
                ("table", [["Name", "Age"], ["Asha", "20"]]),
            ], path)
            self.assertTrue(zipfile.is_zipfile(path))
            blocks = read_document_blocks(path)
            texts = [t for _, t in blocks]
            self.assertIn("My Report", texts)
            self.assertIn("Intro", texts)
            self.assertIn("Hello world", texts)
            self.assertTrue(any("First point" in t for t in texts))
            self.assertIn("Asha", texts)
            self.assertEqual(read_document_text(path).splitlines()[0], "My Report")

    def test_append_keeps_existing_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "Doc.docx")
            build_document([("heading", "Part 1"), ("paragraph", "Original")], path)
            append_to_document(path, [("paragraph", "Added later")])
            text = read_document_text(path)
            self.assertIn("Original", text)
            self.assertIn("Added later", text)

    def test_markdown_to_blocks(self):
        blocks = text_to_blocks("# Title\nSome text\n- one\n- two")
        kinds = [k for k, _ in blocks]
        self.assertEqual(kinds, ["heading", "paragraph", "bullet", "bullet"])

    @unittest.skipUnless(shutil.which("soffice"), "LibreOffice not available")
    def test_generated_docx_opens_in_libreoffice(self):
        """Strongest proof the file is a real Word document: convert it."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "Real.docx")
            build_document([("title", "LibreOffice Check"),
                            ("heading", "Section One"),
                            ("paragraph", "This must survive conversion.")], path)
            subprocess.run(["soffice", "--headless", "--convert-to", "pdf",
                            "--outdir", tmp, path],
                           check=True, capture_output=True, timeout=120)
            pdf = os.path.join(tmp, "Real.pdf")
            self.assertTrue(os.path.exists(pdf))
            try:
                import fitz
                text = "".join(p.get_text() for p in fitz.open(pdf))
            except ImportError:
                self.skipTest("pymupdf not available")
            self.assertIn("LibreOffice Check", text)
            self.assertIn("This must survive conversion.", text)


if __name__ == "__main__":
    unittest.main()
