"""Сериализаторы API Foodgram."""

from api.services import Base64ImageField
from django.contrib.auth import get_user_model
from recipes.models import (
    Favorite,
    Ingredient,
    Recipe,
    RecipeIngredient,
    ShoppingCart,
    Tag,
)
from rest_framework import serializers
from users.models import Follow

User = get_user_model()


class AvatarSerializer(serializers.ModelSerializer):
    """Сериализатор аватара."""

    avatar = Base64ImageField(allow_null=True, file_prefix='avatar')

    class Meta:
        """Поля аватара."""

        model = User
        fields = ('avatar',)


class UserPostSerializer(serializers.ModelSerializer):
    """Создание пользователя."""

    password = serializers.CharField(write_only=True)

    class Meta:
        """Поля пользователя при создании."""

        model = User
        fields = (
            'id',
            'email',
            'username',
            'first_name',
            'last_name',
            'password',
        )

    def create(self, validated_data):
        """Создать пользователя с хэшированным паролем."""
        return User.objects.create_user(**validated_data)


class UserGetSerializer(serializers.ModelSerializer):
    """Чтение данных пользователя."""

    avatar = Base64ImageField(allow_null=True, required=False)
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        """Поля пользователя для чтения."""

        model = User
        fields = (
            'id',
            'email',
            'username',
            'first_name',
            'last_name',
            'avatar',
            'is_subscribed',
        )

    def get_is_subscribed(self, author):
        """Проверить подписку."""
        request = self.context.get('request')
        if not request:
            return False
        return author.followers.filter(user_id=request.user.pk).exists()


class TagSerializer(serializers.ModelSerializer):
    """Сериализатор тега."""

    class Meta:
        """Поля тега."""

        model = Tag
        fields = ('id', 'name', 'slug')


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор ингредиента."""

    class Meta:
        """Поля ингредиента."""

        model = Ingredient
        fields = '__all__'


class RecipeIngredientPostSerializer(serializers.ModelSerializer):
    """Ингредиент при создании рецепта."""

    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(),
        source='ingredient',
    )

    class Meta:
        """Поля ингредиента в запросе."""

        model = RecipeIngredient
        fields = ('id', 'amount')

    def validate_amount(self, value):
        """Проверить количество."""
        if value <= 0:
            raise serializers.ValidationError(
                'Количество должно быть больше нуля.',
            )
        return value


class RecipeIngredientGetSerializer(serializers.ModelSerializer):
    """Ингредиент рецепта для чтения."""

    id = serializers.IntegerField(source='ingredient.id')
    name = serializers.CharField(source='ingredient.name')
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit',
    )

    class Meta:
        """Поля ингредиента для чтения."""

        model = RecipeIngredient
        fields = (
            'id',
            'name',
            'measurement_unit',
            'amount',
        )


class RecipePostSerializer(serializers.ModelSerializer):
    """Создание и изменение рецепта."""

    author = serializers.SlugRelatedField(
        slug_field='username',
        read_only=True,
    )
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True,
    )
    ingredients = RecipeIngredientPostSerializer(
        many=True,
        source='recipe_ingredients',
    )
    image = Base64ImageField(required=True, file_prefix='recipe')

    class Meta:
        """Поля рецепта при создании."""

        model = Recipe
        fields = (
            'author',
            'ingredients',
            'tags',
            'image',
            'name',
            'text',
            'cooking_time',
        )

    def validate(self, value):
        """Проверить ингредиенты и теги."""
        ingredients = value.get('recipe_ingredients')
        tags = value.get('tags')

        if not ingredients:
            raise serializers.ValidationError(
                'Отсутствуют ингредиенты.',
            )
        if not tags:
            raise serializers.ValidationError('Отсутствуют теги.')

        ingredient_ids = [
            item.get('ingredient').id for item in ingredients
        ]
        if len(set(ingredient_ids)) != len(ingredients):
            raise serializers.ValidationError(
                'Ингредиенты должны быть уникальными.',
            )

        if len(set(tags)) != len(tags):
            raise serializers.ValidationError('Теги должны быть уникальными.')

        return value

    def _update_tags_and_ingredients(self, recipe, tags, ingredients):
        """Обновить теги и ингредиенты."""
        recipe.tags.set(tags)
        recipe.recipe_ingredients.all().delete()
        RecipeIngredient.objects.bulk_create(
            RecipeIngredient(recipe=recipe, **ingredient)
            for ingredient in ingredients
        )

    def create(self, validated_data):
        """Создать рецепт."""
        tags = validated_data.pop('tags')
        ingredients = validated_data.pop('recipe_ingredients')
        validated_data['author'] = self.context['request'].user

        recipe = Recipe.objects.create(**validated_data)
        self._update_tags_and_ingredients(recipe, tags, ingredients)
        return recipe

    def update(self, instance, validated_data):
        """Обновить рецепт."""
        tags = validated_data.pop('tags')
        ingredients = validated_data.pop('recipe_ingredients')

        self._update_tags_and_ingredients(instance, tags, ingredients)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        """Вернуть данные для чтения рецепта."""
        return RecipeGetSerializer(
            instance,
            context=self.context,
        ).data


class RecipeGetSerializer(serializers.ModelSerializer):
    """Чтение рецепта."""

    author = UserGetSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    ingredients = RecipeIngredientGetSerializer(
        source='recipe_ingredients',
        many=True,
        read_only=True,
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        """Поля рецепта для чтения."""

        model = Recipe
        fields = (
            'id',
            'tags',
            'author',
            'ingredients',
            'is_favorited',
            'is_in_shopping_cart',
            'name',
            'image',
            'text',
            'cooking_time',
        )

    def _check(self, obj, model):
        """Проверить статус рецепта."""
        request = self.context.get('request')
        if not request:
            return False
        return model.objects.filter(
            recipe_id=obj.pk,
            user_id=request.user.pk,
        ).exists()

    def get_is_favorited(self, obj):
        """Проверить, находится ли рецепт в избранном."""
        return self._check(obj, Favorite)

    def get_is_in_shopping_cart(self, obj):
        """Проверить, находится ли рецепт в списке покупок."""
        return self._check(obj, ShoppingCart)


class MiniRecipeSerializer(serializers.ModelSerializer):
    """Короткий рецепт."""

    image = Base64ImageField()

    class Meta:
        """Поля короткого рецепта."""

        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class FavoriteSerializer(serializers.ModelSerializer):
    """Добавление в избранное."""

    error_message = 'Рецепт уже в избранном.'
    not_found_message = 'Рецепт отсутствует в избранном.'

    class Meta:
        """Поля избранного."""

        model = Favorite
        fields = ('user', 'recipe')

    def validate(self, data):
        """Проверить существование записи."""
        if Favorite.objects.filter(**data).exists():
            raise serializers.ValidationError(self.error_message)
        return data

    @classmethod
    def validate_delete(cls, user, recipe):
        """Проверить возможность удаления из избранного."""
        if not Favorite.objects.filter(user=user, recipe=recipe).exists():
            raise serializers.ValidationError(cls.not_found_message)

    def to_representation(self, instance):
        """Вернуть мини-рецепт для ответа."""
        return MiniRecipeSerializer(
            instance.recipe,
            context=self.context,
        ).data


class ShoppingCartSerializer(FavoriteSerializer):
    """Добавление в корзину."""

    error_message = 'Рецепт уже в корзине.'
    not_found_message = 'Рецепта нет в корзине.'

    class Meta(FavoriteSerializer.Meta):
        """Поля корзины."""

        model = ShoppingCart


class SubscriptionPostSerializer(serializers.ModelSerializer):
    """Создание подписки."""

    class Meta:
        """Поля подписки при записи."""

        model = Follow
        fields = ()

    def validate(self, attrs):
        """Проверить возможность подписки."""
        request = self.context['request']
        author = self.context['author']

        if request.user == author:
            raise serializers.ValidationError(
                'Нельзя подписаться на себя.',
            )
        if author.followers.filter(user=request.user).exists():
            raise serializers.ValidationError('Подписка уже существует.')
        attrs['author'] = author
        return attrs

    def create(self, validated_data):
        """Создать подписку."""
        return Follow.objects.create(
            user=self.context['request'].user,
            author=validated_data['author'],
        )

    @classmethod
    def validate_delete(cls, *, user, author):
        """Проверить возможность удаления подписки."""
        if not author.followers.filter(user=user).exists():
            raise serializers.ValidationError('Подписки не существует.')


class SubscriptionGetSerializer(serializers.ModelSerializer):
    """Чтение подписки."""

    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(default=0)
    is_subscribed = serializers.BooleanField(default=True)
    avatar = Base64ImageField(allow_null=True, required=False)

    class Meta:
        """Поля подписки при чтении."""

        model = User
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
            'recipes',
            'recipes_count',
            'avatar',
        )

    def get_recipes(self, obj):
        """Получить рецепты автора."""
        request = self.context.get('request')
        qs = obj.recipes.all().order_by('-id')

        limit = request.query_params.get('recipes_limit') if request else None
        if limit and limit.isdigit():
            qs = qs[: int(limit)]

        return MiniRecipeSerializer(
            qs,
            many=True,
            context=self.context,
        ).data


class SubscriptionSerializer(UserGetSerializer):
    """Автор, на которого подписан пользователь (список подписок)."""

    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(
        source='recipes.count',
        read_only=True,
    )

    class Meta(UserGetSerializer.Meta):
        """Поля списка подписок."""
        fields = UserGetSerializer.Meta.fields + ('recipes', 'recipes_count')

    def get_recipes(self, obj):
        """Вернуть рецепты автора с учётом recipes_limit."""
        request = self.context.get('request')
        recipes_qs = obj.recipes.all().order_by('-id')

        recipes_limit = None
        if request is not None:
            recipes_limit = request.query_params.get('recipes_limit')

        if recipes_limit is not None:
            try:
                limit = int(recipes_limit)
                if limit > 0:
                    recipes_qs = recipes_qs[:limit]
            except (TypeError, ValueError):
                # если в recipes_limit пришла ерунда — просто отдаём все рецепты
                pass

        return MiniRecipeSerializer(
            recipes_qs,
            many=True,
            context={'request': request},
        ).data
