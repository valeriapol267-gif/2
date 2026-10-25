"""Тестовый репозиторий: граф зависимостей из текстового файла.

Формат: по одной строке на пакет, имена - большие латинские буквы.
``A: B C`` - пакет A зависит от B и C (разделители: пробелы и запятые);
``A:`` или ``A`` - у пакета A нет зависимостей. Пустые строки и строки,
начинающиеся с символа «решётка», игнорируются. Пакет, упомянутый только как
зависимость, считается пакетом без зависимостей.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from depviz.errors import FetchError

NAME_RE = re.compile(r"[A-Z]+")
LINE_RE = re.compile(r"([A-Z]+)\s*(?::(.*))?")
SEPARATOR_RE = re.compile(r"[\s,]+")
COMMENT_PREFIX = "\N{NUMBER SIGN}"
MAX_FILE_BYTES = 1024 * 1024
ENCODING = "utf-8-sig"


def parse_line(
    line: str, number: int
) -> Optional[Tuple[str, List[str]]]:
    """Разобрать строку файла; вернуть (пакет, зависимости) или None."""
    text = line.strip()
    if not text or text.startswith(COMMENT_PREFIX):
        return None
    match = LINE_RE.fullmatch(text)
    if match is None:
        raise FetchError(
            f"строка {number}: ожидается формат 'A: B C', получено {text!r}."
        )
    parts = SEPARATOR_RE.split((match.group(2) or "").strip())
    dependencies = list(dict.fromkeys(part for part in parts if part))
    for dependency in dependencies:
        if not NAME_RE.fullmatch(dependency):
            raise FetchError(
                f"строка {number}: имя зависимости должно состоять из "
                f"больших латинских букв: {dependency!r}."
            )
    return match.group(1), dependencies


def parse_graph_text(text: str) -> Dict[str, List[str]]:
    """Разобрать текст файла в словарь пакет -> список зависимостей."""
    packages: Dict[str, List[str]] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        parsed = parse_line(line, number)
        if parsed is None:
            continue
        name, dependencies = parsed
        if name in packages:
            raise FetchError(f"строка {number}: пакет {name} описан дважды.")
        packages[name] = dependencies
    return packages


class GraphFileRepository:
    """Источник зависимостей, читающий граф из тестового файла."""

    def __init__(self, packages: Dict[str, List[str]]) -> None:
        """Создать репозиторий из словаря пакет -> зависимости."""
        self.packages = packages

    def require(self, name: str) -> None:
        """Убедиться, что пакет описан в файле."""
        if name not in self.packages:
            raise FetchError(f"пакет {name} не описан в тестовом репозитории.")

    def dependencies(self, node: str) -> List[str]:
        """Вернуть прямые зависимости пакета (пустой список, если нет)."""
        return list(self.packages.get(node, []))


def load_graph_file(path: str) -> GraphFileRepository:
    """Прочитать тестовый репозиторий из файла."""
    try:
        if Path(path).stat().st_size > MAX_FILE_BYTES:
            raise FetchError(f"файл {path!r} слишком большой.")
        text = Path(path).read_bytes().decode(ENCODING)
    except (OSError, UnicodeDecodeError) as error:
        raise FetchError(f"не удалось прочитать {path!r}: {error}.") from error
    return GraphFileRepository(parse_graph_text(text))
