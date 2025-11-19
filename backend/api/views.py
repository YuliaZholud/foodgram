from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.http import HttpResponse
from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    ShoppingCart,
    Tag,
    IngredientInRecipe,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from users.models import Subscription

from .serializers import (
    IngredientSerializer,
    TagSerializer,
    UserSerializer,
    RecipeReadSerializer,
    SubscriptionSerializer,
    RecipeWriteSerializer,
)

User = get_user_model()


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all().order_by('id')
    serializer_class = UserSerializer
    permission_classes = (AllowAny,)

    @action(
        detail=False,
        methods=('get',),
        permission_classes=(IsAuthenticated,),
    )
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=('get',),
        permission_classes=(IsAuthenticated,),
    )
    def subscriptions(self, request):
        authors = User.objects.filter(
            subscribers__user=request.user
        ).order_by('id').distinct()

        page = self.paginate_queryset(authors)
        serializer = SubscriptionSerializer(
            page if page is not None else authors,
            many=True,
            context={'request': request},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=('post',),
        permission_classes=(IsAuthenticated,),
    )
    def subscribe(self, request, pk=None):
        user = request.user
        author = self.get_object()

        if user == author:
            return Response(
                {'errors': 'Нельзя подписаться на самого себя.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        obj, created = Subscription.objects.get_or_create(
            user=user,
            author=author,
        )
        if not created:
            return Response(
                {'errors': 'Подписка уже существует.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SubscriptionSerializer(
            author,
            context={'request': request},
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @subscribe.mapping.delete
    def delete_subscribe(self, request, pk=None):
        user = request.user
        author = self.get_object()

        deleted, _ = Subscription.objects.filter(
            user=user,
            author=author,
        ).delete()
        if deleted == 0:
            return Response(
                {'errors': 'Подписка не найдена.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class TagViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Tag.objects.all().order_by('id')
    serializer_class = TagSerializer
    permission_classes = (AllowAny,)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all().order_by('name')
    serializer_class = IngredientSerializer
    permission_classes = (AllowAny,)

    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__istartswith=name)
        return queryset


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all().order_by('-id').select_related(
        'author',
    ).prefetch_related(
        'tags',
        'ingredient_links__ingredient',
        'favorites',
        'shopping_cart',
    )
    serializer_class = RecipeReadSerializer
    permission_classes = (AllowAny,)

    def get_serializer_class(self):
        """Для чтения — RecipeReadSerializer, для записи — RecipeWriteSerializer."""
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return RecipeWriteSerializer
        return RecipeReadSerializer

    def get_permissions(self):
        """Права доступа:
        - чтение (list/retrieve) — всем;
        - создание/изменение/удаление, избранное, корзина, скачивание списка —
          только аутентифицированным.
        """
        if self.action in (
                'favorite',
                'delete_favorite',
                'shopping_cart',
                'delete_shopping_cart',
                'download_shopping_cart',
        ):
            return (IsAuthenticated(),)

        if self.request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return (IsAuthenticated(),)

        return (AllowAny(),)

    def perform_update(self, serializer):
        recipe = self.get_object()
        if self.request.user != recipe.author:
            raise PermissionDenied('Изменять рецепт может только автор.')
        serializer.save()

    def perform_destroy(self, instance):
        if self.request.user != instance.author:
            raise PermissionDenied('Удалять рецепт может только автор.')
        instance.delete()

    def _add_relation(self, model, user, recipe):
        obj, created = model.objects.get_or_create(user=user, recipe=recipe)
        if not created:
            return Response(
                {'errors': 'Запись уже существует.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = RecipeReadSerializer(
            recipe,
            context={'request': self.request},
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def _remove_relation(self, model, user, recipe):
        obj = model.objects.filter(user=user, recipe=recipe).first()
        if not obj:
            return Response(
                {'errors': 'Такой записи нет.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=('post',),
        permission_classes=(IsAuthenticated,),
    )
    def favorite(self, request, pk=None):
        recipe = self.get_object()
        return self._add_relation(Favorite, request.user, recipe)

    @favorite.mapping.delete
    def delete_favorite(self, request, pk=None):
        recipe = self.get_object()
        return self._remove_relation(Favorite, request.user, recipe)

    @action(
        detail=True,
        methods=('post',),
        permission_classes=(IsAuthenticated,),
    )
    def shopping_cart(self, request, pk=None):
        recipe = self.get_object()
        return self._add_relation(ShoppingCart, request.user, recipe)

    @shopping_cart.mapping.delete
    def delete_shopping_cart(self, request, pk=None):
        recipe = self.get_object()
        return self._remove_relation(ShoppingCart, request.user, recipe)

    @action(
        detail=False,
        methods=('get',),
        permission_classes=(IsAuthenticated,),
    )
    def download_shopping_cart(self, request):
        ingredients = IngredientInRecipe.objects.filter(
            recipe__shopping_cart__user=request.user
        ).values(
            'ingredient__name',
            'ingredient__measurement_unit',
        ).annotate(
            total_amount=Sum('amount')
        ).order_by('ingredient__name')

        if not ingredients:
            return Response(
                {'errors': 'Список покупок пуст.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lines = []
        for item in ingredients:
            line = (
                f"{item['ingredient__name']} "
                f"({item['ingredient__measurement_unit']}) — "
                f"{item['total_amount']}"
            )
            lines.append(line)

        content = '\n'.join(lines)
        response = HttpResponse(
            content,
            content_type='text/plain; charset=utf-8',
        )
        response['Content-Disposition'] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response
