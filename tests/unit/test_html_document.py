from pathlib import Path
import tempfile
import unittest

from inresearch.adapters.html_document import extract


class HtmlDocumentTests(unittest.TestCase):
    def test_extracts_product_content_tables_and_links_without_executing_markup(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'page.html'
            path.write_text('''<html><head><title>Compute platform</title><script>IGNORE_SECRET()</script></head>
              <body><nav>Navigation only</nav><main><h1>Product overview</h1>
              <p>Supports 8 GPUs.</p><table><tr><th>Power</th><td>10 kW</td></tr></table>
              <a href="/support/manual.pdf">Manual</a></main><footer>Cookie settings</footer></body></html>''')
            text, meta = extract(path)
        self.assertEqual(meta['title'], 'Compute platform')
        self.assertIn('Product overview', text)
        self.assertIn('8 GPUs', text)
        self.assertIn('Power', text)
        self.assertIn('10 kW', text)
        self.assertIn('/support/manual.pdf', text)
        self.assertNotIn('IGNORE_SECRET', text)
        self.assertNotIn('Navigation only', text)
        self.assertNotIn('Cookie settings', text)
        self.assertFalse(meta['truncated'])

    def test_explicitly_marks_text_truncation(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'page.html'
            path.write_text('<main><p>abcdefghij</p></main>')
            text, meta = extract(path, limit=5)
        self.assertEqual(text, 'abcde')
        self.assertTrue(meta['truncated'])


if __name__ == '__main__':
    unittest.main()
