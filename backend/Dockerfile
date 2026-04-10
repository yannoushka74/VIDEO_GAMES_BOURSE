FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install without botasaurus/chrome deps for now (API only)
RUN pip install --no-cache-dir django==4.2.29 djangorestframework==3.16.1 \
    django-cors-headers==4.9.0 django-filter==25.1 psycopg2-binary==2.9.11 \
    gunicorn==23.0.0 rapidfuzz==3.10.1 requests==2.32.5

COPY . .

ENV DJANGO_DEBUG=False
ENV POSTGRES_PORT=5432

RUN python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
