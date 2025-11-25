# Foodgram — «Продуктовый помощник»

Онлайн-сервис, на котором пользователи могут:

- публиковать рецепты;
- добавлять чужие рецепты в избранное;
- подписываться на авторов;
- формировать список покупок по выбранным рецептам и скачивать его в виде файла.

Проект состоит из backend (Django + DRF), SPA-frontend (React) и инфраструктуры (Docker, nginx, PostgreSQL).

---

## Оглавление

- [Описание проекта](#описание-проекта)
- [Стек технологий](#стек-технологий)
- [Установка и запуск локально](#установка-и-запуск-локально)
    - [1. Клонирование репозитория](#1-клонирование-репозитория)
    - [2. Настройка виртуального окружения](#2-настройка-виртуального-окружения)
    - [3. Настройка переменных окружения](#3-настройка-переменных-окружения)
    - [4. Установка зависимостей](#4-установка-зависимостей)
    - [5. Миграции, суперпользователь и статика](#5-миграции-суперпользователь-и-статика)
    - [6. Запуск сервера разработки](#6-запуск-сервера-разработки)
- [Запуск в Docker](#запуск-в-docker)
- [Документация по API](#документация-по-api)
- [Примеры запросов к API](#примеры-запросов-к-api)
- [Автор](#автор)

---

## Описание проекта

**Foodgram** — это сервис для публикации и просмотра рецептов.

Основные возможности:

- регистрация и аутентификация пользователей;
- просмотр рецептов с фильтрацией по тегам;
- создание, редактирование и удаление собственных рецептов;
- добавление рецептов в избранное;
- подписка на авторов и просмотр ленты «Мои подписки»;
- добавление рецептов в «Список покупок» с возможностью скачать агрегированный список ингредиентов;
- смена пароля и изменение аватара пользователя;
- админ-зона для управления пользователями, рецептами, тегами и ингредиентами.

---

## Стек технологий

**Backend:**

- Python 3.x
- Django
- Django REST Framework
- Djoser (аутентификация)
- PostgreSQL
- Gunicorn

**Инфраструктура:**

- Docker, Docker Compose
- Nginx

**Frontend:**

- React (SPA, предоставлен Яндекс Практикумом)

---

## Установка и запуск локально

### 1. Клонирование репозитория

```bash
git clone <ссылка-на-репозиторий>
cd foodgram/backend
(если структура репозитория другая — перейти в папку backend, где лежит manage.py)

2. Настройка виртуального окружения
bash
Копировать код
python -m venv venv
source venv/bin/activate        # Linux / macOS
# или
venv\Scripts\activate           # Windows
3. Настройка переменных окружения
В папке backend создайте файл .env и укажите в нём минимум:

env
Копировать код
SECRET_KEY=your_secret_key
DEBUG=True

POSTGRES_DB=django
POSTGRES_USER=django
POSTGRES_PASSWORD=django
DB_HOST=localhost
DB_PORT=5432
ALLOWED_HOSTS=localhost,127.0.0.1
Для локальной разработки можно использовать SQLite, а для боевого сервера — PostgreSQL (как настроено в проекте).

4. Установка зависимостей
Находясь в папке backend:

bash
Копировать код
pip install -r requirements.txt
5. Миграции, суперпользователь и статика
bash
Копировать код
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic
6. Запуск сервера разработки
bash
Копировать код
python manage.py runserver
После запуска:

главный сайт: http://127.0.0.1:8000/

документация API: http://127.0.0.1:8000/api/docs/

Запуск в Docker
Полная инфраструктура (nginx + backend + frontend + PostgreSQL) собрана в папке infra.

Перейдите в папку infra:

bash
Копировать код
cd infra
При необходимости создайте .env для backend (если используется общий .env, убедитесь, что путь к нему корректен в docker-compose).

Запустите контейнеры:

bash
Копировать код
docker compose up -d
Контейнер frontend соберёт статические файлы и завершит работу — это ожидаемое поведение.

После запуска:

сайт: http://localhost/

API и документация: http://localhost/api/docs/

Документация по API
Спецификация API доступна по адресу:

http://localhost/api/docs/ — при локальном запуске;

/api/docs/ — на боевом сервере (например, https://foodgram-yulia.duckdns.org/api/docs/ при установленном домене).

Примеры запросов к API
Ниже приведены примеры запросов с использованием curl. Адрес /api/ может отличаться в зависимости от окружения.

Регистрация пользователя
bash
Копировать код
curl -X POST http://localhost/api/users/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "username": "testuser",
    "first_name": "Test",
    "last_name": "User",
    "password": "strong_password"
  }'
Получение токена (Djoser, token-auth)
bash
Копировать код
curl -X POST http://localhost/api/auth/token/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "strong_password"
  }'
В ответе придёт токен:

json
Копировать код
{"auth_token": "<your_token>"}
Дальше этот токен используем в заголовке:

http
Копировать код
Authorization: Token <your_token>
Получение списка рецептов
bash
Копировать код
curl -X GET http://localhost/api/recipes/
Добавление рецепта в избранное
bash
Копировать код
curl -X POST http://localhost/api/recipes/1/favorite/ \
  -H "Authorization: Token <your_token>"
Удаление рецепта из избранного
bash
Копировать код
curl -X DELETE http://localhost/api/recipes/1/favorite/ \
  -H "Authorization: Token <your_token>"
Добавление рецепта в список покупок
bash
Копировать код
curl -X POST http://localhost/api/recipes/1/shopping_cart/ \
  -H "Authorization: Token <your_token>"
Скачивание списка покупок
bash
Копировать код
curl -X GET http://localhost/api/recipes/download_shopping_cart/ \
  -H "Authorization: Token <your_token>" \
  -o shopping_list.txt
Автор
Юлия Жолудь
GitHub: YuliaZholud