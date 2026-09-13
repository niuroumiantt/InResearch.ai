import tempfile
import unittest
from pathlib import Path

from inresearch.delivery import report as report_model
from inresearch.knowledge import registry as research


class ReportModelTests(unittest.TestCase):
    def test_repository_chapters_and_content_identity(self):
        report = report_model.build_report()
        self.assertEqual(15, len(report['chapters']))
        self.assertEqual(150, report['finding_count'])
        self.assertEqual('legacy_unverified', report['acceptance'])
        self.assertEqual(report['data_revision'], report_model.build_report()['data_revision'])
        markdown = '\n'.join(report_model.markdown_report(report, report['title'], '2026-09-12'))
        for chapter in report['chapters']:
            for finding in chapter['findings']:
                self.assertIn(finding['id'], markdown)
        for source in report['sources']:
            self.assertIn(source, markdown)

    def test_superseded_body_never_enters_current_report_but_link_survives(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            research.atomic_json(root / 'framework/modules.json', {
                'version': 'test', 'modules': [{'id': 'M01', 'name': 'Test'}]})
            path = root / 'research/M01.md'
            path.parent.mkdir()
            path.write_text('## M01-F1 Old\n- **状态**：superseded ｜ **修订**：2026-09-01\n'
                            '- **结论**：RETIRED_BODY\nhttps://retired.example/source\n'
                            '## M01-F2 Current\n- **结论**：Current body\n'
                            '- **待办**：INTERNAL_TODO\n')
            report = report_model.build_report(root)
            self.assertEqual(['M01-F2'], [f['id'] for f in report['chapters'][0]['findings']])
            self.assertEqual('M01-F1', report['history'][0]['id'])
            self.assertNotIn('RETIRED_BODY', str(report))
            self.assertNotIn('INTERNAL_TODO', str(report))
            self.assertNotIn('https://retired.example/source', report['sources'])
            before = report['data_revision']
            path.write_text(path.read_text().replace('Current body', 'Updated body'))
            self.assertNotEqual(before, report_model.build_report(root)['data_revision'])


if __name__ == '__main__':
    unittest.main()
