"""Источник зависимостей на основе Maven-репозитория.

Пакет в графе - строка ``groupId:artifactId:version``. Для корня
учитываются все зависимости, для остальных пакетов - только
транзитивные (без scope test/provided/system и без optional), как это
делает Maven. Медиация версий не выполняется: одна и та же библиотека
разных версий - разные узлы графа.
"""

import re
from typing import Dict, List

from depviz.config import VERSION_RE
from depviz.errors import FetchError
from depviz.maven import (
    Coordinate,
    Dependency,
    Fetcher,
    get_direct_dependencies,
)

NODE_PARTS = 3
UNKNOWN_VERSION = "?"
NAME_PART_RE = re.compile(r"[A-Za-z0-9_.\-]+")
NON_TRANSITIVE_SCOPES = frozenset({"test", "provided", "system"})


def node_id(dep: Dependency) -> str:
    """Вернуть имя узла графа для зависимости."""
    version = dep.version or UNKNOWN_VERSION
    return f"{dep.group_id}:{dep.artifact_id}:{version}"


def parse_node(node: str) -> Coordinate:
    """Разобрать имя узла; отклонить неопределённые версии и диапазоны."""
    parts = node.split(":")
    if len(parts) == NODE_PARTS:
        group_id, artifact_id, version = parts
        if (
            NAME_PART_RE.fullmatch(group_id)
            and NAME_PART_RE.fullmatch(artifact_id)
            and VERSION_RE.fullmatch(version)
        ):
            return Coordinate(group_id, artifact_id, version)
    raise FetchError(
        f"некорректные координаты {node!r}: версия не определена, "
        "является диапазоном или содержит неразрешённое свойство."
    )


def is_transitive(dep: Dependency) -> bool:
    """Проверить, попадает ли зависимость в транзитивное замыкание."""
    return dep.scope not in NON_TRANSITIVE_SCOPES and not dep.optional


def memoize_fetch(fetch: Fetcher) -> Fetcher:
    """Обернуть загрузчик кэшем: parent-pom скачиваются один раз."""
    cache: Dict[str, bytes] = {}

    def cached(url: str) -> bytes:
        """Вернуть содержимое URL из кэша или загрузить его."""
        if url not in cache:
            cache[url] = fetch(url)
        return cache[url]

    return cached


class MavenRepository:
    """Источник зависимостей, читающий pom.xml из Maven-репозитория."""

    def __init__(self, repo_url: str, fetch: Fetcher, root: str) -> None:
        """Создать источник для репозитория ``repo_url`` и корня ``root``."""
        self.repo_url = repo_url
        self.fetch = memoize_fetch(fetch)
        self.root = root
        self.cache: Dict[str, List[Dependency]] = {}

    def dependencies(self, node: str) -> List[str]:
        """Вернуть имена узлов-зависимостей пакета ``node``."""
        if node not in self.cache:
            self.cache[node] = get_direct_dependencies(
                parse_node(node), self.repo_url, self.fetch
            )
        deps = self.cache[node]
        if node != self.root:
            deps = [dep for dep in deps if is_transitive(dep)]
        return [node_id(dep) for dep in deps]
