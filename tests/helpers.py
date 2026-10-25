"""Вспомогательные функции для тестов."""

from typing import Dict, List

from depviz.errors import FetchError

REPO = "https://repo.test/maven2"


def make_fetch(files: Dict[str, str]):
    """Вернуть загрузчик, читающий данные из словаря url -> текст."""
    def fetch(url: str) -> bytes:
        """Вернуть содержимое по URL или выбросить FetchError."""
        if url not in files:
            raise FetchError(f"файл не найден: {url}")
        return files[url].encode("utf-8")
    return fetch


def dependency_xml(text: str) -> str:
    """Построить <dependency> из строки 'g:a:v[:scope[:optional]]'."""
    keys = ("group", "artifact", "version", "scope", "optional")
    fields = dict(zip(keys, text.split(":")))
    scope = f"<scope>{fields['scope']}</scope>" if "scope" in fields else ""
    optional = "<optional>true</optional>" if "optional" in fields else ""
    return (
        f"<dependency><groupId>{fields['group']}</groupId>"
        f"<artifactId>{fields['artifact']}</artifactId>"
        f"<version>{fields['version']}</version>{scope}{optional}"
        "</dependency>"
    )


def make_pom(coordinate: str, dependencies: List[str]) -> str:
    """Собрать pom.xml; зависимость - 'g:a:v' или 'g:a:v:scope[:optional]'."""
    group_id, artifact_id, version = coordinate.split(":")
    items = "".join(dependency_xml(text) for text in dependencies)
    return (
        f"<project><groupId>{group_id}</groupId>"
        f"<artifactId>{artifact_id}</artifactId><version>{version}</version>"
        f"<dependencies>{items}</dependencies></project>"
    )
