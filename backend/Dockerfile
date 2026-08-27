# Solo el backend se contiene. El frontend NO: su build de producción son 791 KB de
# estáticos (228 KB gzip) que nginx sirve con cero procesos Node. Meterlo aquí
# significaría o un dev server de Vite (203 MB de RAM para servir archivos) o una
# imagen con node_modules de ~918 MB, que es exactamente lo que llenó el disco del
# droplet: ~3 GB de capas por build acumuladas en el cache de BuildKit.
FROM python:3.12-slim

# PYTHONUNBUFFERED: sin esto los logs de gunicorn se quedan en el buffer y `docker
# logs` no muestra nada hasta que el proceso muere, que es justo cuando hacen falta.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Las dependencias en su propia capa: cambian mucho menos que el código, así que un
# `docker build` tras editar una vista no vuelve a bajar nada de PyPI.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/

# Usuario sin privilegios: si alguien consigue ejecución dentro del contenedor, que
# no sea root. Los directorios que Django escribe se crean antes de bajar de nivel.
RUN useradd --system --create-home --uid 10001 gymaccess \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R gymaccess:gymaccess /app
USER gymaccess

EXPOSE 8000

# 3 workers = 2 núcleos + 1, la regla práctica. El droplet tiene 2 núcleos y los
# comparte con el SaaS de spas, así que no conviene subir de ahí.
# --access-logfile - manda el log a stdout, que es donde Docker lo recoge.
CMD ["gunicorn", "gymaccess.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "60", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
