FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# libpq5 es lo unico que psycopg[binary] necesita en runtime; sin build-essential
# para que la imagen no arrastre compilador (mantiene el disco del droplet chico).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Las dependencias van antes que el codigo: mientras requirements.txt no cambie,
# los rebuilds reutilizan esta capa y no vuelven a bajar nada.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN adduser --disabled-password --gecos '' --uid 10001 app \
    && mkdir -p /app/staticfiles /app/media \
    && chmod +x /app/entrypoint.sh \
    && chown -R app:app /app
USER app

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "gymaccess.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
