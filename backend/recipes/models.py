"""Модели приложения recipes."""

from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from recipes.constants import (
    MAX_RECIPE_NAME_LENGTH,
    MAX_VIEW_LENGTH,
    MIN_COOKING_TIME,
    MIN_INGREDIENT_COUNT,
    SHORT_LINK_MAX_LENGTH,
    SOME_RESRICTION,
)

User = get_user_model()


class Tag(models.Model):
    """Тег рецепта."""

    name = models.CharField(
        verbose_name='Имя тэга',
        unique=True,
        max_length=SOME_RESRICTION,
    )
    slug = models.SlugField(
        verbose_name='Слаг',
        unique=True,
        max_length=SOME_RESRICTION,
    )

    class Meta:
        """Настройки модели."""

        ordering = ('name',)
        verbose_name = 'Тег'
        verbose_name_plural = 'Теги'

    def __str__(self):
        """Строковое представление объекта."""
        return self.name[:MAX_VIEW_LENGTH]


class Ingredient(models.Model):
    """Ингредиент."""

    name = models.CharField(
        verbose_name='Наименование ингредиента',
        max_length=SOME_RESRICTION,
    )
    measurement_unit = models.CharField(
        verbose_name='Единица измерения',
        max_length=SOME_RESRICTION,
    )

    class Meta:
        """Настройки модели."""

        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'
        ordering = ('name',)
        default_related_name = 'ingredients'
        constraints = [
            models.UniqueConstraint(
                fields=('name', 'measurement_unit'),
                name='unique_ingredient_name_unit',
            )
        ]

    def __str__(self):
        """Строковое представление объекта."""
        return self.name[:MAX_VIEW_LENGTH]


class Recipe(models.Model):
    """Рецепт."""

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Автор',
        related_name='recipes',
    )
    name = models.CharField(
        max_length=MAX_RECIPE_NAME_LENGTH,
        verbose_name='Название',
    )
    text = models.TextField(
        verbose_name='Описание',
    )
    image = models.ImageField(
        verbose_name='Картинка блюда',
        upload_to='images',
    )
    cooking_time = models.PositiveSmallIntegerField(
        verbose_name='Время готовки (мин)',
        validators=(
            MinValueValidator(
                MIN_COOKING_TIME,
                message=(
                    f'Время готовки не может быть меньше '
                    f'{MIN_COOKING_TIME} мин.'
                ),
            ),
        ),
    )
    pub_date = models.DateTimeField(
        verbose_name='Дата добавления',
        default=timezone.now,
        db_index=True,
    )
    ingredients = models.ManyToManyField(
        Ingredient,
        verbose_name='Ингредиенты',
        through='RecipeIngredient',
    )
    tags = models.ManyToManyField(
        Tag,
        verbose_name='Тэги',
        related_name='recipes',
    )
    short_link = models.CharField(
        verbose_name='Короткая ссылка',
        max_length=SHORT_LINK_MAX_LENGTH,
        blank=True,
    )

    class Meta:
        """Настройки модели."""

        default_related_name = 'recipes'
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
        ordering = ('-pub_date',)
        constraints = [
            models.UniqueConstraint(
                fields=('short_link',),
                condition=~models.Q(short_link=''),
                name='unique_non_empty_short_link',
            ),
        ]

    def __str__(self):
        """Строковое представление объекта."""
        return self.name[:MAX_VIEW_LENGTH]


class RecipeIngredient(models.Model):
    """Количество ингредиента в рецепте."""

    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name='Рецепт',
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        verbose_name='Ингредиент',
    )
    amount = models.PositiveSmallIntegerField(
        verbose_name='Количество',
        validators=[MinValueValidator(MIN_INGREDIENT_COUNT)],
    )

    class Meta:
        """Настройки модели."""

        default_related_name = 'recipe_ingredients'
        verbose_name = 'Ингредиент рецепта'
        verbose_name_plural = 'Ингредиенты рецепта'
        constraints = [
            models.UniqueConstraint(
                fields=('ingredient', 'recipe'),
                name='unique_recipe_ingredient',
            )
        ]

    def __str__(self):
        """Строковое представление объекта."""
        return (
            f'Ингредиент {self.ingredient.name[:MAX_VIEW_LENGTH]} '
            f'в рецепте {self.recipe.name[:MAX_VIEW_LENGTH]}'
        )


class BaseFavoriteShoppingCart(models.Model):
    """Базовая модель для избранного и списка покупок."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Пользователь',
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        verbose_name='Рецепт',
    )
    pub_date = models.DateTimeField(
        verbose_name='Дата добавления',
        default=timezone.now,
        db_index=True,
    )

    class Meta:
        """Настройки модели."""

        abstract = True
        ordering = ('-pub_date',)


class Favorite(BaseFavoriteShoppingCart):
    """Избранный рецепт."""

    class Meta:
        """Настройки модели."""

        default_related_name = 'favorites'
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранные'
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'recipe'),
                name='unique_user_favorite_recipe',
            )
        ]

    def __str__(self):
        """Строковое представление объекта."""
        return f'Избранный рецепт: {self.recipe} у пользователя {self.user}'


class ShoppingCart(BaseFavoriteShoppingCart):
    """Рецепт в списке покупок."""

    class Meta:
        """Настройки модели."""

        default_related_name = 'cart_recipes'
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзина'
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'recipe'),
                name='unique_user_cart_recipe',
            )
        ]

    def __str__(self):
        """Строковое представление объекта."""
        return f'Рецепт: {self.recipe} в корзине пользователя {self.user}'
