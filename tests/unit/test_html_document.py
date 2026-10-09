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

    def test_valueless_attributes_preserve_body_and_navigation_omission(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'page.html'
            path.write_text('''<html><head><title>Transformer report</title></head>
              <body class id><nav class id>Navigation only</nav>
              <div class="navigation" id>Hidden menu</div>
              <main class id><p class>Transformer lead time is 12 months.</p>
              <p id>Supply remains constrained.</p><a href>Source label</a>
              <a href="/report.pdf" class id>Full report</a></main></body></html>''')
            text, meta = extract(path)
        self.assertEqual(meta['title'], 'Transformer report')
        self.assertIn('Transformer lead time is 12 months.', text)
        self.assertIn('Supply remains constrained.', text)
        self.assertIn('Source label', text)
        self.assertIn('/report.pdf', text)
        self.assertNotIn('Navigation only', text)
        self.assertNotIn('Hidden menu', text)
        self.assertNotIn('[link: Source label', text)
        self.assertFalse(meta['truncated'])

    def test_form_container_preserves_article_and_omits_input_controls(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'page.html'
            path.write_text('''<title>PJM - Large Load</title><form id="frmMain" method="post">
              <input type="hidden" name="__VIEWSTATE" value="hidden state">
              <nav>Navigation only</nav><script>IGNORE_SECRET()</script>
              <main><h1>Large Load</h1><p>The rapid growth in demand for electricity
              in PJM is largely driven by Large-Load customers, including data centers.</p>
              <p>Interim Resource Adequacy Service provides a framework to connect
              new Large Load customers that bring their own new power supply.</p>
              <button>Submit search</button><textarea>User input</textarea>
              <select><option>Select a region</option></select>
              <p>Electricity grid approval and interconnection cost.</p></main></form>''')
            text, meta = extract(path)
        self.assertEqual(meta['title'], 'PJM - Large Load')
        self.assertIn('Large-Load customers, including data centers.', text)
        self.assertIn('bring their own new power supply.', text)
        self.assertIn('Electricity grid approval and interconnection cost.', text)
        for omitted in ('Navigation only', 'IGNORE_SECRET', 'hidden state',
                        'Submit search', 'User input', 'Select a region'):
            self.assertNotIn(omitted, text)
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
