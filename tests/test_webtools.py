import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools
from tools import ToolError, download_file, research_topic, scrape_text


class WebToolsTests(unittest.TestCase):
    def test_download_organises_by_category(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = download_file("https://example.com/report.pdf", tmp,
                                 opener=lambda url: b"%PDF-fake")
            self.assertTrue(dest.endswith(os.path.join("Documents", "report.pdf")))
            self.assertTrue(os.path.isfile(dest))

    def test_download_rejects_bad_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ToolError):
                download_file("https://example.com/x.bin", tmp,
                              opener=lambda url: (_ for _ in ()).throw(
                                  RuntimeError("boom")))

    def test_scrape_strips_markup(self):
        html = ("<html><head><style>.x{}</style></head><body>"
                "<h1>Hello</h1><script>var x=1;</script><p>World</p></body></html>")
        text = scrape_text("https://example.com", fetcher=lambda url: html)
        self.assertIn("Hello", text)
        self.assertIn("World", text)
        self.assertNotIn("var x", text)

    def test_research_parses_results(self):
        html = ("""<a class='result-link' href='https://a.example'>First Title</a>
                   <a class="result-link" href='https://b.example'>Second</a>""")
        results = research_topic("cats", fetcher=lambda topic: html)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["title"], "First Title")
        self.assertEqual(results[0]["url"], "https://a.example")

    def test_research_no_results_is_honest(self):
        with self.assertRaises(ToolError):
            research_topic("zzz", fetcher=lambda topic: "<html></html>")


if __name__ == "__main__":
    unittest.main()
