"""Тесты режима обратных зависимостей."""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from depviz.cli import EXIT_CONFIG_ERROR, EXIT_ERROR, EXIT_OK, main
from depviz.config import parse_config
from depviz.errors import ConfigError, FetchError
from depviz.file_repo import GraphFileRepository, parse_graph_text
from depviz.graph import build_graph
from depviz.render import format_graph

DIAMOND = "A: B C\nB: D\nC: D\nD:\n"


def reverse_repo(text):
    """Построить репозиторий обратных зависимостей по тексту файла."""
    return GraphFileRepository(parse_graph_text(text)).reversed_repository()


class ReversedRepositoryTests(unittest.TestCase):
    """Проверки построения обратного репозитория."""

    def test_dependents(self):
        """Для каждого пакета перечислены пакеты, которые от него зависят."""
        repo = reverse_repo(DIAMOND)
        self.assertEqual(repo.dependencies("D"), ["B", "C"])
        self.assertEqual(repo.dependencies("B"), ["A"])
        self.assertEqual(repo.dependencies("A"), [])

    def test_package_only_mentioned_as_dependency(self):
        """Пакет, не описанный отдельной строкой, тоже известен."""
        repo = reverse_repo("A: X\n")
        repo.require("X")
        self.assertEqual(repo.dependencies("X"), ["A"])

    def test_unknown_package(self):
        """Неизвестный пакет отклоняется."""
        with self.assertRaises(FetchError):
            reverse_repo(DIAMOND).require("Z")

    def test_self_dependency(self):
        """Самозависимость остаётся самозависимостью."""
        self.assertEqual(reverse_repo("G: G\n").dependencies("G"), ["G"])


class ReverseGraphTests(unittest.TestCase):
    """Проверки обхода обратного графа тем же алгоритмом DFS."""

    def test_transitive_dependents(self):
        """Находятся и косвенные зависимые пакеты."""
        graph = build_graph(reverse_repo(DIAMOND), "D", 5)
        self.assertEqual(list(graph.edges), ["D", "B", "A", "C"])

    def test_depth_limit(self):
        """Глубина 1 даёт только прямые зависимые пакеты."""
        graph = build_graph(reverse_repo(DIAMOND), "D", 1)
        self.assertEqual(list(graph.edges), ["D", "B", "C"])

    def test_cycle(self):
        """Цикл в обратном графе находится."""
        graph = build_graph(reverse_repo("A: B\nB: C\nC: A\n"), "A", 5)
        self.assertEqual(len(graph.cycles), 1)
        self.assertEqual(set(graph.cycles[0]), {"A", "B", "C"})

    def test_report_uses_backward_arrows(self):
        """В отчёте используются стрелки «<-» и пометка о пустом списке."""
        graph = build_graph(reverse_repo(DIAMOND), "D", 5)
        lines = format_graph(graph, 5, reverse=True)
        self.assertEqual(lines[0], "Обратные зависимости D (макс. глубина 5):")
        self.assertIn("  D <- B, C", lines)
        self.assertIn("  A <- (нет зависимых пакетов)", lines)

    def test_report_cycle_arrows(self):
        """Цикл в отчёте записан стрелками «<-»."""
        graph = build_graph(reverse_repo("A: B\nB: A\n"), "A", 5)
        lines = format_graph(graph, 5, reverse=True)
        self.assertEqual(lines[-1], "  A <- B <- A")


class ReverseCommandLineTests(unittest.TestCase):
    """Проверки опции --reverse в командной строке."""

    def write_repo(self, text):
        """Записать тестовый репозиторий во временный файл."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "repo.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def run_main(self, args):
        """Запустить main, вернув код, stdout и stderr."""
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(args)
        return code, out.getvalue(), err.getvalue()

    def test_reverse_requires_test_mode(self):
        """Вне тестового режима --reverse - ошибка параметров."""
        with self.assertRaises(ConfigError):
            parse_config(["--package", "a:b", "--version", "1", "--reverse"])

    def test_reverse_flag_parsed(self):
        """В тестовом режиме флаг принимается."""
        path = self.write_repo(DIAMOND)
        config = parse_config(
            ["--test-mode", "--reverse", "--package", "D", "--repo", path]
        )
        self.assertTrue(config.reverse)

    def test_reverse_output(self):
        """Обратные зависимости выводятся на экран."""
        path = self.write_repo(DIAMOND)
        code, out, _ = self.run_main(
            ["--test-mode", "--reverse", "--package", "D", "--repo", path]
        )
        self.assertEqual(code, EXIT_OK)
        self.assertIn("Обратные зависимости D", out)
        self.assertIn("  D <- B, C", out)

    def test_forward_output_unchanged(self):
        """Без --reverse выводятся прямые зависимости."""
        path = self.write_repo(DIAMOND)
        code, out, _ = self.run_main(
            ["--test-mode", "--package", "A", "--repo", path]
        )
        self.assertEqual(code, EXIT_OK)
        self.assertIn("  A -> B, C", out)

    def test_unknown_package(self):
        """Неизвестный пакет в обратном режиме - ошибка получения данных."""
        path = self.write_repo(DIAMOND)
        code, _, err = self.run_main(
            ["--test-mode", "--reverse", "--package", "Q", "--repo", path]
        )
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("не описан", err)

    def test_reverse_without_test_mode_exit_code(self):
        """Код завершения при --reverse без --test-mode - 2."""
        code, _, err = self.run_main(
            ["--package", "a:b", "--version", "1", "--reverse"]
        )
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertIn("--reverse", err)


if __name__ == "__main__":
    unittest.main()
