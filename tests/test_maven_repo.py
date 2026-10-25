"""Тесты построения графа зависимостей по pom-файлам Maven."""

import unittest

from depviz.errors import FetchError
from depviz.graph import build_graph
from depviz.maven import parse_coordinate, pom_url
from depviz.maven_repo import MavenRepository, parse_node
from tests.helpers import REPO, make_fetch, make_pom

APP = "org.demo:app:1.0"


def pom_files(poms):
    """Построить словарь url -> pom по словарю 'g:a:v' -> зависимости."""
    files = {}
    for coordinate, deps in poms.items():
        group, artifact, version = coordinate.split(":")
        url = pom_url(REPO, parse_coordinate(f"{group}:{artifact}", version))
        files[url] = make_pom(coordinate, deps)
    return files


def graph_for(poms, depth=5, root=APP):
    """Построить граф для набора pom-файлов."""
    source = MavenRepository(REPO, make_fetch(pom_files(poms)), root)
    return build_graph(source, root, depth)


class MavenGraphTests(unittest.TestCase):
    """Проверки графа, построенного из pom-файлов."""

    def test_transitive_dependencies(self):
        """Транзитивные зависимости попадают в граф."""
        graph = graph_for({
            APP: ["org.demo:lib:2.0"],
            "org.demo:lib:2.0": ["org.demo:core:3.0"],
            "org.demo:core:3.0": [],
        })
        self.assertEqual(
            list(graph.edges), [APP, "org.demo:lib:2.0", "org.demo:core:3.0"]
        )

    def test_scopes_and_optional(self):
        """У корня видны все зависимости, у остальных - только транзитивные."""
        graph = graph_for({
            APP: ["org.demo:lib:2.0", "junit:junit:4.13:test"],
            "org.demo:lib:2.0": [
                "org.demo:core:3.0", "x:testonly:1:test",
                "x:prov:1:provided", "x:opt:1:compile:optional",
            ],
            "org.demo:core:3.0": [],
            "junit:junit:4.13": ["org.hamcrest:hamcrest:1.3"],
        })
        self.assertEqual(
            graph.edges[APP], ["org.demo:lib:2.0", "junit:junit:4.13"]
        )
        self.assertEqual(graph.edges["org.demo:lib:2.0"],
                         ["org.demo:core:3.0"])
        self.assertEqual(graph.edges["junit:junit:4.13"],
                         ["org.hamcrest:hamcrest:1.3"])

    def test_cycle(self):
        """Циклическая зависимость между pom-файлами обнаруживается."""
        graph = graph_for({
            APP: ["org.demo:lib:2.0"],
            "org.demo:lib:2.0": [APP],
        })
        self.assertEqual(len(graph.cycles), 1)
        self.assertEqual(set(graph.cycles[0]), {APP, "org.demo:lib:2.0"})

    def test_missing_transitive_pom_is_skipped(self):
        """Недоступный pom зависимости - предупреждение, а не сбой."""
        graph = graph_for({APP: ["org.demo:gone:9.9", "org.demo:ok:1.0"],
                           "org.demo:ok:1.0": []})
        self.assertIn("org.demo:gone:9.9", graph.skipped)
        self.assertIn("org.demo:ok:1.0", graph.expanded)

    def test_unresolved_version_is_skipped(self):
        """Диапазон версий пропускается с пояснением."""
        graph = graph_for({APP: ["org.demo:range:[1.0,2.0)"]})
        self.assertEqual(len(graph.skipped), 1)

    def test_missing_root_raises(self):
        """Отсутствующий корневой pom - ошибка."""
        with self.assertRaises(FetchError):
            graph_for({})

    def test_depth_limit(self):
        """Глубина ограничивает число загружаемых pom-файлов."""
        graph = graph_for({
            APP: ["org.demo:lib:2.0"],
            "org.demo:lib:2.0": ["org.demo:core:3.0"],
        }, depth=1)
        self.assertEqual(list(graph.edges), [APP, "org.demo:lib:2.0"])


class ParseNodeTests(unittest.TestCase):
    """Проверки разбора имени узла."""

    def test_valid(self):
        """Корректное имя разбирается на координаты."""
        coordinate = parse_node("a.b:c-d:1.0.0")
        self.assertEqual(str(coordinate), "a.b:c-d:1.0.0")

    def test_invalid(self):
        """Некорректные имена отклоняются."""
        for node in ["a:b", "a:b:?", "a:b:${v}", "a:b:[1,2)", "a:b:c:d", ""]:
            with self.subTest(node=node):
                with self.assertRaises(FetchError):
                    parse_node(node)


if __name__ == "__main__":
    unittest.main()
