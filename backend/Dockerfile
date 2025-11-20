FROM python:3.10

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# gunicorn слушает 8000 — под это уже настроен nginx
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "foodgram.wsgi:application"]