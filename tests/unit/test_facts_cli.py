import contextlib
import io
import unittest
from unittest.mock import patch
from inresearch.knowledge import facts

class FactsCLITests(unittest.TestCase):
    def test_help_and_unknown_flags_never_load_or_dump_the_library(self):
        for arg, code in [('--help', 0), ('--not-an-option', 2)]:
            with patch('sys.argv', ['facts', arg]), patch.object(facts, 'load') as load:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as raised: facts.main()
                self.assertEqual(raised.exception.code, code)
                load.assert_not_called()

    def test_summary_keeps_failure_exit_without_comparison_output(self):
        with patch('sys.argv', ['facts', '--summary']), patch.object(facts, 'load', return_value=([{}], {})), patch.object(facts, 'compare') as compare:
            output=io.StringIO()
            with contextlib.redirect_stdout(output): self.assertEqual(facts.main(), 1)
            compare.assert_not_called()
            self.assertIn('校验失败', output.getvalue())
