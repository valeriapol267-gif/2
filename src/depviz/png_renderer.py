"""Получение PNG-изображения из текста PlantUML и запись файлов."""

import subprocess
from pathlib import Path
from typing import Optional

from depviz.errors import FetchError
from depviz.http_client import fetch_bytes
from depviz.plantuml import encode_plantuml

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JAR_TIMEOUT_SECONDS = 120
JAVA_COMMAND = "java"
SERVER_HINT = (
    "Для больших графов или без доступа к серверу используйте "
    "локальную отрисовку (--plantuml-jar)."
)


def render_with_server(text: str, server: str) -> bytes:
    """Получить PNG от сервера PlantUML по закодированному тексту."""
    url = f"{server}/png/{encode_plantuml(text)}"
    try:
        return fetch_bytes(url)
    except FetchError as error:
        raise FetchError(f"{error} {SERVER_HINT}") from error


def render_with_jar(text: str, jar: str) -> bytes:
    """Получить PNG, запустив plantuml.jar через Java."""
    command = [JAVA_COMMAND, "-jar", jar, "-tpng", "-pipe",
               "-charset", "UTF-8"]
    try:
        result = subprocess.run(
            command, input=text.encode("utf-8"), capture_output=True,
            timeout=JAR_TIMEOUT_SECONDS, check=False,
        )
    except FileNotFoundError:
        raise FetchError(
            f"не найдена команда {JAVA_COMMAND}: установите Java."
        ) from None
    except subprocess.TimeoutExpired:
        raise FetchError("PlantUML не завершил работу вовремя.") from None
    if result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise FetchError(f"PlantUML завершился с ошибкой: {message}")
    return result.stdout


def render_png(text: str, jar: Optional[str], server: str) -> bytes:
    """Получить PNG локально (если задан jar) или с сервера PlantUML."""
    if jar:
        image = render_with_jar(text, jar)
    else:
        image = render_with_server(text, server)
    if not image.startswith(PNG_SIGNATURE):
        raise FetchError("PlantUML вернул данные, не похожие на PNG.")
    return image


def write_file(path: Path, data: bytes) -> None:
    """Записать данные в файл; ошибку записи сообщить как FetchError."""
    try:
        path.write_bytes(data)
    except OSError as error:
        raise FetchError(
            f"не удалось записать {str(path)!r}: {error}."
        ) from error
