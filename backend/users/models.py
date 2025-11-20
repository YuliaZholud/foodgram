"""Модели приложения users."""

from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models

from .constants import MAX_EMAIL_LENGTH, NAME_LENGTH, USERNAME_REGEX
from .validators import not_allowed_user_name


class User(AbstractUser):
    """Модель пользователя с авторизацией по email."""

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = (
        'username',
        'first_name',
        'last_name',
    )

    username = models.CharField(
        verbose_name='Ник',
        max_length=NAME_LENGTH,
        unique=True,
        validators=(
            RegexValidator(USERNAME_REGEX),
            not_allowed_user_name,
        ),
        error_messages={
            'unique': (
                'Пользователь с таким ником уже существует'
            ),
        },
    )
    email = models.EmailField(
        verbose_name='Эл. почта',
        max_length=MAX_EMAIL_LENGTH,
        unique=True,
    )
    # поле password унаследовано от AbstractUser, переопределять не нужно
    first_name = models.CharField(
        verbose_name='Имя',
        max_length=NAME_LENGTH,
    )
    last_name = models.CharField(
        verbose_name='Фамилия',
        max_length=NAME_LENGTH,
    )
    avatar = models.ImageField(
        verbose_name='Аватар',
        upload_to='users/avatars/',
        blank=True,
        null=True,
        default=None,
    )

    class Meta:
        """Настройки модели пользователя."""

        ordering = ('username',)
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        """Строковое представление объекта."""
        return self.username


class Follow(models.Model):
    """Подписка пользователя на автора."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Подписчик',
        related_name='follows',
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='Автор',
        related_name='followers',
    )

    class Meta:
        """Настройки модели подписки."""

        verbose_name = 'Подписка'
        verbose_name_plural = 'Подписки'
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'author'),
                name='unique_following_pair',
            ),
            models.CheckConstraint(
                check=~models.Q(user=models.F('author')),
                name='self_sub_prohibited',
            ),
        ]

    def __str__(self):
        """Строковое представление объекта."""
        return f'{self.user} подписан на {self.author}'
