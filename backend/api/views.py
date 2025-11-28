"""Вьюсеты API Foodgram."""

from api.filters import IngredientFilter, RecipeFilter
from api.permissions import IsAuthenticatedAuthorOrReadOnly
from api.serializers import (
    FavoriteSerializer,
    ShoppingCartSerializer,
    SubscriptionPostSerializer,
    TagSerializer,
    IngredientSerializer,
    RecipePostSerializer,
    UserGetSerializer,
    UserPostSerializer,
)
from api.services import Pagination, ShortLink
from django.contrib.auth import get_user_model
from django.db.models import BooleanField, Exists, OuterRef, Sum, Value, F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet as DjoserUserViewSet
from recipes.constants import SHORT_LINK_MAX_POSTFIX
from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

User = get_user_model()


class RecipeViewSet(viewsets.ModelViewSet):
    """Работа с рецептами."""

    serializer_class = RecipePostSerializer
    pagination_class = Pagination
    permission_classes = (IsAuthenticatedAuthorOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter
    lookup_field = 'pk'

    def get_queryset(self):
        """Вернуть рецепты с аннотациями."""
        user = self.request.user
        qs = Recipe.objects.all()

        if user.is_authenticated:
            return qs.annotate(
                is_favorited=Exists(
                    Favorite.objects.filter(
                        user=user,
                        recipe=OuterRef('pk'),
                    )
                ),
                is_in_shopping_cart=Exists(
                    ShoppingCart.objects.filter(
                        user=user,
                        recipe=OuterRef('pk'),
                    )
                ),
            )

        return qs.annotate(
            is_favorited=Value(False, output_field=BooleanField()),
            is_in_shopping_cart=Value(False, output_field=BooleanField()),
        )

    def perform_create(self, serializer):
        """Создать рецепт с автором."""
        serializer.save(author=self.request.user)

    @action(
        url_path='get-link',
        detail=True,
        permission_classes=(AllowAny,),
    )
    def get_short_link(self, request, pk=None):
        """Получить короткую ссылку."""
        recipe = self.get_object()

        if recipe.short_link:
            url = reverse('short_link', args=(recipe.short_link,))
            return Response({'short-link': request.build_absolute_uri(url)})

        while True:
            code = ShortLink().create_short_link(SHORT_LINK_MAX_POSTFIX)
            if not Recipe.objects.filter(short_link=code).exists():
                break

        recipe.short_link = code
        recipe.save(update_fields=('short_link',))

        url = reverse('short_link', args=(code,))
        return Response({'short-link': request.build_absolute_uri(url)})

    @action(
        methods=('POST', 'DELETE'),
        url_path='favorite',
        detail=True,
        permission_classes=(IsAuthenticated,),
    )
    def favorite(self, request, pk=None):
        """Добавить или удалить избранное."""
        return self._add_or_remove(
            request,
            model=Favorite,
            serializer_class=FavoriteSerializer,
        )

    @action(
        methods=('POST', 'DELETE'),
        url_path='shopping_cart',
        detail=True,
        permission_classes=(IsAuthenticated,),
    )
    def shopping_cart(self, request, pk=None):
        """Добавить или удалить корзину."""
        return self._add_or_remove(
            request,
            model=ShoppingCart,
            serializer_class=ShoppingCartSerializer,
        )

    def _add_or_remove(self, request, model, serializer_class):
        """Общий метод добавления/удаления."""
        recipe = self.get_object()

        if request.method == 'POST':
            serializer = serializer_class(
                data={'user': request.user.pk, 'recipe': recipe.pk},
                context={'request': request},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        serializer_class.validate_delete(request.user, recipe)
        model.objects.filter(user=request.user, recipe=recipe).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        url_path='download_shopping_cart',
        detail=False,
        permission_classes=(IsAuthenticated,),
    )
    def download_shopping_cart(self, request):
        """Скачать список покупок."""
        items = (
            RecipeIngredient.objects.filter(
                recipe__cart_recipes__user=request.user,
            )
            .values(
                name=F('ingredient__name'),
                measurement_unit=F('ingredient__measurement_unit'),
            )
            .annotate(total_amount=Sum('amount'))
            .order_by('name')
        )

        lines = [
            f"{item['name']} ({item['measurement_unit']}) — "
            f"{item['total_amount']}"
            for item in items
        ]

        response = HttpResponse(
            '\n'.join(lines),
            content_type='text/plain; charset=utf-8',
        )
        response['Content-Disposition'] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response


class UserViewSet(DjoserUserViewSet):
    """Работа с пользователями."""

    queryset = User.objects.all()
    serializer_class = UserPostSerializer
    pagination_class = Pagination

    def get_serializer_class(self):
        """Выбрать сериализатор."""
        if self.action in {'list', 'retrieve', 'me'}:
            return UserGetSerializer
        return super().get_serializer_class()

    @action(
        methods=("GET",),
        url_path="subscriptions",
        permission_classes=(IsAuthenticated,),
        detail=False,
    )
    def subscriptions(self, request):
        """Возвратить список авторов, на которых подписан пользователь."""
        user = request.user
        queryset = user.follower.select_related("author")

        pages = self.paginate_queryset(queryset)
        serializer = SubscriptionSerializer(
            pages,
            many=True,
            context={'request': request},
        )
        return self.get_paginated_response(serializer.data)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """Теги."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    pagination_class = None


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """Ингредиенты."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter
    pagination_class = None


def redirect_to_recipe_detail(request, short_link_code):
    """Редирект по короткой ссылке."""
    recipe = get_object_or_404(Recipe, short_link=short_link_code)
    return redirect('api:recipe-detail', pk=recipe.id)
