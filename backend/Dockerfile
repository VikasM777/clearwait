FROM python:3.12-slim

# Prevent Python from writing .pyc and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies if required (gcc, libpq for postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run db seed / migrations and start application with uvicorn
EXPOSE 8000

CMD ["sh", "-c", "python seed.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
