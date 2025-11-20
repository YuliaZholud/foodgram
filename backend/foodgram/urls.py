"""Главная URL-конфигурация проекта Foodgram."""

from api.views import redirect_to_recipe_detail
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path(
        's/<slug:short_link_code>/',
        redirect_to_recipe_detail,
        name='short_link_redirect',
    ),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
