"""Текстовое представление графа зависимостей."""

from typing import List

from depviz.graph import Cycle, DependencyGraph

NO_DEPENDENCIES_NOTE = "(нет зависимостей)"
TRUNCATED_NOTE = "(не раскрыт: достигнута максимальная глубина)"
UNAVAILABLE_NOTE = "(данные недоступны)"


def format_cycle(cycle: Cycle) -> str:
    """Представить цикл строкой вида A -> B -> A."""
    return " -> ".join(cycle + (cycle[0],))


def describe_node(graph: DependencyGraph, node: str) -> str:
    """Описать зависимости узла одной строкой."""
    if node in graph.skipped:
        return UNAVAILABLE_NOTE
    if node not in graph.expanded:
        return TRUNCATED_NOTE
    return ", ".join(graph.edges[node]) or NO_DEPENDENCIES_NOTE


def format_graph(graph: DependencyGraph, max_depth: int) -> List[str]:
    """Сформировать строки отчёта о графе зависимостей."""
    lines = [f"Граф зависимостей {graph.root} (макс. глубина {max_depth}):"]
    for node in graph.edges:
        lines.append(f"  {node} -> {describe_node(graph, node)}")
    lines.append(
        f"Узлов: {len(graph.edges)}, рёбер: {graph.edge_count()}"
    )
    if not graph.cycles:
        lines.append("Циклических зависимостей нет.")
        return lines
    lines.append(f"Циклические зависимости ({len(graph.cycles)}):")
    lines.extend(f"  {format_cycle(cycle)}" for cycle in graph.cycles)
    return lines


def format_warnings(graph: DependencyGraph) -> List[str]:
    """Сформировать предупреждения о пакетах без данных."""
    return [
        f"Предупреждение: не удалось получить зависимости {node}: {reason}"
        for node, reason in graph.skipped.items()
    ]
