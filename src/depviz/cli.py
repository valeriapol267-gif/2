"""Точка входа командной строки (этап 1: вывод параметров)."""

import sys
from typing import Optional, Sequence

from depviz.config import Config, parse_config
from depviz.errors import ConfigError

EXIT_OK = 0
EXIT_CONFIG_ERROR = 2


def print_config(config: Config) -> None:
    """Вывести все настраиваемые параметры в формате ключ-значение."""
    for key, value in config.as_pairs():
        print(f"{key}: {value}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Запустить приложение и вернуть код завершения."""
    try:
        config = parse_config(argv)
    except ConfigError as error:
        print(f"Ошибка параметров: {error}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    print_config(config)
    return EXIT_OK
