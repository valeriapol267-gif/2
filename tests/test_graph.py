"""Тесты обхода в глубину: глубина, циклы, отсутствие рекурсии."""

import unittest

from depviz.errors import FetchError
from depviz.graph import build_graph


class DictSource:
    """Источник зависимостей на основе словаря."""

    def __init__(self, packages, broken=()):
        """Запомнить граф и пакеты, при загрузке которых будет ошибка."""
        self.packages = packages
        self.broken = set(broken)

    def dependencies(self, node):
        """Вернуть зависимости пакета или выбросить FetchError."""
        if node in self.broken:
            raise FetchError(f"нет данных о {node}")
        return list(self.packages.get(node, []))


def graph_of(packages, root="A", depth=10, broken=()):
    """Построить граф для словаря пакетов."""
    return build_graph(DictSource(packages, broken), root, depth)


class DepthTests(unittest.TestCase):
    """Проверки ограничения глубины."""

    def test_chain(self):
        """Цепочка раскрывается полностью."""
        graph = graph_of({"A": ["B"], "B": ["C"], "C": []})
        self.assertEqual(list(graph.edges), ["A", "B", "C"])
        self.assertEqual(graph.edge_count(), 2)
        self.assertEqual(graph.cycles, [])

    def test_diamond(self):
        """Общая зависимость попадает в граф один раз."""
        graph = graph_of({"A": ["B", "C"], "B": ["D"], "C": ["D"]})
        self.assertEqual(list(graph.edges), ["A", "B", "D", "C"])
        self.assertEqual(graph.edges["C"], ["D"])

    def test_depth_one_is_direct_only(self):
        """Глубина 1 даёт только прямые зависимости корня."""
        graph = graph_of({"A": ["B"], "B": ["C"]}, depth=1)
        self.assertEqual(list(graph.edges), ["A", "B"])
        self.assertNotIn("B", graph.expanded)

    def test_depth_limit_cuts_chain(self):
        """Узлы глубже предела не раскрываются."""
        packages = {"A": ["B"], "B": ["C"], "C": ["D"], "D": []}
        graph = graph_of(packages, depth=2)
        self.assertEqual(list(graph.edges), ["A", "B", "C"])
        self.assertIn("B", graph.expanded)
        self.assertNotIn("C", graph.expanded)

    def test_reexpand_on_shallower_path(self):
        """Узел, впервые найденный на пределе глубины, раскрывается позже."""
        packages = {
            "A": ["B", "D"], "B": ["C"], "C": ["D"], "D": ["E"], "E": [],
        }
        graph = graph_of(packages, depth=3)
        self.assertEqual(graph.edges["D"], ["E"])
        self.assertEqual(graph.expanded["D"], 1)

    def test_unknown_package_is_leaf(self):
        """Пакет, которого нет в источнике, считается листом."""
        graph = graph_of({"A": ["X"]})
        self.assertEqual(graph.edges["X"], [])
        self.assertIn("X", graph.expanded)


class CycleTests(unittest.TestCase):
    """Проверки обработки циклических зависимостей."""

    def test_simple_cycle(self):
        """Цикл найден и не приводит к бесконечному обходу."""
        graph = graph_of({"A": ["B"], "B": ["A"]})
        self.assertEqual(graph.cycles, [("A", "B")])
        self.assertEqual(graph.edges["B"], ["A"])

    def test_self_loop(self):
        """Зависимость пакета от самого себя - цикл из одного узла."""
        graph = graph_of({"A": ["A"]})
        self.assertEqual(graph.cycles, [("A",)])

    def test_cycle_not_through_root(self):
        """Цикл ниже корня тоже находится, корень в него не входит."""
        graph = graph_of({"A": ["B"], "B": ["C"], "C": ["B"]})
        self.assertEqual(graph.cycles, [("B", "C")])

    def test_cycle_reported_once(self):
        """Один и тот же цикл не дублируется при разных путях к нему."""
        packages = {"A": ["B", "C"], "B": ["C"], "C": ["B"]}
        graph = graph_of(packages)
        self.assertEqual(graph.cycles, [("B", "C")])

    def test_two_cycles(self):
        """Несколько независимых циклов находятся все."""
        packages = {"A": ["B", "C"], "B": ["A"], "C": ["C"]}
        graph = graph_of(packages)
        self.assertEqual(sorted(graph.cycles), [("A", "B"), ("C",)])

    def test_cycle_with_depth_limit(self):
        """Цикл за пределом глубины не обнаруживается."""
        packages = {"A": ["B"], "B": ["C"], "C": ["A"]}
        graph = graph_of(packages, depth=2)
        self.assertEqual(graph.cycles, [])


class RobustnessTests(unittest.TestCase):
    """Проверки устойчивости обхода."""

    def test_deep_chain_without_recursion(self):
        """Очень длинная цепочка не вызывает RecursionError."""
        size = 5000
        packages = {
            f"N{index}": [f"N{index + 1}"] for index in range(size)
        }
        graph = graph_of(packages, root="N0", depth=size + 1)
        self.assertEqual(len(graph.edges), size + 1)

    def test_broken_child_is_skipped(self):
        """Сбой при загрузке не корня фиксируется и не прерывает обход."""
        graph = graph_of({"A": ["B", "C"]}, broken=["B"])
        self.assertIn("B", graph.skipped)
        self.assertIn("C", graph.expanded)

    def test_broken_root_raises(self):
        """Сбой при загрузке корня - ошибка."""
        with self.assertRaises(FetchError):
            graph_of({"A": ["B"]}, broken=["A"])

    def test_duplicate_dependencies(self):
        """Повторы в списке зависимостей не создают лишних рёбер."""
        graph = graph_of({"A": ["B", "B"]})
        self.assertEqual(graph.edges["A"], ["B"])


if __name__ == "__main__":
    unittest.main()
