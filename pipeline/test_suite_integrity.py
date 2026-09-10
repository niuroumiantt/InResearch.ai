#!/usr/bin/env python3
"""Tests that never run are worse than tests that fail: they read as green.

Appending a method to a file whose `if __name__ == "__main__"` guard sits in
the middle silently parents it to that guard instead of to a class, and
discovery skips it without a word.  Three tests were lost that way.
"""
import ast
from pathlib import Path
import unittest

PIPELINE = Path(__file__).resolve().parent


def guard_blocks(tree):
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        if (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
                and test.left.id == '__name__'):
            yield node


class SuiteIntegrityTests(unittest.TestCase):
    def modules(self):
        return sorted(PIPELINE.glob('test_*.py'))

    def test_there_are_test_modules_to_check(self):
        self.assertGreater(len(self.modules()), 5)

    def test_no_test_is_stranded_inside_a_main_guard(self):
        stranded = []
        for path in self.modules():
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for block in guard_blocks(tree):
                for node in ast.walk(block):
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and \
                            node.name.startswith(('test', 'Test')):
                        stranded.append('%s:%d %s' % (path.name, node.lineno, node.name))
        self.assertEqual(stranded, [], 'these never run: ' + ', '.join(stranded))

    def test_the_main_guard_is_the_last_thing_in_the_file(self):
        """Anything after it is where the next append will land."""
        trailing = []
        for path in self.modules():
            tree = ast.parse(path.read_text(encoding='utf-8'))
            guards = [n for n in tree.body if n in list(guard_blocks(tree))]
            if not guards:
                continue
            last_guard = max(tree.body.index(g) for g in guards)
            after = tree.body[last_guard + 1:]
            if after:
                trailing.append('%s: %d node(s) after the guard' % (path.name, len(after)))
        self.assertEqual(trailing, [], '; '.join(trailing))


if __name__ == '__main__':
    unittest.main()
