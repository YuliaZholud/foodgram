"""Фильтры для рецептов и ингредиентов."""

from django_filters import rest_framework as filters
from django_filters.rest_framework import FilterSet

from recipes.models import Ingredient, Recipe


class RecipeFilter(filters.FilterSet):
    """Фильтры для рецептов."""

    # tags: список slug-тегов (?tags=breakfast&tags=lunch)
    tags = filters.AllValuesMultipleFilter(field_name='tags__slug')
    # author и так подхватится через Meta.fields → author=id автора
    is_favorited = filters.BooleanFilter(method='filter_is_favorited')
    is_in_shopping_cart = filters.BooleanFilter(
        method='filter_is_in_shopping_cart',
    )

    class Meta:
        """Параметры фильтрации рецептов."""

        model = Recipe
        # author не объявляем явно, он берётся из модели по pk,
        # но его нужно перечислить в fields:
        fields = ('author', 'tags', 'is_favorited', 'is_in_shopping_cart')

    def filter_is_favorited(self, queryset, name, value):
        """
        Вернуть рецепты, добавленные в избранное указанным пользователем.

        /api/recipes/?is_favorited=1 — только избранные рецепты.
        """
        if not value:
            return queryset

        user = getattr(self.request, 'user', None)
        if not user or user.is_anonymous:
            return queryset.none()

        # используем related_name='favorites' из модели Favorite
        return queryset.filter(favorites__user=user)

    def filter_is_in_shopping_cart(self, queryset, name, value):
        """
        Вернуть рецепты, которые есть в списке покупок пользователя.

        /api/recipes/?is_in_shopping_cart=1 — только рецепты в корзине.
        """
        if not value:
            return queryset

        user = getattr(self.request, 'user', None)
        if not user or user.is_anonymous:
            return queryset.none()

        # related_name='cart_recipes' из модели ShoppingCart
        return queryset.filter(cart_recipes__user=user)


class IngredientFilter(FilterSet):
    """Фильтр для ингредиентов по началу имени."""

    # /api/ingredients/?name=мо → вернёт «Морковь», «Молоко» и т.п.
    name = filters.CharFilter(lookup_expr='istartswith')

    class Meta:
        """Настройки фильтра для ингредиентов."""

        model = Ingredient
        fields = ('name',)
