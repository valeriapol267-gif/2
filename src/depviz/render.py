"""Текстовое представление графа зависимостей."""

from dataclasses import dataclass
from typing import List

from depviz.graph import Cycle, DependencyGraph

TRUNCATED_NOTE = "(не раскрыт: достигнута максимальная глубина)"
UNAVAILABLE_NOTE = "(данные недоступны)"


@dataclass(frozen=True)
class Style:
    """Оформление отчёта: заголовок, стрелка и пометка пустого списка."""

    title: str
    arrow: str
    empty_note: str


FORWARD = Style("Граф зависимостей", " -> ", "(нет зависимостей)")
BACKWARD = Style("Обратные зависимости", " <- ", "(нет зависимых пакетов)")


def format_cycle(cycle: Cycle, arrow: str = FORWARD.arrow) -> str:
    """Представить цикл строкой вида A -> B -> A."""
    return arrow.join(cycle + (cycle[0],))


def describe_node(
    graph: DependencyGraph, node: str, style: Style = FORWARD
) -> str:
    """Описать связи узла одной строкой."""
    if node in graph.skipped:
        return UNAVAILABLE_NOTE
    if node not in graph.expanded:
        return TRUNCATED_NOTE
    return ", ".join(graph.edges[node]) or style.empty_note


def format_graph(
    graph: DependencyGraph, max_depth: int, reverse: bool = False
) -> List[str]:
    """Сформировать строки отчёта о графе (прямом или обратном)."""
    style = BACKWARD if reverse else FORWARD
    lines = [f"{style.title} {graph.root} (макс. глубина {max_depth}):"]
    for node in graph.edges:
        lines.append(
            f"  {node}{style.arrow}{describe_node(graph, node, style)}"
        )
    lines.append(
        f"Узлов: {len(graph.edges)}, рёбер: {graph.edge_count()}"
    )
    if not graph.cycles:
        lines.append("Циклических зависимостей нет.")
        return lines
    lines.append(f"Циклические зависимости ({len(graph.cycles)}):")
    lines.extend(
        f"  {format_cycle(cycle, style.arrow)}" for cycle in graph.cycles
    )
    return lines


def format_warnings(graph: DependencyGraph) -> List[str]:
    """Сформировать предупреждения о пакетах без данных."""
    return [
        f"Предупреждение: не удалось получить зависимости {node}: {reason}"
        for node, reason in graph.skipped.items()
    ]
