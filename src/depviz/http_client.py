"""Загрузка файлов из репозитория по HTTP."""

import urllib.error
import urllib.request
from http import HTTPStatus

from depviz.errors import FetchError

REQUEST_TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
USER_AGENT = "depviz/0.2"


def describe_http_error(error: urllib.error.HTTPError, url: str) -> str:
    """Сформировать понятное сообщение об HTTP-ошибке."""
    if error.code == HTTPStatus.NOT_FOUND:
        return (
            f"файл не найден (HTTP {error.code}): {url}. "
            "Проверьте имя пакета, версию и адрес репозитория."
        )
    return f"сервер вернул HTTP {error.code} ({error.reason}): {url}."


def fetch_bytes(url: str) -> bytes:
    """Скачать содержимое URL; при сбое выбросить FetchError."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(
            request, timeout=REQUEST_TIMEOUT_SECONDS
        ) as response:
            data = response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        raise FetchError(describe_http_error(error, url)) from error
    except urllib.error.URLError as error:
        raise FetchError(
            f"не удалось подключиться к {url}: {error.reason}."
        ) from error
    except OSError as error:
        raise FetchError(
            f"сетевая ошибка при загрузке {url}: {error}."
        ) from error
    if len(data) > MAX_RESPONSE_BYTES:
        raise FetchError(f"файл слишком большой: {url}.")
    return data
