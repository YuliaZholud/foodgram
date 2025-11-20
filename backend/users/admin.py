"""Админ-конфигурация приложения users."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Follow, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Админка пользователя."""

    list_display = (
        'id',
        'username',
        'email',
        'first_name',
        'last_name',
        'is_staff',
        'subscribers_count',
        'recipes_count',
    )
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',)

    @admin.display(description='Подписчиков')
    def subscribers_count(self, obj):
        """Вернуть количество подписчиков пользователя."""
        return obj.followers.count()

    @admin.display(description='Рецептов')
    def recipes_count(self, obj):
        """Вернуть количество рецептов пользователя."""
        return obj.recipes.count()


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    """Админка подписок."""

    list_display = ('id', 'user', 'author')
    search_fields = (
        'user__username',
        'user__email',
        'author__username',
        'author__email',
    )
    list_filter = ('user', 'author')


admin.site.empty_value_display = 'Нет значения'
