"""Фильтры для рецептов и ингредиентов."""

from django_filters import rest_framework as filters
from django_filters.rest_framework import FilterSet

from recipes.models import Ingredient, Recipe


class RecipeFilter(filters.FilterSet):
    """Фильтры для рецептов."""

    tags = filters.AllValuesMultipleFilter(field_name='tags__slug')
    is_favorited = filters.BooleanFilter(method='filter_is_favorited')
    is_in_shopping_cart = filters.BooleanFilter(
        method='filter_is_in_shopping_cart'
    )

    class Meta:
        """Параметры фильтрации рецептов."""

        model = Recipe
        fields = ('author', 'tags', 'is_favorited', 'is_in_shopping_cart')

    def filter_is_favorited(self, queryset, name, value):
        """Вернуть рецепты, добавленные в избранное указанным пользователем."""
        if not value:
            return queryset
        user = getattr(self.request, 'user', None)
        if not user or user.is_anonymous:
            return queryset.none()
        return queryset.filter(favorites__user=user)

    def filter_is_in_shopping_cart(self, queryset, name, value):
        """Вернуть рецепты, находящиеся в списке покупок пользователя."""
        if not value:
            return queryset
        user = getattr(self.request, 'user', None)
        if not user or user.is_anonymous:
            return queryset.none()
        return queryset.filter(cart_recipes__user=user)


class IngredientFilter(FilterSet):
    """Фильтр для ингредиентов по началу имени."""

    name = filters.CharFilter(lookup_expr='istartswith')

    class Meta:
        """Настройки фильтра для ингредиентов."""

        model = Ingredient
        fields = ('name',)
