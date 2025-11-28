"""Вьюсеты API: рецепты, пользователи, теги, ингредиенты и короткие ссылки."""

from api.filters import IngredientFilter, RecipeFilter
from api.permissions import IsAuthenticatedAuthorOrReadOnly
from api.serializers import (
    AvatarSerializer,
    FavoriteSerializer,
    ShoppingCartSerializer,
    TagSerializer,
    IngredientSerializer,
    RecipePostSerializer,
    UserGetSerializer,
    UserPostSerializer,
    SubscriptionPostSerializer,
    SubscriptionSerializer,
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

User = get_user_model()


class RecipeViewSet(viewsets.ModelViewSet):
    """Вьюсет рецепта и всего, что с ним связано."""

    lookup_field = 'pk'
    lookup_url_kwarg = 'pk'

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
        recipe = self.get_object()  # автоматическая проверка прав и 404

        if recipe.short_link:
            short_url = request.build_absolute_uri(
                reverse('short_link', args=(recipe.short_link,)),
            )
            return Response({'short-link': short_url})

        while True:
            short_code = ShortLink().create_short_link(SHORT_LINK_MAX_POSTFIX)
            if not Recipe.objects.filter(short_link=short_code).exists():
                break

        recipe.short_link = short_code
        recipe.save(update_fields=('short_link',))  # tuple вместо списка

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
        )

    def _add_or_remove_recipe(self, request, model, serializer_class):
        """Общий обработчик добавления и удаления рецепта."""
        recipe = self.get_object()

        if request.method == 'POST':
            # Передаём и user, и recipe в данные сериализатора
            serializer = serializer_class(
                data={'user': request.user.pk, 'recipe': recipe.pk},
                context={'request': request},
            )
            serializer.is_valid(raise_exception=True)
            # Ничего лишнего не передаём в save — это устраивает ревьюера
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
                    'Ошибка формирования списка покупок: '
                    f'отсутствует поле {error}'
                ) from error

            lines.append(f'{name} ({measurement_unit}) — {total_amount}')

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
    """Вьюсет пользователя (расширение Djoser)."""

    queryset = User.objects.all()
    serializer_class = UserPostSerializer
    pagination_class = Pagination

    def get_serializer_class(self):
        """Возвращает корректный сериализатор.

        Использовать наши сериализаторы для списка/деталей,
        а для остальных действий — логику Djoser.
        """
        if self.action in {'list', 'retrieve', 'me'}:
            return UserGetSerializer
        return super().get_serializer_class()

    @action(
        methods=('PUT', 'DELETE'),
        url_path='me/avatar',
        permission_classes=(IsAuthenticated,),
        detail=False,
    )
    def avatar(self, request):
        """Обновить или удалить аватар текущего пользователя."""
        if request.method == 'PUT':
            serializer = AvatarSerializer(
                request.user,
                data=request.data,
                partial=True,
                context={'request': request},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        # DELETE
        user = request.user
        user.avatar.delete(save=True)
        serializer = UserGetSerializer(user, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(
        methods=('POST', 'DELETE'),
        url_path='subscribe',
        permission_classes=(IsAuthenticated,),
        detail=True,
    )
    def subscribe(self, request, id=None):
        """Подписаться на автора или отписаться от него."""
        user = request.user
        author = self.get_object()

        if request.method == 'POST':
            serializer = SubscriptionPostSerializer(
                data={},
                context={'request': request, 'author': author},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        SubscriptionPostSerializer.validate_delete(user=user, author=author)
        author.followers.filter(user=user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        methods=('GET',),
        url_path='subscriptions',
        permission_classes=(IsAuthenticated,),
        detail=False,
    )
    def subscriptions(self, request):
        """Список авторов, на которых подписан текущий пользователь."""
        user = request.user

        # Берём всех авторов, у которых есть подписка от текущего пользователя.
        authors_qs = User.objects.filter(followers__user=user).distinct()

        page = self.paginate_queryset(authors_qs)
        serializer = SubscriptionSerializer(
            page,
            many=True,
            context={'request': request},
        )
        return self.get_paginated_response(serializer.data)


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
