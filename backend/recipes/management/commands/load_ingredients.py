import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from recipes.models import Ingredient


class Command(BaseCommand):
    help = 'Загрузка ингредиентов из data/ingredients.json'

    def handle(self, *args, **options):
        file_path = os.path.join(
            settings.BASE_DIR.parent,
            'data',
            'ingredients.json',
        )

        if not os.path.exists(file_path):
            self.stdout.write(
                self.style.ERROR(f'Файл не найден: {file_path}'),
            )
            return

        with open(file_path, encoding='utf-8') as ingredients_file:
            data = json.load(ingredients_file)

        created = 0

        for item in data:
            name = item.get('name')
            measurement_unit = item.get('measurement_unit')

            # Пропускаем записи без имени или единицы измерения
            if not name or not measurement_unit:
                continue

            _, is_created = Ingredient.objects.get_or_create(
                name=name,
                measurement_unit=measurement_unit,
            )
            if is_created:
                created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Загрузка завершена, создано {created} ингредиентов',
            ),
        )
