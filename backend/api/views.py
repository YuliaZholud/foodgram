"""Вьюсеты API Foodgram."""

from api.filters import IngredientFilter, RecipeFilter
from api.permissions import IsAuthenticatedAuthorOrReadOnly
from api.serializers import (
    FavoriteSerializer,
    ShoppingCartSerializer,
    SubscriptionPostSerializer,
    SubscriptionSerializer,  # ← ЭТОГО НЕ ХВАТАЛО
    TagSerializer,
    IngredientSerializer,
    RecipePostSerializer,
    AvatarSerializer,
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

from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from users.models import Follow

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
        """Общий метод добавления или удаления (избранное / корзина)."""
        recipe = self.get_object()

        serializer = serializer_class(
            data={},
            context={'request': request, 'recipe': recipe},
        )
        serializer.is_valid(raise_exception=True)

        if request.method == 'POST':
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        # DELETE - запись уже провалидирована в serializer.validate()
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
            f'{item["name"]} ({item["measurement_unit"]}) — '
            f'{item["total_amount"]}'
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
    """Вьюсет пользователя (расширение Djosер)."""

    queryset = User.objects.all()
    serializer_class = UserPostSerializer
    pagination_class = Pagination

    def get_serializer_class(self):
        """Вернуть корректный сериализатор для действия.

        Для списка, деталей и /me используем свои сериализаторы,
        для остальных действий — стандартную логику Djoser.
        """
        if self.action in {'list', 'retrieve', 'me'}:
            return UserGetSerializer
        return super().get_serializer_class()

    @action(
        detail=False,
        methods=('get',),
        permission_classes=(permissions.IsAuthenticated,),
        url_path='me',
    )
    def me(self, request, *args, **kwargs):
        """Вернуть данные текущего пользователя."""
        return super().me(request, *args, **kwargs)

    @action(
        detail=False,
        methods=('put', 'delete'),
        permission_classes=(permissions.IsAuthenticated,),
        url_path='me/avatar',
    )
    def avatar(self, request, *args, **kwargs):
        """Создать или удалить аватар текущего пользователя."""
        user = request.user

        if request.method == 'DELETE':
            serializer = AvatarSerializer(
                user,
                data={'avatar': None},
                partial=True,
                context={'request': request},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = AvatarSerializer(
            user,
            data=request.data,
            partial=True,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        methods=('POST', 'DELETE'),
        detail=True,
        permission_classes=(permissions.IsAuthenticated,),
        url_path='subscribe',
    )
    def subscribe(self, request, id=None):
        """Подписаться или отписаться от пользователя."""
        author = self.get_object()

        if request.method == 'POST':
            serializer = SubscriptionPostSerializer(
                data={},
                context={'request': request, 'author': author},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            output = SubscriptionSerializer(
                author,
                context={'request': request},
            )
            return Response(output.data, status=status.HTTP_201_CREATED)

        SubscriptionPostSerializer(
            data={},
            context={'request': request, 'author': author},
        ).is_valid(raise_exception=True)
        Follow.objects.filter(user=request.user, author=author).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=('get',),
        permission_classes=(permissions.IsAuthenticated,),
        url_path='subscriptions',
    )
    def subscriptions(self, request):
        """Вернуть список авторов, на которых подписан текущий пользователь."""
        user = request.user
        authors = User.objects.filter(followers__user=user)
        pages = self.paginate_queryset(authors)
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
    """
    Редирект по короткой ссылке.

    Делаем переход на detail-страницу рецепта из API,
    чтобы использовать единый URL и права доступа.
    """
    recipe = get_object_or_404(Recipe, short_link=short_link_code)
    # basename у роутера: 'recipes' → имя маршрута 'recipes-detail'
    return redirect('api:recipes-detail', pk=recipe.pk)
