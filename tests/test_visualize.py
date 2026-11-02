"""Тесты параметров визуализации и сохранения результатов."""

import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from depviz.cli import EXIT_ERROR, EXIT_OK, main
from depviz.config import DEFAULT_PLANTUML_SERVER, parse_config
from depviz.errors import ConfigError, FetchError
from depviz.png_renderer import PNG_SIGNATURE

IMAGE = PNG_SIGNATURE + b"data"
BASE = ["--package", "a.b:c", "--version", "1.0"]


class VisualizeConfigTests(unittest.TestCase):
    """Проверки новых параметров."""

    def test_defaults(self):
        """По умолчанию изображение не создаётся, сервер - plantuml.com."""
        config = parse_config(BASE)
        self.assertIsNone(config.output)
        self.assertIsNone(config.plantuml_jar)
        self.assertEqual(config.plantuml_server, DEFAULT_PLANTUML_SERVER)

    def test_server_url(self):
        """Адрес сервера проверяется и очищается от завершающего «/»."""
        config = parse_config(BASE + ["--plantuml-server", "https://h.io/p/"])
        self.assertEqual(config.plantuml_server, "https://h.io/p")
        with self.assertRaises(ConfigError):
            parse_config(BASE + ["--plantuml-server", "ftp://h.io"])

    def test_jar_must_exist(self):
        """Путь к jar должен указывать на существующий .jar-файл."""
        with tempfile.TemporaryDirectory() as tmp:
            jar = os.path.join(tmp, "plantuml.jar")
            Path(jar).write_bytes(b"x")
            self.assertEqual(
                parse_config(BASE + ["--plantuml-jar", jar]).plantuml_jar, jar
            )
            txt = os.path.join(tmp, "plantuml.txt")
            Path(txt).write_bytes(b"x")
            for bad in [txt, os.path.join(tmp, "none.jar")]:
                with self.subTest(path=bad):
                    with self.assertRaises(ConfigError):
                        parse_config(BASE + ["--plantuml-jar", bad])


class VisualizeCommandTests(unittest.TestCase):
    """Проверки сценария создания изображения."""

    def setup_files(self):
        """Создать каталог с тестовым репозиторием; вернуть пути."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name) / "repo.txt"
        repo.write_text("A: B C\nB: C\nC:\n", encoding="utf-8")
        return repo, Path(tmp.name) / "graph.png"

    def run_main(self, args, **kwargs):
        """Запустить main с подменой render_png."""
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("depviz.cli.render_png", **kwargs) as render:
            with redirect_stdout(out), redirect_stderr(err):
                code = main(args)
        return code, out.getvalue(), err.getvalue(), render

    def test_files_are_saved(self):
        """Сохраняются PNG и .puml, текст PlantUML выводится на экран."""
        repo, png = self.setup_files()
        args = ["--test-mode", "--package", "A", "--repo", str(repo),
                "--output", str(png)]
        code, out, _, render = self.run_main(args, return_value=IMAGE)
        self.assertEqual(code, EXIT_OK)
        self.assertEqual(png.read_bytes(), IMAGE)
        puml = png.with_suffix(".puml").read_text(encoding="utf-8")
        self.assertTrue(puml.startswith("@startuml"))
        self.assertIn(puml, out)
        self.assertIn("Изображение сохранено", out)
        self.assertEqual(render.call_args.args[0], puml)

    def test_reverse_title_in_file(self):
        """В обратном режиме в диаграмме указан соответствующий заголовок."""
        repo, png = self.setup_files()
        args = ["--test-mode", "--reverse", "--package", "C",
                "--repo", str(repo), "--output", str(png)]
        self.run_main(args, return_value=IMAGE)
        puml = png.with_suffix(".puml").read_text(encoding="utf-8")
        self.assertIn("title Обратные зависимости C", puml)

    def test_no_output_no_image(self):
        """Без --output изображение не создаётся и сеть не используется."""
        repo, _ = self.setup_files()
        args = ["--test-mode", "--package", "A", "--repo", str(repo)]
        code, out, _, render = self.run_main(args)
        self.assertEqual(code, EXIT_OK)
        self.assertNotIn("@startuml", out)
        render.assert_not_called()

    def test_render_failure_keeps_puml(self):
        """Сбой отрисовки: код 1, но .puml уже сохранён."""
        repo, png = self.setup_files()
        args = ["--test-mode", "--package", "A", "--repo", str(repo),
                "--output", str(png)]
        code, _, err, _ = self.run_main(
            args, side_effect=FetchError("нет сети")
        )
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("нет сети", err)
        self.assertTrue(png.with_suffix(".puml").exists())
        self.assertFalse(png.exists())


if __name__ == "__main__":
    unittest.main()
