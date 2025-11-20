"""Сериализаторы API для пользователей, рецептов и подписок."""

from api.helpers import Base64ImageField
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
    """Сериализатор аватара пользователя."""

    avatar = Base64ImageField(allow_null=True, file_prefix='avatar')

    class Meta:
        """Настройки сериализатора аватара."""

        model = User
        fields = ('avatar',)


class UserPostSerializer(serializers.ModelSerializer):
    """Сериализатор создания пользователя."""

    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        """Настройки сериализатора создания пользователя."""

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
    """Сериализатор информации о пользователе."""

    avatar = Base64ImageField(allow_null=True, required=False)
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        """Настройки сериализатора пользователя для чтения."""

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
        """Проверить, подписан ли текущий пользователь на автора."""
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        return Follow.objects.filter(user=user, author=author).exists()


class TagSerializer(serializers.ModelSerializer):
    """Сериализатор тега."""

    class Meta:
        """Настройки сериализатора тега."""

        model = Tag
        fields = ('id', 'name', 'slug')


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор ингредиента."""

    class Meta:
        """Настройки сериализатора ингредиента."""

        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class RecipeIngredientPostSerializer(serializers.ModelSerializer):
    """Ингредиент в запросе рецепта: {id, amount}."""

    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(),
        source='ingredient',
    )

    class Meta:
        """Настройки сериализатора ингредиента в запросе рецепта."""

        model = RecipeIngredient
        fields = ('id', 'amount')

    def validate_amount(self, value):
        """Проверить, что количество ингредиента указано и больше нуля."""
        if not value:
            raise serializers.ValidationError(
                'Количество не может быть пустым.'
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
        """Настройки сериализатора ингредиента рецепта для чтения."""

        model = RecipeIngredient
        fields = (
            'id',
            'name',
            'measurement_unit',
            'amount',
        )


class RecipePostSerializer(serializers.ModelSerializer):
    """Сериализатор создания и редактирования рецепта."""

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
        """Настройки сериализатора рецепта для записи."""

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
        read_only_fields = ('author',)

    def validate(self, value):
        """Выполнить общую валидацию полей рецепта."""
        ingredients = value.get('recipe_ingredients')
        tags = value.get('tags')

        if not ingredients:
            raise serializers.ValidationError(
                'Отсутствует обязательное поле ингредиенты.'
            )
        if not tags:
            raise serializers.ValidationError(
                'Отсутствует обязательное поле теги.'
            )

        ingredient_ids = [
            ingredient.get('ingredient').id for ingredient in ingredients
        ]
        if len(set(ingredient_ids)) != len(ingredients):
            raise serializers.ValidationError(
                'Ингредиенты должны быть уникальными.'
            )

        if len(set(tags)) != len(tags):
            raise serializers.ValidationError('Теги должны быть уникальными.')

        return value

    def _update_tags_and_ingredients(self, recipe, tags, ingredients):
        """Обновить теги и ингредиенты рецепта."""
        recipe.tags.set(tags)
        recipe.recipe_ingredients.all().delete()
        RecipeIngredient.objects.bulk_create(
            [
                RecipeIngredient(recipe=recipe, **ingredient)
                for ingredient in ingredients
            ]
        )

    def create(self, validated_data):
        """Создать рецепт и связанные теги и ингредиенты."""
        tags = validated_data.pop('tags')
        ingredients = validated_data.pop('recipe_ingredients')
        validated_data.pop('author', None)
        recipe = Recipe.objects.create(
            author=self.context['request'].user,
            **validated_data,
        )
        self._update_tags_and_ingredients(recipe, tags, ingredients)
        return recipe

    def update(self, instance, validated_data):
        """Обновить рецепт и связанные теги и ингредиенты."""
        tags = validated_data.pop('tags')
        ingredients = validated_data.pop('recipe_ingredients')
        self._update_tags_and_ingredients(instance, tags, ingredients)
        return super().update(instance, validated_data)

    def to_representation(self, instance):
        """Вернуть представление рецепта через сериализатор чтения."""
        return RecipeGetSerializer(
            instance,
            context={'request': self.context.get('request')},
        ).data


class RecipeGetSerializer(serializers.ModelSerializer):
    """Сериализатор рецепта для чтения."""

    author = UserGetSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    ingredients = RecipeIngredientGetSerializer(
        source='recipe_ingredients',
        many=True,
        read_only=True,
    )
    image = Base64ImageField(required=True, allow_null=False)
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        """Настройки сериализатора рецепта для чтения."""

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

    def _check_user_status(self, obj, model_class):
        """Проверить, есть ли рецепт у пользователя в указанной модели."""
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return False
        return model_class.objects.filter(recipe=obj, user=user).exists()

    def get_is_favorited(self, obj):
        """Проверить, находится ли рецепт в избранном у пользователя."""
        return self._check_user_status(obj, Favorite)

    def get_is_in_shopping_cart(self, obj):
        """Проверить, находится ли рецепт в списке покупок пользователя."""
        return self._check_user_status(obj, ShoppingCart)


class MiniRecipeSerializer(serializers.ModelSerializer):
    """Короткая версия рецепта для списков."""

    image = Base64ImageField(required=True, allow_null=False)

    class Meta:
        """Настройки сериализатора короткого рецепта."""

        model = Recipe
        fields = (
            'id',
            'name',
            'image',
            'cooking_time',
        )


class FavoriteSerializer(serializers.ModelSerializer):
    """Сериализатор добавления и удаления рецепта из избранного."""

    class Meta:
        """Настройки сериализатора избранных рецептов."""

        model = Favorite
        fields = ('user', 'recipe')

    def validate(self, data):
        """Проверить, что рецепт ещё не добавлен в избранное."""
        if Favorite.objects.filter(**data).exists():
            raise serializers.ValidationError(
                'Рецепт уже добавлен в избранное.'
            )
        return data

    def to_representation(self, instance):
        """Вернуть краткое представление рецепта."""
        return MiniRecipeSerializer(
            instance.recipe,
            context={'request': self.context.get('request')},
        ).data


class ShoppingCartSerializer(serializers.ModelSerializer):
    """Сериализатор добавления и удаления рецепта из списка покупок."""

    class Meta:
        """Настройки сериализатора списка покупок."""

        model = ShoppingCart
        fields = ('user', 'recipe')

    def validate(self, data):
        """Проверить, что рецепт ещё не в списке покупок."""
        if ShoppingCart.objects.filter(**data).exists():
            raise serializers.ValidationError(
                'Рецепт уже добавлен в список покупок.'
            )
        return data

    def to_representation(self, instance):
        """Вернуть краткое представление рецепта."""
        return MiniRecipeSerializer(
            instance.recipe,
            context={'request': self.context.get('request')},
        ).data


class SubscriptionPostSerializer(serializers.ModelSerializer):
    """Сериализатор создания подписки."""

    class Meta:
        """Настройки сериализатора создания подписки."""

        model = Follow
        fields = ('user', 'author')

    def validate(self, attrs):
        """Проверить корректность подписки при создании."""
        request = self.context['request']
        user = request.user
        author = attrs.get('author')

        attrs['user'] = user

        if user == author:
            raise serializers.ValidationError('Нельзя подписаться на себя.')
        if Follow.objects.filter(user=user, author=author).exists():
            raise serializers.ValidationError(
                'Вы уже подписаны на этого пользователя.'
            )
        return attrs

    def to_representation(self, instance):
        """Вернуть представление подписки через сериализатор чтения."""
        request = self.context.get('request')
        return SubscriptionGetSerializer(
            instance.author,
            context={'request': request},
        ).data


class SubscriptionGetSerializer(serializers.ModelSerializer):
    """Сериализатор подписки: автор с его рецептами."""

    recipes = serializers.SerializerMethodField(method_name='get_recipes')
    recipes_count = serializers.IntegerField(default=0)
    is_subscribed = serializers.BooleanField(default=True)
    avatar = Base64ImageField(allow_null=True, required=False)

    class Meta:
        """Настройки сериализатора подписки для чтения."""

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

    def get_recipes(self, author):
        """Вернуть список рецептов автора с учётом recipes_limit."""
        recipes = author.recipes.all()
        request = self.context.get('request')
        recipes_limit = None
        if request:
            recipes_limit = request.query_params.get('recipes_limit')
        if recipes_limit and recipes_limit.isdigit():
            recipes = recipes[: int(recipes_limit)]
        return MiniRecipeSerializer(
            recipes,
            many=True,
            context={'request': request},
        ).data


class SubscriptionSerializer(UserGetSerializer):
    """Автор, на которого подписан пользователь (список подписок)."""

    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta(UserGetSerializer.Meta):
        """Настройки сериализатора списка подписок."""

        fields = UserGetSerializer.Meta.fields + ('recipes', 'recipes_count')

    def get_recipes(self, obj):
        """Вернуть рецепты автора с учётом recipes_limit."""
        request = self.context.get('request')
        recipes_qs = obj.recipes.all().order_by('-id')
        recipes_limit = None
        if request:
            recipes_limit = request.query_params.get('recipes_limit')
        if recipes_limit:
            try:
                recipes_qs = recipes_qs[: int(recipes_limit)]
            except (TypeError, ValueError):
                pass
        return MiniRecipeSerializer(
            recipes_qs,
            many=True,
            context={'request': request},
        ).data

    def get_recipes_count(self, obj):
        """Вернуть количество рецептов автора."""
        return obj.recipes.count()
