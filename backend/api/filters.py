"""Фильтры для рецептов и ингредиентов."""

from django_filters.rest_framework import FilterSet, filters

from recipes.models import Ingredient, Recipe


class RecipeFilter(FilterSet):
    """Фильтры для рецептов."""

    is_favorited = filters.BooleanFilter(method='filter_is_favorited')
    is_in_shopping_cart = filters.BooleanFilter(
        method='filter_is_in_shopping_cart'
    )

    def filter_is_favorited(self, queryset, name, value):
        """Отфильтровать рецепты по наличию в избранном пользователя."""
        user = self.request.user
        if not value:
            return queryset
        if not user.is_authenticated:
            return queryset.none()
        return queryset.filter(favorites__user=user)

    def filter_is_in_shopping_cart(self, queryset, name, value):
        """Отфильтровать рецепты по наличию в списке покупок пользователя."""
        user = self.request.user
        if not value:
            return queryset
        if not user.is_authenticated:
            return queryset.none()
        return queryset.filter(cart_recipes__user=user)

    class Meta:
        """Настройки фильтра для рецептов."""

        model = Recipe
        fields = ('author', 'tags', 'is_favorited', 'is_in_shopping_cart')


class IngredientFilter(FilterSet):
    """Фильтр для ингредиентов по началу имени."""

    name = filters.CharFilter(lookup_expr='istartswith')

    class Meta:
        """Настройки фильтра для ингредиентов."""

        model = Ingredient
        fields = ('name',)
