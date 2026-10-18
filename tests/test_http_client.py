"""Тесты загрузки по HTTP и полного сценария на локальном сервере."""

import functools
import http.server
import io
import os
import socket
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from depviz import http_client
from depviz.cli import EXIT_ERROR, EXIT_OK, main
from depviz.errors import FetchError

POM = """<project>
  <groupId>org.demo</groupId><artifactId>app</artifactId>
  <version>1.0</version>
  <dependencies>
    <dependency>
      <groupId>org.demo</groupId><artifactId>lib</artifactId>
      <version>2.1</version>
    </dependency>
  </dependencies>
</project>"""


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Обработчик статических файлов без журнала в консоль."""

    def log_message(self, message_format, *args):
        """Не выводить журнал запросов."""


class LocalRepoTests(unittest.TestCase):
    """Проверки на локальном HTTP-сервере с раскладкой Maven."""

    def start_repo(self):
        """Запустить сервер с pom-файлом; вернуть базовый URL."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        folder = os.path.join(tmp.name, "org", "demo", "app", "1.0")
        os.makedirs(folder)
        with open(os.path.join(folder, "app-1.0.pom"), "w",
                  encoding="utf-8") as handle:
            handle.write(POM)
        handler = functools.partial(QuietHandler, directory=tmp.name)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def run_main(self, args):
        """Запустить main, вернув код, stdout и stderr."""
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(args)
        return code, out.getvalue(), err.getvalue()

    def test_fetch_bytes(self):
        """Существующий файл скачивается."""
        base = self.start_repo()
        data = http_client.fetch_bytes(f"{base}/org/demo/app/1.0/app-1.0.pom")
        self.assertIn(b"<artifactId>app</artifactId>", data)

    def test_not_found(self):
        """Ответ 404 превращается в понятную FetchError."""
        base = self.start_repo()
        with self.assertRaises(FetchError) as context:
            http_client.fetch_bytes(f"{base}/org/demo/app/9.9/app-9.9.pom")
        self.assertIn("404", str(context.exception))

    def test_connection_refused(self):
        """Недоступный сервер превращается в FetchError."""
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        with self.assertRaises(FetchError):
            http_client.fetch_bytes(f"http://127.0.0.1:{port}/x.pom")

    def test_too_large(self):
        """Слишком большой ответ отклоняется."""
        base = self.start_repo()
        url = f"{base}/org/demo/app/1.0/app-1.0.pom"
        with mock.patch.object(http_client, "MAX_RESPONSE_BYTES", 10):
            with self.assertRaises(FetchError):
                http_client.fetch_bytes(url)

    def test_end_to_end(self):
        """Полный запуск приложения против локального репозитория."""
        base = self.start_repo()
        args = ["--package", "org.demo:app", "--version", "1.0",
                "--repo", base]
        code, out, _ = self.run_main(args)
        self.assertEqual(code, EXIT_OK)
        self.assertIn("org.demo:lib:2.1 (compile)", out)

    def test_end_to_end_wrong_version(self):
        """Несуществующая версия даёт сообщение об ошибке и код 1."""
        base = self.start_repo()
        args = ["--package", "org.demo:app", "--version", "7.7",
                "--repo", base]
        code, _, err = self.run_main(args)
        self.assertEqual(code, EXIT_ERROR)
        self.assertIn("404", err)


if __name__ == "__main__":
    unittest.main()
