"""Точка входа командной строки (этап 3: граф зависимостей)."""

import sys
from typing import Optional, Sequence, Tuple

from depviz.config import Config, parse_config
from depviz.errors import ConfigError, DepvizError
from depviz.file_repo import load_graph_file
from depviz.graph import DependencySource, build_graph
from depviz.http_client import fetch_bytes
from depviz.maven import parse_coordinate
from depviz.maven_repo import MavenRepository
from depviz.render import format_graph, format_warnings

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CONFIG_ERROR = 2


def create_source(config: Config) -> Tuple[DependencySource, str]:
    """Создать источник данных и имя корневого узла по параметрам."""
    if config.test_mode:
        repository = load_graph_file(config.repo)
        repository.require(config.package)
        return repository, config.package
    if config.version is None:
        raise ConfigError("не задана версия пакета (--version).")
    root = str(parse_coordinate(config.package, config.version))
    return MavenRepository(config.repo, fetch_bytes, root), root


def run(config: Config) -> None:
    """Построить граф зависимостей и вывести его на экран."""
    source, root = create_source(config)
    graph = build_graph(source, root, config.max_depth)
    for line in format_graph(graph, config.max_depth):
        print(line)
    for line in format_warnings(graph):
        print(line, file=sys.stderr)


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
