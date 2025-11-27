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
from users.models import User, Follow

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

        user = request.user
        # Для анонимного пользователя user.pk == None,
        # фильтр по внешнему ключу ничего не вернёт результат будет False.
        return author.followers.filter(user_id=user.pk).exists()


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
        # Берём данные, не мутируя исходный словарь
        tags = validated_data.get('tags')
        ingredients = validated_data.get('recipe_ingredients')

        # Работаем с копией
        data = validated_data.copy()
        data.pop('tags', None)
        data.pop('recipe_ingredients', None)
        # author в запросе игнорируем, всегда берём из контекста
        data['author'] = self.context['request'].user

        recipe = super().create(data)
        self._update_tags_and_ingredients(recipe, tags, ingredients)
        return recipe

    def update(self, instance, validated_data):
        """Обновить рецепт и связанные теги и ингредиенты."""
        tags = validated_data.get('tags')
        ingredients = validated_data.get('recipe_ingredients')

        data = validated_data.copy()
        data.pop('tags', None)
        data.pop('recipe_ingredients', None)

        self._update_tags_and_ingredients(instance, tags, ingredients)
        return super().update(instance, data)

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

    def get_is_favorited(self, obj):
        """Проверить, есть ли рецепт в избранном у текущего пользователя."""
        return self._check_user_status(obj, Favorite)

    def get_is_in_shopping_cart(self, obj):
        """Возвращает True, если рецепт в списке покупок."""
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

    error_message = 'Рецепт уже добавлен в избранное.'
    not_found_message = 'Рецепт не найден в избранном.'

    class Meta:
        """Настройки сериализатора избранных рецептов."""

        model = Favorite
        fields = ('user', 'recipe')

    def validate(self, data):
        """Проверить, что такая запись уже существует."""
        if self.Meta.model.objects.filter(**data).exists():
            raise serializers.ValidationError(self.error_message)
        return data

    @classmethod
    def validate_delete(cls, user, recipe):
        """Проверка перед удалением рецепта из избранного."""
        if not cls.Meta.model.objects.filter(user=user, recipe=recipe).exists():
            raise serializers.ValidationError(cls.not_found_message)

    def to_representation(self, instance):
        """Вернуть краткое представление рецепта."""
        return MiniRecipeSerializer(
            instance.recipe,
            context=self.context,
        ).data


class ShoppingCartSerializer(FavoriteSerializer):
    """Сериализатор добавления и удаления рецепта из списка покупок."""

    error_message = 'Рецепт уже добавлен в список покупок.'
    not_found_message = 'Рецепт не найден в списке покупок.'

    class Meta(FavoriteSerializer.Meta):
        """Настройки сериализатора списка покупок."""

        model = ShoppingCart


class SubscriptionPostSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и удаления подписки."""

    class Meta:
        model = Follow
        # На вход никаких полей не ожидаем — маршрут не принимает body.
        fields = ()

    def validate(self, attrs):
        """Проверка возможности подписки."""
        request = self.context.get('request')
        author = self.context.get('author')

        if request is None or author is None:
            raise ValidationError(
                'Отсутствуют данные контекста для проверки подписки.'
            )

        user = request.user

        if user == author:
            raise ValidationError('Нельзя подписаться на самого себя.')

        if author.followers.filter(user=user).exists():
            raise ValidationError('Подписка уже существует.')

        # Прокинем автора дальше в create через validated_data.
        attrs['author'] = author
        return attrs

    def create(self, validated_data):
        """Создание подписки."""
        request = self.context['request']
        user = request.user
        author = validated_data['author']
        return Follow.objects.create(user=user, author=author)

    @classmethod
    def validate_delete(cls, *, user, author):
        """Проверка перед удалением подписки."""
        if not author.followers.filter(user=user).exists():
            raise ValidationError('Подписки не существует')


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
