"""Кастомные валидаторы для пользователей."""

from django.core.exceptions import ValidationError

from .constants import NOT_ALLOWED_USER_NAME


def not_allowed_user_name(value):
    """Запретить использование зарезервированных имён в нике пользователя."""
    if value in NOT_ALLOWED_USER_NAME:
        raise ValidationError(
            f'"{value}" — запрещённое значение для имени пользователя.',
        )
    return value
