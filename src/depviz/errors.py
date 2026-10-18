"""Исключения приложения."""


class DepvizError(Exception):
    """Базовое исключение приложения."""


class ConfigError(DepvizError):
    """Некорректные параметры командной строки."""


class FetchError(DepvizError):
    """Ошибка получения или разбора данных репозитория."""
