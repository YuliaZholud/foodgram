FROM nginx:1.25.4

# Конфиг берём из папки nginx/
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf

# redoc-доки копируем в /api/docs/
COPY docs/ /usr/share/nginx/html/api/docs/
