import os
from pathlib import Path

from django.core.management.utils import get_random_secret_key
from dotenv import load_dotenv
from recipes.constants import PAGE_SIZE

# Подгрузка .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# === Безопасность и отладка ===

SECRET_KEY = os.getenv('SECRET_KEY', get_random_secret_key())

DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

raw_allowed_hosts = os.getenv('ALLOWED_HOSTS')
if raw_allowed_hosts:
    ALLOWED_HOSTS = [h.strip() for h in raw_allowed_hosts.split(',')]
else:
    ALLOWED_HOSTS = [
        'localhost',
        '127.0.0.1',
        '89.169.186.95',
        'foodgram-yulia.duckdns.org',
    ]

CSRF_TRUSTED_ORIGINS = [
    'http://89.169.186.95',
    'http://89.169.186.95:8001',
    'http://foodgram-yulia.duckdns.org',
    'http://foodgram-yulia.duckdns.org:8001',
]

# === Приложения ===

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework.authtoken',
    'django_filters',
    'djoser',

    'users.apps.UsersConfig',
    'recipes.apps.RecipesConfig',
    'api.apps.ApiConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'foodgram.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'foodgram.wsgi.application'

# === База данных ===
# Локально можешь использовать SQLite, на сервере - PostgreSQL через переменные окружения

if DEBUG:
    # Локальная разработка - простая SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    # Продакшен / сервер - PostgreSQL из переменных окружения
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('POSTGRES_DB', 'django'),
            'USER': os.getenv('POSTGRES_USER', 'django'),
            'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'db'),
            'PORT': os.getenv('DB_PORT', 5432),
        }
    }

# === Валидация паролей ===

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# === Локаль и время ===

LANGUAGE_CODE = 'ru-ru'

TIME_ZONE = 'UTC'

USE_I18N = True
USE_TZ = True

# === DRF и Djoser ===

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': PAGE_SIZE,
}

DJOSER = {
    'LOGIN_FIELD': 'email',
    'SERIALIZERS': {
        'user': 'api.serializers.UserSerializer',
        'current_user': 'api.serializers.UserSerializer',
    },
    'HIDE_USERS': False,
    'PERMISSIONS': {
        'user_list': ('rest_framework.permissions.AllowAny',),
        'user': ('rest_framework.permissions.IsAuthenticatedOrReadOnly',),
    },
}

# === Статика и медиа ===

STATIC_URL = '/static/'
STATIC_ROOT = os.getenv(
    'STATIC_ROOT',
    BASE_DIR / 'collected_static',
)

MEDIA_URL = '/media/'
MEDIA_ROOT = os.getenv(
    'MEDIA_ROOT',
    os.path.join(BASE_DIR, 'media'),
)

# Путь к ингредиентам

PATH_TO_INGREDIENTS = BASE_DIR / 'data/ingredients.json'

# === PK по умолчанию ===

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
