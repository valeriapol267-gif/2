"""Получение прямых зависимостей Maven-пакета из его pom.xml.

Учитывается наследование от parent-pom (свойства, dependencyManagement
и зависимости), подстановка свойств ``${...}``. Профили, BOM-импорты
(scope ``import``) и диапазоны версий не разворачиваются.
"""

import re
from dataclasses import dataclass, replace
from typing import Callable, Dict, Iterable, List, Optional, Tuple
from xml.etree import ElementTree

from depviz.errors import FetchError

Fetcher = Callable[[str], bytes]
DependencyKey = Tuple[str, str]

MAX_PARENT_DEPTH = 10
MAX_INTERPOLATION_PASSES = 10
DEFAULT_SCOPE = "compile"
IMPORT_SCOPE = "import"
ROOT_TAG = "project"
PROPERTY_RE = re.compile(r"\$\{([^}]+)\}")
MODEL_PREFIXES = ("project", "pom")


@dataclass(frozen=True)
class Coordinate:
    """Координаты Maven-артефакта."""

    group_id: str
    artifact_id: str
    version: str

    def __str__(self) -> str:
        """Вернуть строку вида groupId:artifactId:version."""
        return f"{self.group_id}:{self.artifact_id}:{self.version}"


@dataclass(frozen=True)
class Dependency:
    """Зависимость, объявленная в pom.xml."""

    group_id: str
    artifact_id: str
    version: Optional[str] = None
    scope: Optional[str] = None
    optional: bool = False


@dataclass
class PomLayer:
    """Данные одного pom.xml из цепочки наследования."""

    coordinate: Coordinate
    parent: Optional[Coordinate]
    properties: Dict[str, str]
    managed: List[Dependency]
    dependencies: List[Dependency]


def pom_url(repo: str, coordinate: Coordinate) -> str:
    """Построить URL файла pom по стандартной раскладке Maven."""
    group_path = coordinate.group_id.replace(".", "/")
    artifact = coordinate.artifact_id
    file_name = f"{artifact}-{coordinate.version}.pom"
    return f"{repo}/{group_path}/{artifact}/{coordinate.version}/{file_name}"


def parse_coordinate(package: str, version: str) -> Coordinate:
    """Создать координаты из имени groupId:artifactId и версии."""
    group_id, _, artifact_id = package.partition(":")
    return Coordinate(group_id, artifact_id, version)


def parse_pom(data: bytes, url: str) -> ElementTree.Element:
    """Разобрать XML pom-файла и убрать пространства имён из тегов."""
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as error:
        raise FetchError(f"некорректный XML в {url}: {error}.") from error
    for element in root.iter():
        if isinstance(element.tag, str):
            element.tag = element.tag.rpartition("}")[2]
    if root.tag != ROOT_TAG:
        raise FetchError(f"файл {url} не является pom.xml (нет <project>).")
    return root


def child_text(element: ElementTree.Element, name: str) -> Optional[str]:
    """Вернуть непустой текст дочернего тега либо None."""
    child = element.find(name)
    if child is None or child.text is None:
        return None
    return child.text.strip() or None


def read_parent(root: ElementTree.Element, url: str) -> Optional[Coordinate]:
    """Прочитать блок <parent>, если он есть."""
    node = root.find("parent")
    if node is None:
        return None
    tags = ("groupId", "artifactId", "version")
    values = [child_text(node, tag) for tag in tags]
    if None in values:
        raise FetchError(f"неполный блок <parent> в {url}.")
    return Coordinate(*values)


def read_properties(root: ElementTree.Element) -> Dict[str, str]:
    """Прочитать блок <properties> в словарь."""
    node = root.find("properties")
    if node is None:
        return {}
    return {
        child.tag: (child.text or "").strip()
        for child in node
        if isinstance(child.tag, str)
    }


def read_dependencies(
    node: Optional[ElementTree.Element],
) -> List[Dependency]:
    """Прочитать список <dependency> из блока <dependencies>."""
    if node is None:
        return []
    result = []
    for item in node.findall("dependency"):
        group_id = child_text(item, "groupId")
        artifact_id = child_text(item, "artifactId")
        if group_id is None or artifact_id is None:
            continue
        optional = (child_text(item, "optional") or "").lower() == "true"
        result.append(Dependency(
            group_id, artifact_id, child_text(item, "version"),
            child_text(item, "scope"), optional,
        ))
    return result


def read_managed(root: ElementTree.Element) -> List[Dependency]:
    """Прочитать dependencyManagement без BOM-импортов."""
    node = root.find("dependencyManagement")
    if node is None:
        return []
    items = read_dependencies(node.find("dependencies"))
    return [item for item in items if item.scope != IMPORT_SCOPE]


def build_layer(root: ElementTree.Element, url: str) -> PomLayer:
    """Собрать PomLayer из корня pom.xml; наследует groupId и version."""
    parent = read_parent(root, url)
    group_id = child_text(root, "groupId") or (parent and parent.group_id)
    version = child_text(root, "version") or (parent and parent.version)
    artifact_id = child_text(root, "artifactId")
    if not (group_id and artifact_id and version):
        raise FetchError(f"в {url} не удалось определить groupId/version.")
    return PomLayer(
        coordinate=Coordinate(group_id, artifact_id, version),
        parent=parent,
        properties=read_properties(root),
        managed=read_managed(root),
        dependencies=read_dependencies(root.find("dependencies")),
    )


def load_layer(coordinate: Coordinate, repo: str, fetch: Fetcher) -> PomLayer:
    """Скачать pom заданного артефакта и разобрать его."""
    url = pom_url(repo, coordinate)
    return build_layer(parse_pom(fetch(url), url), url)


def load_chain(
    coordinate: Coordinate, repo: str, fetch: Fetcher
) -> List[PomLayer]:
    """Загрузить pom и всех его предков; первым идёт сам артефакт."""
    layers: List[PomLayer] = []
    current = coordinate
    for _ in range(MAX_PARENT_DEPTH):
        layer = load_layer(current, repo, fetch)
        layers.append(layer)
        if layer.parent is None:
            return layers
        current = layer.parent
    raise FetchError(f"слишком длинная цепочка parent для {coordinate}.")


def model_properties(layer: PomLayer) -> Dict[str, str]:
    """Встроенные свойства project.* и pom.* для артефакта."""
    values = {
        "groupId": layer.coordinate.group_id,
        "artifactId": layer.coordinate.artifact_id,
        "version": layer.coordinate.version,
    }
    if layer.parent is not None:
        values["parent.groupId"] = layer.parent.group_id
        values["parent.version"] = layer.parent.version
    return {
        f"{prefix}.{key}": value
        for prefix in MODEL_PREFIXES
        for key, value in values.items()
    }


def collect_properties(layers: List[PomLayer]) -> Dict[str, str]:
    """Объединить свойства цепочки; свойства потомка важнее родителя."""
    properties: Dict[str, str] = {}
    for layer in reversed(layers):
        properties.update(layer.properties)
    properties.update(model_properties(layers[0]))
    return properties


def interpolate(
    text: Optional[str], properties: Dict[str, str]
) -> Optional[str]:
    """Подставить значения свойств вместо ${имя} (многократно)."""
    if text is None:
        return None
    for _ in range(MAX_INTERPOLATION_PASSES):
        replaced = PROPERTY_RE.sub(
            lambda match: properties.get(match.group(1), match.group(0)),
            text,
        )
        if replaced == text:
            break
        text = replaced
    return text


def resolve(dep: Dependency, properties: Dict[str, str]) -> Dependency:
    """Подставить свойства во все текстовые поля зависимости."""
    return replace(
        dep,
        group_id=interpolate(dep.group_id, properties),
        artifact_id=interpolate(dep.artifact_id, properties),
        version=interpolate(dep.version, properties),
        scope=interpolate(dep.scope, properties),
    )


def merge(
    groups: Iterable[List[Dependency]], properties: Dict[str, str]
) -> Dict[DependencyKey, Dependency]:
    """Объединить списки зависимостей; более поздние перекрывают ранние."""
    merged: Dict[DependencyKey, Dependency] = {}
    for group in groups:
        for dep in group:
            resolved = resolve(dep, properties)
            merged[(resolved.group_id, resolved.artifact_id)] = resolved
    return merged


def apply_management(
    dep: Dependency, managed: Dict[DependencyKey, Dependency]
) -> Dependency:
    """Дополнить версию и scope значениями из dependencyManagement."""
    entry = managed.get((dep.group_id, dep.artifact_id))
    version = dep.version or (entry.version if entry else None)
    scope = dep.scope or (entry.scope if entry else None) or DEFAULT_SCOPE
    return replace(dep, version=version, scope=scope)


def effective_dependencies(layers: List[PomLayer]) -> List[Dependency]:
    """Вычислить итоговые прямые зависимости артефакта."""
    properties = collect_properties(layers)
    ancestors_first = list(reversed(layers))
    managed = merge([layer.managed for layer in ancestors_first], properties)
    declared = merge(
        [layer.dependencies for layer in ancestors_first], properties
    )
    return [apply_management(dep, managed) for dep in declared.values()]


def get_direct_dependencies(
    coordinate: Coordinate, repo: str, fetch: Fetcher
) -> List[Dependency]:
    """Получить прямые зависимости артефакта из Maven-репозитория."""
    return effective_dependencies(load_chain(coordinate, repo, fetch))
