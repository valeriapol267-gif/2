"""Тесты чтения файла тестового репозитория."""

import os
import tempfile
import unittest

from depviz.errors import FetchError
from depviz.file_repo import load_graph_file, parse_graph_text


class ParseTextTests(unittest.TestCase):
    """Проверки разбора текста файла."""

    def test_basic_format(self):
        """Поддерживаются пробелы, запятые, пустые зависимости."""
        packages = parse_graph_text("A: B C\nB:C, D\nC:\nD\n")
        self.assertEqual(packages, {
            "A": ["B", "C"], "B": ["C", "D"], "C": [], "D": [],
        })

    def test_comments_and_blank_lines(self):
        """Комментарии и пустые строки игнорируются."""
        sign = "\N{NUMBER SIGN}"
        text = f"{sign} заголовок\n\n  A : B  \n   {sign} ещё\n"
        packages = parse_graph_text(text)
        self.assertEqual(packages, {"A": ["B"]})

    def test_duplicate_dependencies_removed(self):
        """Повторы зависимостей в строке удаляются."""
        self.assertEqual(parse_graph_text("A: B B C B"), {"A": ["B", "C"]})

    def test_multiletter_names(self):
        """Имена из нескольких больших букв допустимы."""
        self.assertEqual(parse_graph_text("AB: CD"), {"AB": ["CD"]})

    def test_bad_lines(self):
        """Некорректные строки приводят к FetchError с номером строки."""
        bad_texts = ["a: B", "A: b", "A B", "A: B1", "1: A", "A:: B", ": B"]
        for text in bad_texts:
            with self.subTest(text=text):
                with self.assertRaises(FetchError) as context:
                    parse_graph_text(text)
                self.assertIn("строка 1", str(context.exception))

    def test_duplicate_package(self):
        """Повторное описание пакета - ошибка."""
        with self.assertRaises(FetchError) as context:
            parse_graph_text("A: B\nA: C\n")
        self.assertIn("строка 2", str(context.exception))

    def test_empty_text(self):
        """Пустой файл даёт пустой репозиторий."""
        self.assertEqual(parse_graph_text(""), {})


class LoadFileTests(unittest.TestCase):
    """Проверки чтения файла с диска."""

    def write(self, data):
        """Записать данные во временный файл; вернуть его путь."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "repo.txt")
        with open(path, "wb") as handle:
            handle.write(data)
        return path

    def test_load_with_bom(self):
        """Файл с BOM читается корректно."""
        repo = load_graph_file(self.write(b"\xef\xbb\xbfA: B\n"))
        self.assertEqual(repo.dependencies("A"), ["B"])
        self.assertEqual(repo.dependencies("B"), [])

    def test_invalid_encoding(self):
        """Файл не в UTF-8 даёт FetchError."""
        with self.assertRaises(FetchError):
            load_graph_file(self.write(b"\xff\xfe\x00A"))

    def test_missing_file(self):
        """Несуществующий файл даёт FetchError."""
        with self.assertRaises(FetchError):
            load_graph_file(os.path.join(tempfile.gettempdir(), "no_x.txt"))

    def test_require(self):
        """Корневой пакет обязан быть описан в файле."""
        repo = load_graph_file(self.write(b"A: B\n"))
        repo.require("A")
        with self.assertRaises(FetchError):
            repo.require("B")


if __name__ == "__main__":
    unittest.main()
