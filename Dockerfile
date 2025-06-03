FROM python:3.12-slim

RUN apt-get update && apt-get install -y libgl1 libglib2.0-0 tesseract-ocr

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

CMD exec gunicorn project.wsgi:application --bind 0.0.0.0:${PORT}
