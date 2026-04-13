FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

COPY web/requirements.txt /tmp/web-requirements.txt
COPY celery-worker/requirements.txt /tmp/celery-requirements.txt
COPY govno_model/requirements.txt /tmp/govno-model-requirements.txt
COPY new_model/requirements.txt /tmp/new-model-requirements.txt

RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r /tmp/web-requirements.txt && \
    pip install --no-cache-dir -r /tmp/celery-requirements.txt && \
    pip install --no-cache-dir -r /tmp/govno-model-requirements.txt && \
    pip install --no-cache-dir -r /tmp/new-model-requirements.txt

COPY . /app

EXPOSE 8000

CMD ["python", "web/manage.py", "runserver", "0.0.0.0:8000"]
