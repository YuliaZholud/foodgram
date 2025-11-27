"""Сервисные классы для приложения api."""

import base64
import random
import string
import uuid

from django.core.files.base import ContentFile
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination


class Base64ImageField(serializers.ImageField):
    """Поле для приёма изображений в формате Base64."""

    def __init__(self, *args, **kwargs):
        """Инициализировать поле с поддержкой префикса имени файла."""
        file_prefix = kwargs.pop('file_prefix', 'file')  # убираем свой параметр
        super().__init__(*args, **kwargs)  # вызываем родителя раньше
        self.file_prefix = file_prefix  # и только потом задаём свои поля

    def to_internal_value(self, data):
        """Преобразовать Base64-строку в объект загружаемого файла."""
        if not (isinstance(data, str) and data.startswith('data:image')):
            return super().to_internal_value(data)

        fmt, img_str = data.split(';base64,')
        ext = fmt.split('/')[-1]

        unique_id = uuid.uuid4()
        filename = f'{self.file_prefix}_{unique_id}.{ext}'

        data = ContentFile(base64.b64decode(img_str), name=filename)
        return super().to_internal_value(data)


class Pagination(PageNumberPagination):
    """Постраничная пагинация для API."""

    page_size = 6
    page_size_query_param = 'limit'
    max_page_size = 100


class ShortLink:
    """Генератор коротких ссылок для рецептов."""

    alphabet = string.ascii_letters + string.digits

    def create_short_link(self, length):
        """Создать случайную строку заданной длины."""
        return ''.join(random.choices(self.alphabet, k=length))
