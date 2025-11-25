"""Сериализаторы API для пользователей, рецептов и подписок."""

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
    """Сериализатор аватара пользователя."""

    avatar = Base64ImageField(allow_null=True, file_prefix='avatar')

    class Meta:
        """Настройки сериализатора аватара."""

        model = User
        fields = ('avatar',)


class UserPostSerializer(serializers.ModelSerializer):
    """Сериализатор создания пользователя."""

    password = serializers.CharField(write_only=True)

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
        if request is None:
            return False

        user = request.user  # может быть и AnonymousUser
        return Follow.objects.filter(
            user_id=user.pk,
            author_id=author.pk,
        ).exists()


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
        fields = '__all__'


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
        """Проверить, что количество ингредиента больше нуля."""
        if value <= 0:
            raise serializers.ValidationError(
                'Количество должно быть больше нуля.'
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
            tuple(
                RecipeIngredient(recipe=recipe, **ingredient)
                for ingredient in ingredients
            )
        )

    def create(self, validated_data):
        """Создать рецепт и связанные теги и ингредиенты."""
        tags = validated_data.pop('tags')
        ingredients = validated_data.pop('recipe_ingredients')

        # author в запросе игнорируем, всегда берём из контекста
        validated_data['author'] = self.context['request'].user

        recipe = super().create(validated_data)
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
            context=self.context,
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
        if request is None:
            return False

        user = request.user  # может быть и AnonymousUser
        return model_class.objects.filter(
            recipe_id=obj.pk,
            user_id=user.pk,
        ).exists()


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

    error_message = 'Рецепт уже добавлен в избранное.'

    class Meta:
        """Настройки сериализатора избранных рецептов."""

        model = Favorite
        fields = ('user', 'recipe')

    def validate(self, data):
        """Проверить, что такая запись уже существует."""
        if self.Meta.model.objects.filter(**data).exists():
            raise serializers.ValidationError(self.error_message)
        return data

    def to_representation(self, instance):
        """Вернуть краткое представление рецепта."""
        return MiniRecipeSerializer(
            instance.recipe,
            context=self.context,
        ).data


class ShoppingCartSerializer(FavoriteSerializer):
    """Сериализатор добавления и удаления рецепта из списка покупок."""

    error_message = 'Рецепт уже добавлен в список покупок.'

    class Meta(FavoriteSerializer.Meta):
        """Настройки сериализатора списка покупок."""

        model = ShoppingCart


class SubscriptionPostSerializer(serializers.ModelSerializer):
    """Сериализатор создания подписки."""

    class Meta:
        """Настройки сериализатора создания подписки."""

        model = Follow
        fields = ('user', 'author')
        read_only_fields = ('user',)

    def validate(self, attrs):
        """Проверить корректность подписки при создании."""
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        author = attrs.get('author')

        if user is None or not user.is_authenticated:
            raise serializers.ValidationError(
                'Необходима аутентификация.'
            )

        if user == author:
            raise serializers.ValidationError(
                'Нельзя подписаться на себя.'
            )

        if Follow.objects.filter(
                user_id=user.pk,
                author_id=author.pk,
        ).exists():
            raise serializers.ValidationError(
                'Вы уже подписаны на этого пользователя.'
            )

        return attrs

    def create(self, validated_data):
        """Создать подписку для текущего пользователя."""
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        return Follow.objects.create(user=user, **validated_data)


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

    def get_recipes(self, obj):
        """Вернуть рецепты автора с учётом recipes_limit."""
        request = self.context.get('request')
        recipes_qs = obj.recipes.all().order_by('-id')

        if request:
            recipes_limit = request.query_params.get('recipes_limit')
            if recipes_limit and recipes_limit.isdecimal():
                recipes_qs = recipes_qs[: int(recipes_limit)]

        return MiniRecipeSerializer(
            recipes_qs,
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
