FROM python:3.12-slim

WORKDIR /app

# Dépendances système pour PyTorch CPU + PIL + psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    libglib2.0-0 libsm6 libxrender1 libxext6 libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Installer torch CPU-only (beaucoup plus léger que la version CUDA)
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
    torch==2.5.1 torchvision==0.20.1

# Le reste : Django + OCR + Django deps
RUN pip install --no-cache-dir \
    django==4.2.29 djangorestframework==3.16.1 \
    django-cors-headers==4.9.0 django-filter==25.1 psycopg2-binary==2.9.11 \
    requests==2.32.5 rapidfuzz==3.10.1 Pillow==11.1.0 \
    easyocr==1.7.2 numpy==2.0.2 beautifulsoup4==4.14.3

COPY . .

ENV DJANGO_DEBUG=False
ENV POSTGRES_PORT=5432

ENTRYPOINT ["python", "manage.py"]
