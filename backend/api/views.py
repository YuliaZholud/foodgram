"""Вьюсеты API: рецепты, пользователи, теги, ингредиенты и короткие ссылки."""

from api.filters import IngredientFilter, RecipeFilter
from api.helpers import Pagination, ShortLink
from api.permissions import OwnerOrReadOnly
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
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet as DjoserUserViewSet
from recipes.constants import SHORT_LINK_MAX_POSTFIX, URL
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
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
    IsAuthenticatedOrReadOnly,
)
from rest_framework.response import Response
from users.models import Follow

User = get_user_model()


class RecipeViewSet(viewsets.ModelViewSet):
    """Вьюсет рецепта и всего, что с ним связано."""

    queryset = Recipe.objects.all()
    serializer_class = RecipePostSerializer
    pagination_class = Pagination
    permission_classes = (IsAuthenticatedOrReadOnly, OwnerOrReadOnly)
    filter_backends = (DjangoFilterBackend,)
    filterset_class = RecipeFilter

    def perform_create(self, serializer):
        """Сохранить рецепт с указанием текущего пользователя как автора."""
        serializer.save(author=self.request.user)

    @action(
        methods=['GET'],
        url_path='get-link',
        detail=True,
        permission_classes=(AllowAny,),
    )
    def get_short_link(self, request, pk=None):
        """Получить или сгенерировать короткую ссылку на рецепт."""
        recipe = get_object_or_404(Recipe, id=pk)
        if recipe.short_link:
            return Response(
                {'short-link': URL + recipe.short_link},
                status=status.HTTP_200_OK,
            )
        while True:
            short_code = ShortLink().create_short_link(
                SHORT_LINK_MAX_POSTFIX,
            )
            if not Recipe.objects.filter(short_link=short_code).exists():
                break
        recipe.short_link = short_code
        recipe.save(update_fields=['short_link'])
        return Response(
            {'short-link': URL + short_code},
            status=status.HTTP_200_OK,
        )

    @action(
        methods=['POST', 'DELETE'],
        url_path='favorite',
        detail=True,
        permission_classes=(IsAuthenticated,),
    )
    def favorite(self, request, pk=None):
        """Добавить или удалить рецепт из избранного."""
        return self._add_or_remove_recipe(
            request=request,
            pk=pk,
            model=Favorite,
            serializer_class=FavoriteSerializer,
            not_found_message='Рецепт не найден в избранном',
        )

    @action(
        methods=['POST', 'DELETE'],
        url_path='shopping_cart',
        detail=True,
        permission_classes=(IsAuthenticated,),
    )
    def shopping_cart(self, request, pk=None):
        """Добавить или удалить рецепт из списка покупок."""
        return self._add_or_remove_recipe(
            request=request,
            pk=pk,
            model=ShoppingCart,
            serializer_class=ShoppingCartSerializer,
            not_found_message='Рецепт не найден в списке покупок',
        )

    def _add_or_remove_recipe(
            self,
            request,
            pk,
            model,
            serializer_class,
            not_found_message,
    ):
        """
        Общий обработчик добавления и удаления рецепта.

        Работает как для избранного, так и для списка покупок.
        """
        recipe = get_object_or_404(Recipe, id=pk)

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
            return Response(
                {'error': not_found_message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        methods=['GET'],
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
                'ingredient__name',
                'ingredient__measurement_unit',
            )
            .annotate(total_amount=Sum('amount'))
            .order_by('ingredient__name')
        )

        lines = [
            f"{item['ingredient__name']} "
            f"({item['ingredient__measurement_unit']}) — "
            f"{item['total_amount']}"
            for item in ingredients_qs
        ]
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
        """Вернуть сериализатор в зависимости от выполняемого действия."""
        if self.action in ('list', 'retrieve', 'me'):
            return UserGetSerializer
        return UserPostSerializer

    @action(
        methods=['GET'],
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
        methods=['PUT', 'DELETE'],
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
        methods=['POST', 'DELETE'],
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

        deleted, _ = Follow.objects.filter(
            user=user,
            author=author,
        ).delete()
        if deleted == 0:
            return Response(
                {'error': 'Подписки не существует'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        methods=['GET'],
        url_path='subscriptions',
        permission_classes=(IsAuthenticated,),
        detail=False,
    )
    def subscriptions(self, request):
        """Список авторов, на которых подписан пользователь."""
        user = request.user
        # авторы, на которых подписан пользователь
        authors = User.objects.filter(
            following__user=user,
        ).distinct()
        page = self.paginate_queryset(authors)
        serializer = SubscriptionSerializer(
            page if page is not None else authors,
            many=True,
            context={'request': request},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    """Вьюсет тэгов."""

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    pagination_class = None
    permission_classes = (AllowAny,)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """Вьюсет ингредиентов."""

    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = IngredientFilter
    pagination_class = None
    permission_classes = (AllowAny,)


def redirect_to_recipe_detail(request, short_link_code):
    """Редирект с короткой ссылки на detail-страницу рецепта."""
    recipe = get_object_or_404(Recipe, short_link=short_link_code)
    return redirect('api:recipe-detail', pk=recipe.id)
