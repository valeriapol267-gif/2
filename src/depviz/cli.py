"""Точка входа командной строки (этап 5: визуализация)."""

import sys
from pathlib import Path
from typing import Optional, Sequence, Tuple

from depviz.config import Config, parse_config
from depviz.errors import ConfigError, DepvizError
from depviz.file_repo import load_graph_file
from depviz.graph import DependencyGraph, DependencySource, build_graph
from depviz.http_client import fetch_bytes
from depviz.maven import parse_coordinate
from depviz.maven_repo import MavenRepository
from depviz.plantuml import build_plantuml
from depviz.png_renderer import render_png, write_file
from depviz.render import format_graph, format_warnings

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CONFIG_ERROR = 2
PUML_SUFFIX = ".puml"


def create_source(config: Config) -> Tuple[DependencySource, str]:
    """Создать источник данных и имя корневого узла по параметрам."""
    if config.test_mode:
        repository = load_graph_file(config.repo)
        if config.reverse:
            repository = repository.reversed_repository()
        repository.require(config.package)
        return repository, config.package
    if config.version is None:
        raise ConfigError("не задана версия пакета (--version).")
    root = str(parse_coordinate(config.package, config.version))
    return MavenRepository(config.repo, fetch_bytes, root), root


def visualize(graph: DependencyGraph, config: Config, output: str) -> None:
    """Сохранить описание PlantUML и PNG-изображение графа."""
    text = build_plantuml(graph, config.max_depth, config.reverse)
    puml_path = Path(output).with_suffix(PUML_SUFFIX)
    write_file(puml_path, text.encode("utf-8"))
    print("PlantUML:")
    print(text, end="")
    print(f"Описание PlantUML сохранено: {puml_path}")
    image = render_png(text, config.plantuml_jar, config.plantuml_server)
    write_file(Path(output), image)
    print(f"Изображение сохранено: {output}")


def run(config: Config) -> None:
    """Построить граф, вывести отчёт и при необходимости изображение."""
    source, root = create_source(config)
    graph = build_graph(source, root, config.max_depth)
    for line in format_graph(graph, config.max_depth, config.reverse):
        print(line)
    for line in format_warnings(graph):
        print(line, file=sys.stderr)
    if config.output is not None:
        visualize(graph, config, config.output)


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
