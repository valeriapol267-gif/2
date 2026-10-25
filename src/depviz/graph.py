"""Построение графа зависимостей обходом в глубину без рекурсии."""

from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Protocol, Set, Tuple

from depviz.errors import FetchError

Cycle = Tuple[str, ...]


class DependencySource(Protocol):
    """Источник данных: возвращает прямые зависимости пакета."""

    def dependencies(self, node: str) -> List[str]:
        """Вернуть имена прямых зависимостей пакета ``node``."""
        raise NotImplementedError


@dataclass
class DependencyGraph:
    """Граф зависимостей, построенный от корневого пакета.

    ``edges`` содержит все найденные пакеты в порядке обхода и их
    зависимости; ``expanded`` - пакеты, зависимости которых загружены
    (значение - наименьшая глубина раскрытия); ``skipped`` - пакеты,
    данные о которых получить не удалось, с причиной.
    """

    root: str
    edges: Dict[str, List[str]] = field(default_factory=dict)
    expanded: Dict[str, int] = field(default_factory=dict)
    cycles: List[Cycle] = field(default_factory=list)
    skipped: Dict[str, str] = field(default_factory=dict)

    def edge_count(self) -> int:
        """Вернуть число рёбер графа."""
        return sum(len(children) for children in self.edges.values())


@dataclass
class Frame:
    """Элемент явного стека обхода: пакет и его необработанные дети."""

    node: str
    depth: int
    children: Iterator[str]


def normalize_cycle(cycle: Cycle) -> Cycle:
    """Повернуть цикл так, чтобы он начинался с наименьшего пакета."""
    pivot = cycle.index(min(cycle))
    return cycle[pivot:] + cycle[:pivot]


class DepthFirstBuilder:
    """Итеративный обход в глубину с ограничением глубины.

    Пакет раскрывается повторно, если он снова достигнут на меньшей
    глубине: так зависимости не теряются, когда он впервые встретился
    на предельной глубине. Циклы находятся по множеству пакетов
    текущего пути и не приводят к бесконечному обходу.
    """

    def __init__(
        self, source: DependencySource, root: str, max_depth: int
    ) -> None:
        """Подготовить построитель для корня ``root``."""
        self.source = source
        self.max_depth = max_depth
        self.graph = DependencyGraph(root=root)
        self.stack: List[Frame] = []
        self.on_path: Set[str] = set()

    def build(self) -> DependencyGraph:
        """Выполнить обход и вернуть построенный граф."""
        self.expand(self.graph.root, 0)
        while self.stack:
            frame = self.stack[-1]
            child = next(frame.children, None)
            if child is None:
                self.stack.pop()
                self.on_path.discard(frame.node)
            else:
                self.visit(frame, child)
        return self.graph

    def load_children(self, node: str) -> List[str]:
        """Получить зависимости пакета; сбой не у корня не фатален."""
        try:
            return self.source.dependencies(node)
        except FetchError as error:
            if node == self.graph.root:
                raise
            self.graph.skipped[node] = str(error)
            return []

    def expand(self, node: str, depth: int) -> None:
        """Загрузить зависимости пакета и поместить его в стек."""
        children = self.load_children(node)
        self.graph.expanded[node] = depth
        self.graph.edges.setdefault(node, [])
        self.stack.append(Frame(node, depth, iter(children)))
        self.on_path.add(node)

    def visit(self, frame: Frame, child: str) -> None:
        """Обработать одно ребро ``frame.node -> child``."""
        edges = self.graph.edges[frame.node]
        if child not in edges:
            edges.append(child)
        self.graph.edges.setdefault(child, [])
        if child in self.on_path:
            self.record_cycle(child)
            return
        depth = frame.depth + 1
        known = self.graph.expanded.get(child)
        if depth >= self.max_depth or (known is not None and known <= depth):
            return
        self.expand(child, depth)

    def record_cycle(self, child: str) -> None:
        """Запомнить цикл, замкнувшийся на пакете ``child``."""
        path = [frame.node for frame in self.stack]
        cycle = normalize_cycle(tuple(path[path.index(child):]))
        if cycle not in self.graph.cycles:
            self.graph.cycles.append(cycle)


def build_graph(
    source: DependencySource, root: str, max_depth: int
) -> DependencyGraph:
    """Построить граф зависимостей пакета ``root`` до глубины max_depth."""
    return DepthFirstBuilder(source, root, max_depth).build()
