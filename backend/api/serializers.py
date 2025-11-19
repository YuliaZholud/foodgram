import base64

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from recipes.models import (
    Favorite,
    Ingredient,
    IngredientInRecipe,
    Recipe,
    ShoppingCart,
    Tag,
)
from rest_framework import serializers

User = get_user_model()


class Base64ImageField(serializers.ImageField):
    """Поле для приёма картинок в base64."""

    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            # data:image/png;base64,....
            format_, imgstr = data.split(';base64,')
            ext = format_.split('/')[-1]
            data = ContentFile(
                base64.b64decode(imgstr),
                name=f'temp.{ext}',
            )
        return super().to_internal_value(data)


class UserSerializer(serializers.ModelSerializer):
    """Пользователь с флагом is_subscribed."""

    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'is_subscribed',
        )

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if not request or request.user.is_anonymous:
            return False
        return obj.subscribers.filter(user=request.user).exists()


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ('id', 'name', 'slug')


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class IngredientAmountSerializer(serializers.Serializer):
    """Ингредиент в теле запроса рецепта: {id, amount}."""

    id = serializers.IntegerField()
    amount = serializers.IntegerField(min_value=1)


class RecipeIngredientReadSerializer(serializers.ModelSerializer):
    """Ингредиент в рецепте (для чтения)."""

    id = serializers.ReadOnlyField(source='ingredient.id')
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit'
    )

    class Meta:
        model = IngredientInRecipe
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeShortSerializer(serializers.ModelSerializer):
    """Короткая версия рецепта (для подписок, избранного и корзины)."""

    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')


class RecipeReadSerializer(serializers.ModelSerializer):
    """Рецепт для чтения (список, детальная страница)."""

    author = UserSerializer(read_only=True)
    ingredients = RecipeIngredientReadSerializer(
        source='ingredient_links',
        many=True,
        read_only=True,
    )
    tags = TagSerializer(many=True, read_only=True)
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id',
            'author',
            'name',
            'image',
            'text',
            'ingredients',
            'tags',
            'cooking_time',
            'is_favorited',
            'is_in_shopping_cart',
        )

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if not request or request.user.is_anonymous:
            return False
        return obj.favorites.filter(user=request.user).exists()

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if not request or request.user.is_anonymous:
            return False
        return obj.shopping_cart.filter(user=request.user).exists()


class SubscriptionSerializer(UserSerializer):
    """Автор, на которого подписан пользователь."""

    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ('recipes', 'recipes_count')

    def get_recipes(self, obj):
        request = self.context.get('request')
        recipes_qs = obj.recipes.all().order_by('-id')
        recipes_limit = request.query_params.get('recipes_limit')
        if recipes_limit is not None:
            try:
                recipes_qs = recipes_qs[: int(recipes_limit)]
            except (TypeError, ValueError):
                pass
        return RecipeShortSerializer(
            recipes_qs,
            many=True,
            context={'request': request},
        ).data

    def get_recipes_count(self, obj):
        return obj.recipes.count()


class RecipeWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для создания и редактирования рецептов."""

    ingredients = IngredientAmountSerializer(many=True)
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True,
    )
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = (
            'id',
            'ingredients',
            'tags',
            'image',
            'name',
            'text',
            'cooking_time',
        )

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError(
                'Нужно указать хотя бы один ингредиент.'
            )
        seen = set()
        for item in value:
            ingredient_id = item.get('id')
            if ingredient_id in seen:
                raise serializers.ValidationError(
                    'Ингредиенты не должны повторяться.'
                )
            seen.add(ingredient_id)
            amount = item.get('amount')
            if amount is None or amount <= 0:
                raise serializers.ValidationError(
                    'Количество ингредиента должно быть больше 0.'
                )
        return value

    def validate_tags(self, value):
        if not value:
            raise serializers.ValidationError(
                'Нужно указать хотя бы один тег.'
            )
        if len(set(value)) != len(value):
            raise serializers.ValidationError(
                'Теги не должны повторяться.'
            )
        return value

    def validate_cooking_time(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                'Время приготовления должно быть больше 0.'
            )
        return value

    def create_ingredients(self, recipe, ingredients_data):
        """Создать связи IngredientInRecipe для рецепта."""
        objs = []
        for item in ingredients_data:
            ingredient_id = item['id']
            amount = item['amount']
            ingredient = Ingredient.objects.get(pk=ingredient_id)
            objs.append(
                IngredientInRecipe(
                    recipe=recipe,
                    ingredient=ingredient,
                    amount=amount,
                )
            )
        IngredientInRecipe.objects.bulk_create(objs)

    def create(self, validated_data):
        ingredients_data = validated_data.pop('ingredients')
        tags = validated_data.pop('tags')
        author = self.context['request'].user

        recipe = Recipe.objects.create(author=author, **validated_data)
        recipe.tags.set(tags)
        self.create_ingredients(recipe, ingredients_data)
        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('ingredients', None)
        tags = validated_data.pop('tags', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if tags is not None:
            instance.tags.set(tags)

        if ingredients_data is not None:
            instance.ingredient_links.all().delete()
            self.create_ingredients(instance, ingredients_data)

        instance.save()
        return instance

    def to_representation(self, instance):
        """Вернуть ответ в формате RecipeReadSerializer."""
        return RecipeReadSerializer(
            instance,
            context=self.context,
        ).data
