"""Тесты вывода зависимостей и кодов завершения."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from depviz.cli import EXIT_CONFIG_ERROR, EXIT_ERROR, EXIT_OK, main
from depviz.errors import FetchError

POM = b"""<project>
  <groupId>a.b</groupId><artifactId>app</artifactId><version>1.0</version>
  <dependencies>
    <dependency>
      <groupId>x.y</groupId><artifactId>lib</artifactId>
      <version>2.0</version><scope>runtime</scope>
    </dependency>
  </dependencies>
</project>"""
ARGS = ["--package", "a.b:app", "--version", "1.0"]


def run_main(args):
    """Запустить main, вернув код, stdout и stderr."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


class MainTests(unittest.TestCase):
    """Проверки функции main."""

    def test_prints_direct_dependencies(self):
        """Прямые зависимости выводятся списком."""
        with mock.patch("depviz.cli.fetch_bytes", return_value=POM):
            code, out, _ = run_main(ARGS)
        self.assertEqual(code, EXIT_OK)
        self.assertIn("Прямые зависимости a.b:app:1.0", out)
        self.assertIn("x.y:lib:2.0 (runtime)", out)

    def test_no_dependencies(self):
        """Для пакета без зависимостей выводится сообщение."""
        pom = (
            b"<project><groupId>a</groupId><artifactId>b</artifactId>"
            b"<version>1</version></project>"
        )
        with mock.patch("depviz.cli.fetch_bytes", return_value=pom):
            code, out, _ = run_main(ARGS)
        self.assertEqual(code, EXIT_OK)
        self.assertIn("нет прямых зависимостей", out)

    def test_fetch_error(self):
        """Ошибка загрузки - stderr и код EXIT_ERROR."""
        error = FetchError("файл не найден")
        with mock.patch("depviz.cli.fetch_bytes", side_effect=error):
            code, out, err = run_main(ARGS)
        self.assertEqual(code, EXIT_ERROR)
        self.assertEqual(out, "")
        self.assertIn("файл не найден", err)

    def test_config_error(self):
        """Ошибка параметров - stderr и код EXIT_CONFIG_ERROR."""
        code, out, err = run_main(["--package", "bad"])
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertEqual(out, "")
        self.assertIn("Ошибка параметров", err)


if __name__ == "__main__":
    unittest.main()
