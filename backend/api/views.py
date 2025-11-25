"""Вьюсеты API: рецепты, пользователи, теги, ингредиенты и короткие ссылки."""

from api.filters import IngredientFilter, RecipeFilter
from api.permissions import IsAuthenticatedAuthorOrReadOnly
from api.serializers import (
    FavoriteSerializer,
    ShoppingCartSerializer,
    SubscriptionSerializer,
    TagSerializer,
    IngredientSerializer,
    RecipePostSerializer,
    AvatarSerializer,
    UserGetSerializer,
    UserPostSerializer,
    SubscriptionPostSerializer,
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
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
)
from rest_framework.response import Response
from users.models import Follow

User = get_user_model()


class RecipeViewSet(viewsets.ModelViewSet):
    """Вьюсет рецепта и всего, что с ним связано."""

    queryset = Recipe.objects.all()
    serializer_class = RecipePostSerializer
    pagination_class = Pagination
    permission_classes = (IsAuthenticatedAuthorOrReadOnly,)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def get_queryset(self):
        """Возвращает queryset с аннотациями для фильтров."""
        user = self.request.user
        base_qs = Recipe.objects.all()

        if user.is_authenticated:
            return base_qs.annotate(
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

        return base_qs.annotate(
            is_favorited=Value(False, output_field=BooleanField()),
            is_in_shopping_cart=Value(False, output_field=BooleanField()),
        )

    def perform_create(self, serializer):
        """Сохранить рецепт с указанием текущего пользователя как автора."""
        serializer.save(author=self.request.user)

    @action(
        url_path='get-link',
        detail=True,
        permission_classes=(AllowAny,),
    )
    def get_short_link(self, request, pk=None):
        """Получить или сгенерировать короткую ссылку на рецепт."""
        recipe = get_object_or_404(Recipe, id=pk)

        if recipe.short_link:
            short_url = request.build_absolute_uri(
                reverse('short_link', args=(recipe.short_link,)),
            )
            return Response({'short-link': short_url})

        while True:
            short_code = ShortLink().create_short_link(
                SHORT_LINK_MAX_POSTFIX,
            )
            if not Recipe.objects.filter(short_link=short_code).exists():
                break

        recipe.short_link = short_code
        recipe.save(update_fields=['short_link'])

        short_url = request.build_absolute_uri(
            reverse('short_link', args=(short_code,)),
        )
        return Response({'short-link': short_url})

    @action(
        methods=('POST', 'DELETE'),
        url_path='favorite',
        detail=True,
        permission_classes=(IsAuthenticated,),
    )
    def favorite(self, request, pk=None):
        """Добавить или удалить рецепт из избранного."""
        return self._add_or_remove_recipe(
            request=request,
            model=Favorite,
            serializer_class=FavoriteSerializer,
            not_found_message='Рецепт не найден в избранном',
        )

    @action(
        methods=('POST', 'DELETE'),
        url_path='shopping_cart',
        detail=True,
        permission_classes=(IsAuthenticated,),
    )
    def shopping_cart(self, request, pk=None):
        """Добавить или удалить рецепт из списка покупок."""
        return self._add_or_remove_recipe(
            request=request,
            model=ShoppingCart,
            serializer_class=ShoppingCartSerializer,
            not_found_message='Рецепт не найден в списке покупок',
        )

    def _add_or_remove_recipe(
            self,
            request,
            model,
            serializer_class,
            not_found_message,
    ):
        """
        Общий обработчик добавления и удаления рецепта.

        Работает как для избранного, так и для списка покупок.
        """
        recipe = self.get_object()

        if request.method == 'POST':
            serializer = serializer_class(
                data={'recipe': recipe.id, 'user': request.user.id},
                context={'request': request},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        qs = model.objects.filter(user=request.user, recipe=recipe)
        if not qs.exists():
            raise ValidationError(not_found_message)

        qs.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        url_path='download_shopping_cart',
        detail=False,
        permission_classes=(IsAuthenticated,),
    )
    def download_shopping_cart(self, request):
        """Скачать список покупок (.txt) с суммированными ингредиентами."""
        ingredients_qs = (
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

        lines = []
        for item in ingredients_qs:
            try:
                name = item['name']
                measurement_unit = item['measurement_unit']
                total_amount = item['total_amount']
            except KeyError as error:
                raise ValidationError(
                    f'Ошибка формирования списка покупок: отсутствует поле {error}'
                ) from error

            lines.append(
                f'{name} ({measurement_unit}) — {total_amount}',
            )

        content = '\n'.join(lines)
        response = HttpResponse(
            content,
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
        """
        Использовать наши сериализаторы для списка/деталей,
        а для остальных действий - логику Djoser.
        """
        if self.action in {'list', 'retrieve', 'me'}:
            return UserGetSerializer
        return super().get_serializer_class()

    @action(
        url_path='me',
        permission_classes=(IsAuthenticated,),
        detail=False,
    )
    def me(self, request):
        """Вернуть данные текущего пользователя."""
        serializer = UserGetSerializer(
            request.user,
            context={'request': request},
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        methods=('PUT', 'DELETE'),
        url_path='me/avatar',
        permission_classes=(IsAuthenticated,),
        detail=False,
    )
    def user_avatar(self, request):
        """Обновить или удалить аватар текущего пользователя."""
        user = request.user
        if request.method == 'PUT':
            serializer = AvatarSerializer(
                user,
                data=request.data,
                context={'request': request},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        user.avatar.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        methods=('POST', 'DELETE'),
        url_path='subscribe',
        permission_classes=(IsAuthenticated,),
        detail=True,
    )
    def subscribe(self, request, id=None):
        """Подписаться на автора или отписаться от него."""
        user = request.user
        author = get_object_or_404(User, pk=id)

        if request.method == 'POST':
            serializer = SubscriptionPostSerializer(
                data={'author': author.id},
                context={'request': request},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        deleted, _ = author.followers.filter(user=user).delete()
        if deleted == 0:
            return Response(
                {'error': 'Подписки не существует'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        url_path='subscriptions',
        permission_classes=(IsAuthenticated,),
        detail=False,
    )
    def subscriptions(self, request):
        """Список авторов, на которых подписан пользователь."""
        user = self.request.user
        authors = User.objects.filter(
            followers__user=user,
        ).distinct()
        page = self.paginate_queryset(authors)
        context = self.get_serializer_context()
        serializer = SubscriptionSerializer(
            page if page is not None else authors,
            many=True,
            context=context,
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """Вьюсет тэгов."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    pagination_class = None


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """Вьюсет ингредиентов."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter
    pagination_class = None


def redirect_to_recipe_detail(request, short_link_code):
    """Редирект с короткой ссылки на detail-страницу рецепта."""
    recipe = get_object_or_404(Recipe, short_link=short_link_code)
    return redirect('api:recipe-detail', pk=recipe.id)
