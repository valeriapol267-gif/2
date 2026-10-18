"""Параметры командной строки и их проверка."""

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, Optional, Sequence
from urllib.parse import urlparse

from depviz.errors import ConfigError

PROGRAM_NAME = "depviz"
DEFAULT_REPO_URL = "https://repo1.maven.org/maven2"
DEFAULT_OUTPUT = "graph.png"
DEFAULT_MAX_DEPTH = 3
MIN_DEPTH = 1
MAX_DEPTH_LIMIT = 100
OUTPUT_EXTENSION = ".png"
ALLOWED_SCHEMES = ("http", "https")
MAVEN_NAME_RE = re.compile(r"[A-Za-z0-9_.\-]+:[A-Za-z0-9_.\-]+")
TEST_NAME_RE = re.compile(r"[A-Z]+")
VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.+\-]*")
FORBIDDEN_NAME_CHARS = frozenset('<>:"/\\|?*')


@dataclass(frozen=True)
class Config:
    """Проверенные параметры, заданные пользователем."""

    package: str
    repo: str
    test_mode: bool
    version: Optional[str]
    output: str
    max_depth: int



class ArgumentParserWithErrors(argparse.ArgumentParser):
    """Парсер, который сообщает об ошибках исключением, а не выходом."""

    def error(self, message: str) -> NoReturn:
        """Преобразовать ошибку разбора аргументов в ConfigError."""
        raise ConfigError(message)


def build_parser() -> argparse.ArgumentParser:
    """Создать парсер опций командной строки."""
    parser = ArgumentParserWithErrors(
        prog=PROGRAM_NAME,
        allow_abbrev=False,
        description="Визуализация графа зависимостей Maven-пакета.",
    )
    parser.add_argument(
        "--package",
        help="имя пакета: groupId:artifactId (в тестовом режиме: A, B, ...)",
    )
    parser.add_argument(
        "--repo",
        help="URL Maven-репозитория или путь к файлу тестового репозитория "
        f"(по умолчанию {DEFAULT_REPO_URL})",
    )
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="работать с файлом тестового репозитория вместо URL",
    )
    parser.add_argument(
        "--version",
        help="версия пакета (обязательна вне тестового режима)",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"имя файла с изображением графа (по умолчанию "
        f"{DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--max-depth",
        default=str(DEFAULT_MAX_DEPTH),
        help="максимальная глубина анализа зависимостей "
        f"(от {MIN_DEPTH} до {MAX_DEPTH_LIMIT}, "
        f"по умолчанию {DEFAULT_MAX_DEPTH})",
    )
    return parser


def validate_package(package: Optional[str], test_mode: bool) -> str:
    """Проверить имя пакета с учётом режима работы."""
    if package is None:
        raise ConfigError("не задано имя пакета (--package).")
    if test_mode:
        if not TEST_NAME_RE.fullmatch(package):
            raise ConfigError(
                f"имя пакета в тестовом режиме должно состоять из больших "
                f"латинских букв (A, B, ...): {package!r}."
            )
    elif not MAVEN_NAME_RE.fullmatch(package):
        raise ConfigError(
            f"имя пакета должно иметь вид groupId:artifactId: {package!r}."
        )
    return package


def check_test_repo_path(repo: str) -> str:
    """Проверить, что путь указывает на читаемый файл."""
    path = Path(repo)
    if not path.is_file():
        raise ConfigError(
            f"файл тестового репозитория не найден: {repo!r}."
        )
    if not os.access(path, os.R_OK):
        raise ConfigError(
            f"нет доступа на чтение файла тестового репозитория: {repo!r}."
        )
    return repo


def check_repo_url(repo: str) -> str:
    """Проверить URL репозитория и убрать завершающие символы «/»."""
    try:
        parsed = urlparse(repo)
    except ValueError:
        raise ConfigError(f"некорректный URL репозитория: {repo!r}.") from None
    has_space = any(char.isspace() for char in repo)
    if parsed.scheme not in ALLOWED_SCHEMES or not parsed.hostname or has_space:
        raise ConfigError(
            "URL репозитория должен иметь вид http(s)://хост/путь: "
            f"{repo!r}."
        )
    return repo.rstrip("/")


def validate_repo(repo: Optional[str], test_mode: bool) -> str:
    """Проверить URL репозитория либо путь к файлу тестового репозитория."""
    if test_mode:
        if repo is None:
            raise ConfigError(
                "в тестовом режиме нужно указать путь к файлу (--repo)."
            )
        return check_test_repo_path(repo)
    return check_repo_url(DEFAULT_REPO_URL if repo is None else repo)


def validate_version(version: Optional[str], test_mode: bool) -> Optional[str]:
    """Проверить версию пакета; в тестовом режиме она необязательна."""
    if version is None:
        if test_mode:
            return None
        raise ConfigError("не задана версия пакета (--version).")
    if not VERSION_RE.fullmatch(version):
        raise ConfigError(f"некорректная версия пакета: {version!r}.")
    return version


def validate_output(output: str) -> str:
    """Проверить имя файла изображения графа."""
    path = Path(output)
    name = path.name
    if not name or path.suffix.lower() != OUTPUT_EXTENSION:
        raise ConfigError(
            f"имя файла изображения должно оканчиваться на "
            f"{OUTPUT_EXTENSION}: {output!r}."
        )
    if FORBIDDEN_NAME_CHARS & set(name) or not name.isprintable():
        raise ConfigError(
            f"имя файла изображения содержит недопустимые символы: "
            f"{output!r}."
        )
    if not path.parent.is_dir():
        raise ConfigError(f"каталог для файла не существует: {output!r}.")
    if path.is_dir():
        raise ConfigError(f"{output!r} является каталогом, а не файлом.")
    return output


def validate_depth(raw_depth: str) -> int:
    """Преобразовать глубину анализа в число и проверить её границы."""
    try:
        depth = int(raw_depth)
    except ValueError:
        raise ConfigError(
            f"максимальная глубина должна быть целым числом: {raw_depth!r}."
        ) from None
    if not MIN_DEPTH <= depth <= MAX_DEPTH_LIMIT:
        raise ConfigError(
            f"максимальная глубина должна быть от {MIN_DEPTH} до "
            f"{MAX_DEPTH_LIMIT}: {depth}."
        )
    return depth


def parse_config(argv: Optional[Sequence[str]] = None) -> Config:
    """Разобрать аргументы командной строки и проверить все параметры."""
    args = build_parser().parse_args(argv)
    return Config(
        package=validate_package(args.package, args.test_mode),
        repo=validate_repo(args.repo, args.test_mode),
        test_mode=args.test_mode,
        version=validate_version(args.version, args.test_mode),
        output=validate_output(args.output),
        max_depth=validate_depth(args.max_depth),
    )
