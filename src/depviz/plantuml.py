"""Текстовое представление графа на языке PlantUML и его кодирование."""

import zlib
from typing import Dict, List, Set, Tuple

from depviz.graph import DependencyGraph
from depviz.render import BACKWARD, FORWARD

ROOT_COLOR = "#LightBlue"
TRUNCATED_COLOR = "#LightGray"
SKIPPED_COLOR = "#Pink"
CYCLE_ARROW = "-[#red]->"
PLAIN_ARROW = "-->"
ENCODING_ALPHABET = (
    "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
)
CHUNK_SIZE = 3
SIX_BITS = 0x3F
FOUR_BITS = 0x0F
TWO_BITS = 0x03
Edge = Tuple[str, str]


def node_label(node: str) -> str:
    """Подготовить подпись узла: версия Maven-пакета на второй строке."""
    name, _, version = node.rpartition(":")
    if ":" in name:
        return f"{name}\\n{version}"
    return node


def node_color(graph: DependencyGraph, node: str) -> str:
    """Выбрать цвет узла: корень, не раскрытый или недоступный."""
    if node in graph.skipped:
        return SKIPPED_COLOR
    if node not in graph.expanded:
        return TRUNCATED_COLOR
    return ROOT_COLOR if node == graph.root else ""


def cycle_edges(graph: DependencyGraph) -> Set[Edge]:
    """Вернуть рёбра графа, входящие в найденные циклы."""
    edges: Set[Edge] = set()
    for cycle in graph.cycles:
        for index, node in enumerate(cycle):
            edges.add((node, cycle[(index + 1) % len(cycle)]))
    return edges


def declare_nodes(
    graph: DependencyGraph, aliases: Dict[str, str]
) -> List[str]:
    """Сформировать объявления узлов диаграммы."""
    lines = []
    for node, alias in aliases.items():
        color = node_color(graph, node)
        suffix = f" {color}" if color else ""
        lines.append(f'rectangle "{node_label(node)}" as {alias}{suffix}')
    return lines


def declare_edges(
    graph: DependencyGraph, aliases: Dict[str, str], reverse: bool
) -> List[str]:
    """Сформировать стрелки: от зависимого пакета к его зависимости."""
    in_cycle = cycle_edges(graph)
    lines = []
    for node, children in graph.edges.items():
        for child in children:
            source, target = (child, node) if reverse else (node, child)
            arrow = CYCLE_ARROW if (node, child) in in_cycle else PLAIN_ARROW
            lines.append(f"{aliases[source]} {arrow} {aliases[target]}")
    return lines


def build_plantuml(
    graph: DependencyGraph, max_depth: int, reverse: bool = False
) -> str:
    """Построить описание графа на языке PlantUML.

    Стрелка ведёт от пакета к его зависимости (в обратном режиме - от
    зависимого пакета к исследуемому). Корень выделен синим, не
    раскрытые из-за глубины узлы - серым, недоступные - розовым,
    рёбра циклов - красным.
    """
    style = BACKWARD if reverse else FORWARD
    aliases = {node: f"n{index}" for index, node in enumerate(graph.edges)}
    lines = [
        "@startuml",
        f"title {style.title} {graph.root} (макс. глубина {max_depth})",
        "skinparam shadowing false",
        "left to right direction",
    ]
    lines.extend(declare_nodes(graph, aliases))
    lines.extend(declare_edges(graph, aliases, reverse))
    lines.append("@enduml")
    return "\n".join(lines) + "\n"


def encode_three_bytes(first: int, second: int, third: int) -> str:
    """Закодировать три байта четырьмя символами алфавита PlantUML."""
    indexes = (
        first >> 2,
        ((first & TWO_BITS) << 4) | (second >> 4),
        ((second & FOUR_BITS) << 2) | (third >> 6),
        third & SIX_BITS,
    )
    return "".join(ENCODING_ALPHABET[index] for index in indexes)


def encode_plantuml(text: str) -> str:
    """Закодировать текст для адреса сервера PlantUML (deflate + base64)."""
    compressor = zlib.compressobj(level=zlib.Z_BEST_COMPRESSION,
                                  wbits=-zlib.MAX_WBITS)
    packed = compressor.compress(text.encode("utf-8")) + compressor.flush()
    padded = packed + bytes(-len(packed) % CHUNK_SIZE)
    return "".join(
        encode_three_bytes(*padded[start:start + CHUNK_SIZE])
        for start in range(0, len(padded), CHUNK_SIZE)
    )
