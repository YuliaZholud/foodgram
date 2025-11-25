"""Пользовательские классы разрешений для API."""

from rest_framework import permissions
from rest_framework.permissions import IsAuthenticatedOrReadOnly


class IsAuthenticatedAuthorOrReadOnly(IsAuthenticatedOrReadOnly):
    """
    Разрешение для объектов.

    - безопасные методы (GET, HEAD, OPTIONS) доступны всем;
    - небезопасные методы доступны только аутентифицированному автору объекта.
    """

    def has_object_permission(self, request, view, obj):
        """Проверить права доступа к объекту."""
        is_safe_method = request.method in permissions.SAFE_METHODS
        is_author = getattr(obj, 'author', None) == request.user
        return is_safe_method or is_author
