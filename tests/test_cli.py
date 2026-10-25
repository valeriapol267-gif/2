"""Тесты командной строки: вывод графа и коды завершения."""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from depviz.cli import EXIT_CONFIG_ERROR, EXIT_ERROR, EXIT_OK, main
from depviz.errors import FetchError
from depviz.maven import parse_coordinate, pom_url
from tests.helpers import REPO, make_fetch, make_pom

ARGS = ["--package", "a.b:app", "--version", "1.0", "--repo", REPO]


def run_main(args):
    """Запустить main, вернув код, stdout и stderr."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


def poms():
    """Вернуть pom-файлы пакета a.b:app:1.0 и его зависимости."""
    files = {
        "a.b:app:1.0": ["x.y:lib:2.0"],
        "x.y:lib:2.0": ["a.b:app:1.0"],
    }
    result = {}
    for coordinate, deps in files.items():
        group, artifact, version = coordinate.split(":")
        url = pom_url(REPO, parse_coordinate(f"{group}:{artifact}", version))
        result[url] = make_pom(coordinate, deps)
    return result


class MavenModeTests(unittest.TestCase):
    """Проверки работы с Maven-репозиторием."""

    def test_prints_graph_and_cycle(self):
        """Граф и найденный цикл выводятся на экран."""
        fetch = make_fetch(poms())
        with mock.patch("depviz.cli.fetch_bytes", fetch):
            code, out, _ = run_main(ARGS)
        self.assertEqual(code, EXIT_OK)
        self.assertIn("a.b:app:1.0 -> x.y:lib:2.0", out)
        self.assertIn("x.y:lib:2.0 -> a.b:app:1.0", out)
        self.assertIn("a.b:app:1.0 -> x.y:lib:2.0 -> a.b:app:1.0", out)

    def test_fetch_error(self):
        """Ошибка загрузки корня - stderr и код EXIT_ERROR."""
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


class TestRepositoryModeTests(unittest.TestCase):
    """Проверки режима тестового репозитория."""

    def write_repo(self, text):
        """Записать тестовый репозиторий во временный файл."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "repo.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_graph_from_file(self):
        """Граф строится по файлу, транзитивные зависимости видны."""
        path = self.write_repo("A: B C\nB: D\nC: D\nD:\n")
        code, out, _ = run_main(["--test-mode", "--package", "A",
                                 "--repo", path])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("  A -> B, C", out)
        self.assertIn("  D -> (нет зависимостей)", out)
        self.assertIn("Циклических зависимостей нет.", out)

    def test_max_depth(self):
        """Параметр --max-depth ограничивает обход."""
        path = self.write_repo("A: B\nB: C\nC:\n")
        args = ["--test-mode", "--package", "A", "--repo", path]
        _, out, _ = run_main(args + ["--max-depth", "1"])
        self.assertIn("не раскрыт", out)
        self.assertNotIn("  C ->", out)

    def test_cycle(self):
        """Цикл выводится и не приводит к зависанию."""
        path = self.write_repo("A: B\nB: A\n")
        _, out, _ = run_main(["--test-mode", "--package", "A",
                              "--repo", path])
        self.assertIn("A -> B -> A", out)

    def test_unknown_root(self):
        """Корневой пакет, которого нет в файле, - ошибка."""
        path = self.write_repo("A: B\n")
        code, _, err = run_main(["--test-mode", "--package", "Z",
                                 "--repo", path])
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("не описан", err)

    def test_bad_file_format(self):
        """Ошибка формата файла сообщает номер строки."""
        path = self.write_repo("A: B\nbad line\n")
        code, _, err = run_main(["--test-mode", "--package", "A",
                                 "--repo", path])
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("строка 2", err)


if __name__ == "__main__":
    unittest.main()
