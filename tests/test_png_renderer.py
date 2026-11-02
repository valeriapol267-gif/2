"""Тесты получения PNG: сервер PlantUML, локальный jar, запись файлов."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from depviz import png_renderer
from depviz.errors import FetchError
from depviz.plantuml import encode_plantuml
from depviz.png_renderer import PNG_SIGNATURE, render_png, write_file

SERVER = "https://plantuml.test/plantuml"
TEXT = "@startuml\nA --> B\n@enduml\n"
IMAGE = PNG_SIGNATURE + b"data"


class ServerTests(unittest.TestCase):
    """Проверки отрисовки через сервер."""

    def test_url_contains_encoded_text(self):
        """Запрос идёт на адрес с закодированным текстом диаграммы."""
        with mock.patch.object(
            png_renderer, "fetch_bytes", return_value=IMAGE
        ) as fetch:
            result = render_png(TEXT, None, SERVER)
        self.assertEqual(result, IMAGE)
        fetch.assert_called_once_with(f"{SERVER}/png/{encode_plantuml(TEXT)}")

    def test_non_png_response(self):
        """Ответ, не похожий на PNG, - ошибка."""
        with mock.patch.object(
            png_renderer, "fetch_bytes", return_value=b"<html>"
        ):
            with self.assertRaises(FetchError):
                render_png(TEXT, None, SERVER)

    def test_network_error_has_hint(self):
        """К сетевой ошибке добавляется подсказка про --plantuml-jar."""
        failure = FetchError("нет сети")
        with mock.patch.object(
            png_renderer, "fetch_bytes", side_effect=failure
        ):
            with self.assertRaises(FetchError) as context:
                render_png(TEXT, None, SERVER)
        self.assertIn("--plantuml-jar", str(context.exception))


class JarTests(unittest.TestCase):
    """Проверки локальной отрисовки через plantuml.jar."""

    def run_with(self, **kwargs):
        """Вызвать render_png с подменённым subprocess.run."""
        with mock.patch.object(subprocess, "run", **kwargs) as run:
            result = render_png(TEXT, "plantuml.jar", SERVER)
        return result, run

    def test_success(self):
        """Текст передаётся в stdin, PNG читается из stdout."""
        done = SimpleNamespace(returncode=0, stdout=IMAGE, stderr=b"")
        result, run = self.run_with(return_value=done)
        self.assertEqual(result, IMAGE)
        command = run.call_args.args[0]
        self.assertIn("plantuml.jar", command)
        self.assertIn("-pipe", command)
        self.assertEqual(run.call_args.kwargs["input"], TEXT.encode("utf-8"))

    def test_nonzero_exit(self):
        """Ненулевой код возврата - ошибка с сообщением PlantUML."""
        done = SimpleNamespace(returncode=1, stdout=b"", stderr=b"boom")
        with self.assertRaises(FetchError) as context:
            self.run_with(return_value=done)
        self.assertIn("boom", str(context.exception))

    def test_java_missing(self):
        """Отсутствие Java - понятная ошибка."""
        with self.assertRaises(FetchError) as context:
            self.run_with(side_effect=FileNotFoundError())
        self.assertIn("Java", str(context.exception))

    def test_timeout(self):
        """Превышение времени ожидания - ошибка."""
        timeout = subprocess.TimeoutExpired(cmd="java", timeout=1)
        with self.assertRaises(FetchError):
            self.run_with(side_effect=timeout)

    def test_jar_has_priority_over_server(self):
        """Если задан jar, сервер не используется."""
        done = SimpleNamespace(returncode=0, stdout=IMAGE, stderr=b"")
        with mock.patch.object(subprocess, "run", return_value=done):
            with mock.patch.object(png_renderer, "fetch_bytes") as fetch:
                render_png(TEXT, "plantuml.jar", SERVER)
        fetch.assert_not_called()


class WriteFileTests(unittest.TestCase):
    """Проверки записи файлов."""

    def test_write(self):
        """Файл записывается."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.png"
            write_file(path, IMAGE)
            self.assertEqual(path.read_bytes(), IMAGE)

    def test_write_failure(self):
        """Невозможность записи - FetchError."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(os.path.join(tmp, "missing", "out.png"))
            with self.assertRaises(FetchError):
                write_file(path, IMAGE)


if __name__ == "__main__":
    unittest.main()
