"""Пользовательские разрешения для API."""

from rest_framework import permissions


class OwnerOrReadOnly(permissions.BasePermission):
    """
    Разрешение для объектов.

    Изменять объект может только его автор, остальные имеют доступ
    только на чтение.
    """

    def has_object_permission(self, request, view, obj):
        """Проверить права доступа к объекту."""
        is_safe_method = request.method in permissions.SAFE_METHODS
        is_author = getattr(obj, 'author', None) == request.user
        return is_safe_method or is_author
