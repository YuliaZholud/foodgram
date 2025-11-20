"""Фильтры для рецептов и ингредиентов."""

from django_filters.rest_framework import FilterSet, filters

from recipes.models import Ingredient, Recipe, Tag


class RecipeFilter(FilterSet):
    """Фильтры для рецептов."""

    is_favorited = filters.BooleanFilter(method='filter_is_favorited')
    is_in_shopping_cart = filters.BooleanFilter(
        method='filter_is_in_shopping_cart',
    )
    tags = filters.ModelMultipleChoiceFilter(
        queryset=Tag.objects.all(),
        field_name='tags__slug',
        to_field_name='slug',
    )

    class Meta:
        """Настройки фильтра для рецептов."""

        model = Recipe
        fields = ('author', 'tags', 'is_favorited', 'is_in_shopping_cart')

    def _get_user(self):
        """Вернуть текущего пользователя, если он аутентифицирован."""
        user = getattr(self.request, 'user', None)
        if user and user.is_authenticated:
            return user
        return None

    def filter_is_favorited(self, queryset, name, value):
        """Отфильтровать рецепты по наличию в избранном пользователя."""
        user = self._get_user()
        if value and user:
            return queryset.filter(user_favorite__user=user)
        return queryset

    def filter_is_in_shopping_cart(self, queryset, name, value):
        """Отфильтровать рецепты по наличию в списке покупок пользователя."""
        user = self._get_user()
        if value and user:
            return queryset.filter(cart_recipes__user=user)
        return queryset


class IngredientFilter(FilterSet):
    """Фильтр для ингредиентов по началу имени."""

    name = filters.CharFilter(lookup_expr='istartswith')

    class Meta:
        """Настройки фильтра для ингредиентов."""

        model = Ingredient
        fields = ('name',)
