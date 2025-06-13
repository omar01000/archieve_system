FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    swig \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-ara \
    tesseract-ocr-eng \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libmagic1 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Run the application
CMD exec gunicorn project.wsgi:application --bind 0.0.0.0:${PORT} --workers 3 --threads 2
