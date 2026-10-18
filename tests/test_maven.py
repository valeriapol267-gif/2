"""Тесты разбора pom.xml и вычисления прямых зависимостей."""

import unittest

from depviz.errors import FetchError
from depviz.maven import (
    Coordinate,
    get_direct_dependencies,
    parse_coordinate,
    pom_url,
)

REPO = "https://repo.test/maven2"
APP = Coordinate("org.demo", "app", "1.0")

SIMPLE_POM = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>org.demo</groupId>
  <artifactId>app</artifactId>
  <version>1.0</version>
  <properties><junit.version>4.13.2</junit.version></properties>
  <dependencies>
    <dependency>
      <groupId>org.slf4j</groupId><artifactId>slf4j-api</artifactId>
      <version>2.0.9</version>
    </dependency>
    <dependency>
      <groupId>junit</groupId><artifactId>junit</artifactId>
      <version>${junit.version}</version><scope>test</scope>
    </dependency>
    <dependency>
      <groupId>com.google.code.findbugs</groupId>
      <artifactId>jsr305</artifactId><version>3.0.2</version>
      <optional>true</optional>
    </dependency>
    <dependency><artifactId>broken</artifactId></dependency>
  </dependencies>
</project>"""

CHILD_POM = """<project>
  <artifactId>app</artifactId>
  <parent>
    <groupId>org.demo</groupId><artifactId>parent</artifactId>
    <version>1.0</version>
  </parent>
  <dependencies>
    <dependency>
      <groupId>org.managed</groupId><artifactId>lib</artifactId>
    </dependency>
    <dependency>
      <groupId>${project.groupId}</groupId><artifactId>core</artifactId>
      <version>${project.version}</version>
    </dependency>
    <dependency>
      <groupId>org.bom</groupId><artifactId>noversion</artifactId>
    </dependency>
  </dependencies>
</project>"""

PARENT_POM = """<project>
  <groupId>org.demo</groupId><artifactId>parent</artifactId>
  <version>1.0</version>
  <properties>
    <lib.version>${base.version}.1</lib.version>
    <base.version>5.2</base.version>
  </properties>
  <dependencyManagement><dependencies>
    <dependency>
      <groupId>org.managed</groupId><artifactId>lib</artifactId>
      <version>${lib.version}</version><scope>runtime</scope>
    </dependency>
    <dependency>
      <groupId>org.bom</groupId><artifactId>bom</artifactId>
      <version>9</version><scope>import</scope><type>pom</type>
    </dependency>
  </dependencies></dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>org.inherited</groupId><artifactId>util</artifactId>
      <version>3.3</version>
    </dependency>
  </dependencies>
</project>"""


def make_fetch(files):
    """Вернуть функцию загрузки, читающую данные из словаря url -> текст."""
    def fetch(url):
        """Вернуть содержимое по URL или выбросить FetchError."""
        if url not in files:
            raise FetchError(f"файл не найден: {url}")
        return files[url].encode("utf-8")
    return fetch


class PomUrlTests(unittest.TestCase):
    """Проверки построения адреса pom-файла."""

    def test_layout(self):
        """URL соответствует стандартной раскладке Maven."""
        package = "org.apache.commons:commons-lang3"
        coordinate = parse_coordinate(package, "3.14.0")
        self.assertEqual(
            pom_url(REPO, coordinate),
            f"{REPO}/org/apache/commons/commons-lang3/3.14.0/"
            "commons-lang3-3.14.0.pom",
        )


class DirectDependenciesTests(unittest.TestCase):
    """Проверки вычисления прямых зависимостей."""

    def test_simple_pom(self):
        """Пространство имён, свойства, scope и optional обрабатываются."""
        fetch = make_fetch({pom_url(REPO, APP): SIMPLE_POM})
        deps = get_direct_dependencies(APP, REPO, fetch)
        names = [(dep.artifact_id, dep.version, dep.scope) for dep in deps]
        self.assertEqual(names, [
            ("slf4j-api", "2.0.9", "compile"),
            ("junit", "4.13.2", "test"),
            ("jsr305", "3.0.2", "compile"),
        ])
        self.assertTrue(deps[-1].optional)
        self.assertFalse(deps[0].optional)

    def test_parent_inheritance(self):
        """Версии, scope и зависимости наследуются от parent."""
        parent = Coordinate("org.demo", "parent", "1.0")
        child = Coordinate("org.demo", "app", "1.0")
        fetch = make_fetch({
            pom_url(REPO, child): CHILD_POM,
            pom_url(REPO, parent): PARENT_POM,
        })
        found = get_direct_dependencies(child, REPO, fetch)
        deps = {dep.artifact_id: dep for dep in found}
        self.assertEqual(deps["lib"].version, "5.2.1")
        self.assertEqual(deps["lib"].scope, "runtime")
        self.assertEqual(deps["core"].group_id, "org.demo")
        self.assertEqual(deps["core"].version, "1.0")
        self.assertEqual(deps["util"].version, "3.3")
        self.assertIsNone(deps["noversion"].version)

    def test_missing_pom(self):
        """Отсутствующий pom приводит к FetchError."""
        with self.assertRaises(FetchError):
            get_direct_dependencies(APP, REPO, make_fetch({}))

    def test_missing_parent(self):
        """Отсутствующий parent-pom приводит к FetchError."""
        child = Coordinate("org.demo", "app", "1.0")
        fetch = make_fetch({pom_url(REPO, child): CHILD_POM})
        with self.assertRaises(FetchError):
            get_direct_dependencies(child, REPO, fetch)

    def test_invalid_xml(self):
        """Некорректный XML и чужой корневой тег дают FetchError."""
        for text in ["<project>", "not xml", "<other/>"]:
            with self.subTest(text=text):
                fetch = make_fetch({pom_url(REPO, APP): text})
                with self.assertRaises(FetchError):
                    get_direct_dependencies(APP, REPO, fetch)

    def test_parent_cycle(self):
        """Цикл в цепочке parent не приводит к зависанию."""
        pom = """<project><artifactId>app</artifactId>
        <parent><groupId>org.demo</groupId><artifactId>app</artifactId>
        <version>1.0</version></parent></project>"""
        fetch = make_fetch({pom_url(REPO, APP): pom})
        with self.assertRaises(FetchError):
            get_direct_dependencies(APP, REPO, fetch)


if __name__ == "__main__":
    unittest.main()
