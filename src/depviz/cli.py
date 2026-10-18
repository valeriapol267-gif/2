"""Точка входа командной строки (этап 2: прямые зависимости)."""

import sys
from typing import List, Optional, Sequence

from depviz.config import Config, parse_config
from depviz.errors import ConfigError, DepvizError
from depviz.http_client import fetch_bytes
from depviz.maven import (
    DEFAULT_SCOPE,
    Coordinate,
    Dependency,
    get_direct_dependencies,
    parse_coordinate,
)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CONFIG_ERROR = 2
UNKNOWN_VERSION = "версия не определена"


def format_dependency(dep: Dependency) -> str:
    """Представить зависимость строкой groupId:artifactId:version (scope)."""
    flags = [dep.scope or DEFAULT_SCOPE]
    if dep.optional:
        flags.append("optional")
    version = dep.version or UNKNOWN_VERSION
    return f"{dep.group_id}:{dep.artifact_id}:{version} ({', '.join(flags)})"


def print_dependencies(
    coordinate: Coordinate, dependencies: List[Dependency]
) -> None:
    """Вывести прямые зависимости пакета на экран."""
    if not dependencies:
        print(f"У пакета {coordinate} нет прямых зависимостей.")
        return
    print(f"Прямые зависимости {coordinate} ({len(dependencies)}):")
    for dep in dependencies:
        print(f"  {format_dependency(dep)}")


def run(config: Config) -> None:
    """Получить и вывести прямые зависимости пакета."""
    if config.test_mode:
        raise DepvizError("тестовый режим будет реализован на этапе 3.")
    if config.version is None:
        raise ConfigError("не задана версия пакета (--version).")
    coordinate = parse_coordinate(config.package, config.version)
    dependencies = get_direct_dependencies(
        coordinate, config.repo, fetch_bytes
    )
    print_dependencies(coordinate, dependencies)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Запустить приложение и вернуть код завершения."""
    try:
        run(parse_config(argv))
    except ConfigError as error:
        print(f"Ошибка параметров: {error}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    except DepvizError as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_OK
