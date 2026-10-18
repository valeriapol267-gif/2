"""Тесты вывода параметров и кодов завершения."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

from depviz.cli import EXIT_CONFIG_ERROR, EXIT_OK, main


class MainTests(unittest.TestCase):
    """Проверки функции main."""

    def test_prints_key_value_pairs(self):
        """Все параметры выводятся в формате ключ-значение."""
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(["--package", "a.b:c", "--version", "1.0"])
        self.assertEqual(code, EXIT_OK)
        lines = out.getvalue().splitlines()
        self.assertIn("package: a.b:c", lines)
        self.assertIn("version: 1.0", lines)
        self.assertIn("max-depth: 3", lines)
        self.assertIn("test-mode: false", lines)

    def test_error_goes_to_stderr(self):
        """Ошибка выводится в stderr, код завершения ненулевой."""
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["--package", "bad"])
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("Ошибка параметров", err.getvalue())


if __name__ == "__main__":
    unittest.main()
