FROM python:3.10

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# gunicorn слушает 8000 — под это мы уже настроили nginx
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "foodgram_backend.wsgi"]
