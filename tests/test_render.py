"""Тесты текстового представления графа."""

import unittest

from depviz.graph import build_graph
from depviz.render import format_graph, format_warnings
from tests.test_graph import DictSource


class RenderTests(unittest.TestCase):
    """Проверки форматирования графа."""

    def test_graph_with_cycle_and_limit(self):
        """В отчёте видны зависимости, пометки и циклы."""
        packages = {"A": ["B"], "B": ["A", "C"], "C": ["D"]}
        graph = build_graph(DictSource(packages), "A", 2)
        self.assertEqual(format_graph(graph, 2), [
            "Граф зависимостей A (макс. глубина 2):",
            "  A -> B",
            "  B -> A, C",
            "  C -> (не раскрыт: достигнута максимальная глубина)",
            "Узлов: 3, рёбер: 3",
            "Циклические зависимости (1):",
            "  A -> B -> A",
        ])

    def test_no_cycles_and_leaf(self):
        """Лист помечается, отсутствие циклов отмечается явно."""
        graph = build_graph(DictSource({"A": ["B"]}), "A", 3)
        lines = format_graph(graph, 3)
        self.assertIn("  B -> (нет зависимостей)", lines)
        self.assertEqual(lines[-1], "Циклических зависимостей нет.")

    def test_warnings(self):
        """Пакеты без данных попадают в предупреждения."""
        graph = build_graph(DictSource({"A": ["B"]}, broken=["B"]), "A", 3)
        self.assertIn("  B -> (данные недоступны)", format_graph(graph, 3))
        warnings = format_warnings(graph)
        self.assertEqual(len(warnings), 1)
        self.assertIn("B", warnings[0])


if __name__ == "__main__":
    unittest.main()
