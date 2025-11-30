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
        if request is None:
            return False

        user = getattr(request, 'user', None)
        # Для анонимного пользователя всегда False
        if user is None or not user.is_authenticated:
            return False

        return author.followers.filter(user=user).exists()


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

    def _get_user(self):
        request = self.context.get('request')
        if request is None:
            return None
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return None
        return user

    def get_is_favorited(self, obj):
        """Проверить, находится ли рецепт в избранном."""
        user = self._get_user()
        if user is None:
            return False
        return obj.favorites.filter(user=user).exists()

    def get_is_in_shopping_cart(self, obj):
        """Проверить, находится ли рецепт в списке покупок."""
        user = self._get_user()
        if user is None:
            return False
        return obj.cart_recipes.filter(user=user).exists()


class MiniRecipeSerializer(serializers.ModelSerializer):
    """Короткий рецепт."""

    image = Base64ImageField()

    class Meta:
        """Поля короткого рецепта."""

        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class FavoriteSerializer(serializers.ModelSerializer):
    """Добавление в избранное / корзину (базовый сериализатор)."""

    error_message = 'Рецепт уже в избранном.'
    not_found_message = 'Рецепт отсутствует в избранном.'

    class Meta:
        """Поля избранного."""
        model = Favorite
        # Тело запроса пустое, всё берём из контекста.
        fields = ()

    def validate(self, attrs):
        """Валидация добавления и удаления (общая для избранного/корзины)."""
        request = self.context['request']
        recipe = self.context['recipe']
        model = self.Meta.model

        exists = model.objects.filter(
            user=request.user,
            recipe=recipe,
        ).exists()

        if request.method == 'POST' and exists:
            raise serializers.ValidationError(self.error_message)

        if request.method == 'DELETE' and not exists:
            raise serializers.ValidationError(self.not_found_message)

        return attrs

    def create(self, validated_data):
        """Создать запись (избранное или корзина)."""
        request = self.context['request']
        recipe = self.context['recipe']
        model = self.Meta.model
        return model.objects.create(
            user=request.user,
            recipe=recipe,
        )

    def to_representation(self, instance):
        """Вернуть мини-рецепт для ответа."""
        request = self.context.get('request')
        return MiniRecipeSerializer(
            instance.recipe,
            context={'request': request},
        ).data


class ShoppingCartSerializer(FavoriteSerializer):
    """Добавление в корзину / удаление из корзины."""

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
        """Валидация создания и удаления подписки."""
        request = self.context['request']
        author = self.context.get('author')

        if author is None:
            raise serializers.ValidationError('Автор не передан в контексте.')

        exists = author.followers.filter(user=request.user).exists()

        # Нельзя подписаться на себя
        if request.method == 'POST':
            if request.user == author:
                raise serializers.ValidationError(
                    'Нельзя подписаться на себя.',
                )
            if exists:
                raise serializers.ValidationError('Подписка уже существует.')

        # Нет подписки → нечего удалять
        if request.method == 'DELETE' and not exists:
            raise serializers.ValidationError('Подписки не существует.')

        attrs['author'] = author
        return attrs

    def create(self, validated_data):
        """Создать подписку."""
        return Follow.objects.create(
            user=self.context['request'].user,
            author=validated_data['author'],
        )


class SubscriptionSerializer(serializers.ModelSerializer):
    """Чтение подписки."""

    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.IntegerField(
        source='recipes.count',
        read_only=True,
    )
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
                # Если recipes_limit некорректен,
                # просто отдаём все рецепты.
                pass

        return MiniRecipeSerializer(
            recipes_qs,
            many=True,
            context={'request': request},
        ).data
