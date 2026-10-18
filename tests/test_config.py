"""Тесты разбора и проверки параметров командной строки."""

import os
import tempfile
import unittest

from depviz.config import DEFAULT_OUTPUT, DEFAULT_REPO_URL, parse_config
from depviz.errors import ConfigError

PACKAGE = "org.apache.commons:commons-lang3"
BASE_ARGS = ["--package", PACKAGE, "--version", "3.14.0"]


class RemoteModeTests(unittest.TestCase):
    """Проверки параметров при работе с реальным репозиторием."""

    def test_defaults(self):
        """Необязательные параметры получают значения по умолчанию."""
        config = parse_config(BASE_ARGS)
        self.assertEqual(config.package, PACKAGE)
        self.assertEqual(config.repo, DEFAULT_REPO_URL)
        self.assertEqual(config.output, DEFAULT_OUTPUT)
        self.assertFalse(config.test_mode)

    def test_all_options(self):
        """Все параметры принимаются и сохраняются."""
        config = parse_config(
            BASE_ARGS
            + ["--repo", "https://example.org/maven/", "--max-depth", "5"]
            + ["--output", "out.PNG"]
        )
        self.assertEqual(config.repo, "https://example.org/maven")
        self.assertEqual(config.max_depth, 5)
        self.assertEqual(config.output, "out.PNG")

    def test_missing_package(self):
        """Отсутствие имени пакета - ошибка."""
        with self.assertRaises(ConfigError):
            parse_config(["--version", "1.0"])

    def test_bad_package_names(self):
        """Имена без groupId или с лишними символами отклоняются."""
        for name in ["commons-lang3", "a:b:c", "a b:c", ":b", "a:", "A\n"]:
            with self.subTest(name=name):
                with self.assertRaises(ConfigError):
                    parse_config(["--package", name, "--version", "1.0"])

    def test_missing_version(self):
        """Вне тестового режима версия обязательна."""
        with self.assertRaises(ConfigError):
            parse_config(["--package", PACKAGE])

    def test_bad_versions(self):
        """Некорректные версии отклоняются."""
        for version in ["", " ", "1 0", "-1", "1.0/../x", "1.0\n"]:
            with self.subTest(version=version):
                with self.assertRaises(ConfigError):
                    parse_config(["--package", PACKAGE, "--version", version])

    def test_bad_urls(self):
        """Некорректные URL репозитория отклоняются."""
        urls = ["ftp://host/x", "repo", "http://", "https:///x", "http://a b"]
        for url in urls:
            with self.subTest(url=url):
                with self.assertRaises(ConfigError):
                    parse_config(BASE_ARGS + ["--repo", url])


class OtherOptionsTests(unittest.TestCase):
    """Проверки глубины, имени файла и неизвестных опций."""

    def test_bad_depth(self):
        """Глубина должна быть целым числом из допустимого диапазона."""
        for depth in ["abc", "1.5", "", "0", "-3", "1000"]:
            with self.subTest(depth=depth):
                with self.assertRaises(ConfigError):
                    parse_config(BASE_ARGS + ["--max-depth", depth])

    def test_bad_output(self):
        """Имя файла должно оканчиваться на .png и быть корректным."""
        missing_dir = os.path.join("no_such_dir_xyz", "graph.png")
        outputs = ["graph.svg", "graph", ".png", "", "a?b.png", missing_dir]
        for output in outputs:
            with self.subTest(output=output):
                with self.assertRaises(ConfigError):
                    parse_config(BASE_ARGS + ["--output", output])

    def test_output_is_directory(self):
        """Каталог с расширением .png не принимается как файл."""
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "dir.png")
            os.mkdir(folder)
            with self.assertRaises(ConfigError):
                parse_config(BASE_ARGS + ["--output", folder])

    def test_unknown_option(self):
        """Неизвестная опция и сокращённое имя опции - ошибка."""
        for option in ["--unknown", "--max"]:
            with self.subTest(option=option):
                with self.assertRaises(ConfigError):
                    parse_config(BASE_ARGS + [option, "1"])

    def test_option_without_value(self):
        """Опция без значения - ошибка."""
        with self.assertRaises(ConfigError):
            parse_config(BASE_ARGS + ["--max-depth"])


class TestModeTests(unittest.TestCase):
    """Проверки параметров в режиме тестового репозитория."""

    def make_repo_file(self):
        """Создать временный файл тестового репозитория; вернуть путь."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = os.path.join(tmp.name, "repo.txt")
        with open(repo, "w", encoding="utf-8") as handle:
            handle.write("A: B C\n")
        return repo

    def test_valid(self):
        """Версия в тестовом режиме необязательна."""
        repo = self.make_repo_file()
        config = parse_config(
            ["--test-mode", "--package", "AB", "--repo", repo]
        )
        self.assertTrue(config.test_mode)
        self.assertEqual(config.repo, repo)
        self.assertIsNone(config.version)

    def test_lowercase_package(self):
        """Имя пакета должно состоять из больших латинских букв."""
        repo = self.make_repo_file()
        for name in ["a", "A1", PACKAGE, "ПАКЕТ"]:
            with self.subTest(name=name):
                with self.assertRaises(ConfigError):
                    parse_config(
                        ["--test-mode", "--package", name, "--repo", repo]
                    )

    def test_repo_required(self):
        """В тестовом режиме нужно указать путь к файлу."""
        with self.assertRaises(ConfigError):
            parse_config(["--test-mode", "--package", "A"])

    def test_repo_missing_file(self):
        """Несуществующий файл или каталог вместо файла - ошибка."""
        folder = os.path.dirname(self.make_repo_file())
        for path in [os.path.join(folder, "none.txt"), folder]:
            with self.subTest(path=path):
                with self.assertRaises(ConfigError):
                    parse_config(
                        ["--test-mode", "--package", "A", "--repo", path]
                    )


if __name__ == "__main__":
    unittest.main()
