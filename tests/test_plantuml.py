"""Тесты генерации и кодирования PlantUML."""

import unittest
import zlib

from depviz.graph import build_graph
from depviz.plantuml import (
    ENCODING_ALPHABET,
    build_plantuml,
    encode_plantuml,
    node_label,
)
from tests.test_graph import DictSource

DIAMOND = {"A": ["B", "C"], "B": ["D"], "C": ["D"]}


def puml_for(packages, root="A", depth=5, reverse=False, broken=()):
    """Построить граф и вернуть его описание PlantUML."""
    graph = build_graph(DictSource(packages, broken), root, depth)
    return build_plantuml(graph, depth, reverse)


def decode_plantuml(encoded):
    """Раскодировать строку PlantUML обратно в текст (для проверки)."""
    values = [ENCODING_ALPHABET.index(char) for char in encoded]
    data = bytearray()
    for start in range(0, len(values), 4):
        first, second, third, fourth = values[start:start + 4]
        data.append((first << 2) | (second >> 4))
        data.append(((second & 0x0F) << 4) | (third >> 2))
        data.append(((third & 0x03) << 6) | fourth)
    unpacker = zlib.decompressobj(-zlib.MAX_WBITS)
    return unpacker.decompress(bytes(data)).decode("utf-8")


class BuildTests(unittest.TestCase):
    """Проверки текста диаграммы."""

    def test_diamond(self):
        """Ромб: узлы, рёбра и подсветка корня."""
        self.assertEqual(puml_for(DIAMOND, depth=5), "\n".join([
            "@startuml",
            "title Граф зависимостей A (макс. глубина 5)",
            "skinparam shadowing false",
            "left to right direction",
            'rectangle "A" as n0 #LightBlue',
            'rectangle "B" as n1',
            'rectangle "D" as n2',
            'rectangle "C" as n3',
            "n0 --> n1",
            "n0 --> n3",
            "n1 --> n2",
            "n3 --> n2",
            "@enduml",
            "",
        ]))

    def test_cycle_edges_are_red(self):
        """Рёбра, образующие цикл, выделены красным."""
        text = puml_for({"A": ["B"], "B": ["A"]})
        self.assertIn("n0 -[#red]-> n1", text)
        self.assertIn("n1 -[#red]-> n0", text)

    def test_edge_outside_cycle_is_plain(self):
        """Ребро вне цикла остаётся обычным."""
        text = puml_for({"A": ["B"], "B": ["C"], "C": ["B"]})
        self.assertIn("n0 --> n1", text)
        self.assertIn("n1 -[#red]-> n2", text)

    def test_truncated_and_skipped_colors(self):
        """Не раскрытые узлы серые, недоступные - розовые."""
        text = puml_for({"A": ["B", "C"], "B": ["D"]}, depth=1, broken=["C"])
        self.assertIn('rectangle "B" as n1 #LightGray', text)
        broken = puml_for({"A": ["B", "C"]}, broken=["C"])
        self.assertIn('rectangle "C" as n2 #Pink', broken)

    def test_reverse_arrows_point_to_dependency(self):
        """В обратном режиме стрелка идёт от зависимого пакета."""
        text = puml_for({"D": ["B"], "B": ["A"]}, root="D", reverse=True)
        self.assertIn("title Обратные зависимости D", text)
        self.assertIn("n1 --> n0", text)

    def test_maven_label(self):
        """Версия Maven-пакета переносится на вторую строку."""
        self.assertEqual(node_label("org.demo:app:1.0"), "org.demo:app\\n1.0")
        self.assertEqual(node_label("A"), "A")


class EncodeTests(unittest.TestCase):
    """Проверки кодирования для сервера PlantUML."""

    def test_known_vectors(self):
        """Результат совпадает с примерами из документации PlantUML."""
        self.assertEqual(
            encode_plantuml("Bob -> Alice : hello"),
            "SyfFKj2rKt3CoKnELR1Io4ZDoSa70000",
        )
        self.assertEqual(
            encode_plantuml("@startuml\nBob -> Alice : hello\n@enduml"),
            "SoWkIImgAStDuNBAJrBGjLDmpCbCJbMmKiX8pSd9vt98pKi1IW80",
        )

    def test_round_trip(self):
        """Закодированный текст (включая кириллицу) восстанавливается."""
        text = puml_for(DIAMOND) * 20 + "Привет, мир!"
        self.assertEqual(decode_plantuml(encode_plantuml(text)), text)

    def test_url_safe_alphabet(self):
        """Результат состоит только из символов, допустимых в адресе."""
        encoded = encode_plantuml("тест " * 100)
        self.assertTrue(set(encoded) <= set(ENCODING_ALPHABET))


if __name__ == "__main__":
    unittest.main()
