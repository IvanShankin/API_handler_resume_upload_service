FROM python:3.13.3
WORKDIR /app
EXPOSE 8000

# Установка зависимостей для PostgreSQL клиента
RUN apt-get update && apt-get install -y \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Установка шрифтов
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    fonts-dejavu \
    fonts-liberation && \
    fc-cache -fv && \
    rm -rf /var/lib/apt/lists/*

COPY . .


ENV PYTHONPATH=/app

CMD ["python", "src/main.py"]