# Plan de despliegue — gymAccess en el droplet `saas-ritual`

Guía para ejecutar de arriba abajo. Cada paso termina con una **verificación**: si no
pasa, no se sigue al siguiente.

**Sustituye a `consideraciones_produccion.md`** (19 de julio), que se escribió antes de
Docker y antes de la auditoría de seguridad. Aquel documento sigue siendo útil como
explicación de *por qué* de cada medida, pero varias de sus instrucciones ya no aplican:
recomienda descomentar un bloque de MySQL que ya no existe, instalar gunicorn a mano
(ahora va en el contenedor) y configurar en `settings.py` cosas que ya están hechas.

> **Lo que aquí NO está verificado.** Los pasos 0 a 2 y 5 a 9 corren en el droplet y no
> se han ejecutado: están escritos con los datos que ya conocemos del servidor, pero
> nadie los ha probado allá. Los pasos 3 y 4 (Postgres y backend) **sí** se ejecutaron
> completos en local, incluida la migración de los datos reales.

---

## El servidor con el que trabajamos

| | |
|---|---|
| Droplet | `saas-ritual` · 143.110.197.117 · Digital Ocean |
| Recursos | 2 núcleos · 3.8 GiB RAM (~1.9 GiB libres) · 4 GiB swap · 77 G disco |
| Ya corriendo | **SaaS de citas para spas** (mxritual.com): `saas_agenda_backend` **:8000**, `saas_agenda_web` :3000, `evolution` :8080, más su Postgres y su Redis |
| Reverse proxy | nginx en el host, con *name-based virtual hosting* (80/443 ocupados) |
| Docker | usa el **containerd image store** — el cache de build NO vive en `/var/lib/docker` |

**El riesgo número uno de este despliegue no es gymAccess: es tumbar mxritual.com**, que
ya está en producción. Todo lo que sigue está pensado alrededor de eso.

---

## Paso 0 · Preventivos de disco — ANTES de nada

No es opcional ni se deja para después. El disco de este droplet se llenaba de 20 % a
60 % cada pocas semanas, y la causa se encontró en agosto: el cache de BuildKit, 24 GB
en 110 entradas. Meter un stack más **sin cerrar eso primero acelera el problema**.

```bash
# 1. Purga semanal del cache de build (sin esto vuelve a 60% en 3-4 semanas)
sudo crontab -e
# añadir:
0 4 * * 0 /usr/bin/docker builder prune -af --filter until=168h

# 2. Rotación de logs de Docker — hoy NO rotan (evolution 269 MB, nginx 53 MB)
sudo tee /etc/docker/daemon.json >/dev/null <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
EOF
sudo systemctl restart docker      # OJO: reinicia los contenedores del spa

# 3. Journal de systemd (estaba en 407 MB)
sudo journalctl --vacuum-size=200M
```

El `restart` de Docker tumba momentáneamente mxritual.com: hacerlo en horario de baja
demanda y confirmar después que sus contenedores volvieron.

> **No tocar el volumen `saas_agenda_postgres_data`.** Un `docker volume prune` a ciegas
> se llevaría la base del spa.

**Verificación**

```bash
df -h /                                   # uso de disco
docker ps --format '{{.Names}}\t{{.Status}}' | sort   # todo el spa arriba
curl -sI https://mxritual.com | head -1   # 200 antes de continuar
```

---

## Paso 1 · Traer el código

```bash
sudo mkdir -p /opt/gymaccess && sudo chown $USER:$USER /opt/gymaccess
git clone <repo> /opt/gymaccess
cd /opt/gymaccess
```

**Verificación**: existen `docker-compose.yml`, `backend/Dockerfile` y `.env.example`.

---

## Paso 2 · Configurar `.env`

```bash
cp .env.example .env
python3 -c "from secrets import token_urlsafe; print(token_urlsafe(50))"   # SECRET_KEY
python3 -c "from secrets import token_urlsafe; print(token_urlsafe(32))"   # POSTGRES_PASSWORD
nano .env
chmod 600 .env
```

Valores reales para este servidor:

```ini
DJANGO_SECRET_KEY=<la generada arriba — NUNCA la del repo>
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=gym.tudominio.com
DJANGO_CORS_ORIGINS=https://gym.tudominio.com
DJANGO_SSL_REDIRECT=1
DJANGO_TRAS_PROXY=1
DJANGO_ADMIN_URL=            # vacío = panel de Django apagado. Recomendado.
BACKEND_PORT=8001            # NO 8000: lo ocupa saas_agenda_backend
POSTGRES_DB=gymaccess
POSTGRES_USER=gymaccess
POSTGRES_PASSWORD=<la generada arriba>
```

Con `DJANGO_DEBUG=0` el arranque **falla** si falta `DJANGO_SECRET_KEY` o
`DJANGO_CORS_ORIGINS`. Es deliberado: antes el servidor arrancaba igual firmando tokens
con la llave de desarrollo, que está publicada en el repo y en el historial de git.

### Ajuste para que nginx pueda leer media y estáticos

En `docker-compose.yml`, cambiar los volúmenes con nombre por *bind mounts*. nginx corre
en el host y no puede servir un volumen de Docker sin meterse en `/var/lib/docker`, que
es frágil y depende de detalles internos:

```yaml
    volumes:
      - /opt/gymaccess/datos/media:/app/media
      - /opt/gymaccess/datos/staticfiles:/app/staticfiles
```

```bash
mkdir -p /opt/gymaccess/datos/{media,staticfiles}
```

**Verificación**: `docker compose config --quiet` sin salida.

---

## Paso 3 · Postgres y los datos

Runbook completo aparte: **`migrar_a_postgres.md`**. Resumen del orden:

1. Respaldo de `db.sqlite3`
2. `migrate` sobre SQLite (crea `token_blacklist`, aplica `usuarios/0006`)
3. `dumpdata` **con `PYTHONUTF8=1`** — sin eso los acentos se corrompen
4. `docker compose up -d db` + `migrate`
5. `loaddata` **por stdin**
6. Comparar conteos tabla por tabla

Ese documento sí está verificado de punta a punta: 67 objetos, 22 tablas cuadrando,
acentos intactos.

**Verificación**: los conteos de SQLite y Postgres coinciden en **todas** las tablas.

---

## Paso 4 · Backend

```bash
docker compose up -d --build
docker compose logs -f backend      # Ctrl-C al ver "Booting worker"
```

**Verificación**

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8001/api/socios/   # 401
ss -tlnp | grep 8001                                                        # SOLO 127.0.0.1
docker compose exec -T backend python manage.py test --noinput | tail -3    # 417 OK
```

El `401` es la respuesta correcta: la API está viva y cerrada. Que escuche **solo** en
`127.0.0.1` es lo que impide que el backend quede expuesto saltándose el firewall.

---

## Paso 5 · Frontend

`frontend/src/api/axios.js` usa `baseURL: '/api'`, **relativo**. Eso obliga a que el SPA
y la API se sirvan desde el **mismo origen**: nginx sirve los archivos y hace proxy de
`/api/` al backend. No hace falta ninguna variable `VITE_API_URL` (lo que pedía el
documento viejo ya no aplica).

```bash
cd /opt/gymaccess/frontend
npm ci
npm run build          # -> dist/  (~791 KB, 228 KB gzip)
sudo mkdir -p /var/www/gymaccess
sudo cp -r dist/* /var/www/gymaccess/
```

**El frontend no va en Docker, a propósito.** Su build son archivos estáticos que nginx
sirve con cero procesos. Containerizarlo significaría o un dev server de Vite (203 MB de
RAM para servir archivos) o una imagen con `node_modules` de ~918 MB — que es exactamente
lo que llenó este disco.

Si `npm ci` no cabe en RAM junto al spa, construir en local y subir solo `dist/` por
`scp`. Es la opción más segura en un droplet de 2 núcleos compartidos.

**Verificación**: `ls /var/www/gymaccess/index.html`.

---

## Paso 6 · nginx — el paso delicado

Aquí es donde se puede tumbar mxritual.com. **Nunca tocar su archivo de configuración.**
Se añade uno nuevo y se valida antes de recargar.

```bash
sudo nano /etc/nginx/sites-available/gymaccess
```

```nginx
# Límites de tasa: primera línea de defensa, antes de gastar CPU de Python.
# Complementan el throttling de DRF, no lo sustituyen.
limit_req_zone $binary_remote_addr zone=gym_api:10m   rate=10r/s;
limit_req_zone $binary_remote_addr zone=gym_login:10m rate=1r/s;

server {
    listen 80;
    server_name gym.tudominio.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name gym.tudominio.com;

    ssl_certificate     /etc/ssl/gymaccess/fullchain.pem;
    ssl_certificate_key /etc/ssl/gymaccess/privkey.pem;

    # Fotos de socios: 5 MB de sobra y corta payloads gigantes.
    client_max_body_size 5M;

    root /var/www/gymaccess;
    index index.html;

    # React Router: cualquier ruta desconocida la resuelve el SPA, no un 404 de nginx.
    location / {
        try_files $uri $uri/ /index.html;
    }

    location /static/ { alias /opt/gymaccess/datos/staticfiles/; access_log off; }

    # Fotos de socios. Son datos personales: `autoindex off` evita listar el directorio.
    location /media/  { alias /opt/gymaccess/datos/media/; autoindex off; }

    location /api/auth/ {
        limit_req zone=gym_login burst=5 nodelay;
        proxy_pass http://127.0.0.1:8001;
        include /etc/nginx/proxy_params;
    }

    location /api/ {
        limit_req zone=gym_api burst=20 nodelay;
        proxy_pass http://127.0.0.1:8001;
        include /etc/nginx/proxy_params;
    }
}
```

`proxy_params` debe pasar `X-Forwarded-Proto` y `X-Forwarded-For`; Django los necesita
para no entrar en bucle de redirección y para registrar la IP real. Comprobar que los
lleva:

```bash
cat /etc/nginx/proxy_params
```

Debe incluir `proxy_set_header X-Forwarded-Proto $scheme;` y
`proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`.

### Enlaces del QR que se mandan al socio

El mensaje de WhatsApp lleva un enlace a `/api/accesos/qr/<token>/`, la página donde el
socio ve su código. Dos cosas que revisar aquí, porque fallan en silencio:

**1. `proxy_params` tiene que pasar también el `Host`.** Django arma ese enlace con el
host de la petición, así que si nginx manda `Host: 127.0.0.1:8001` el socio recibe un
enlace a la dirección interna del servidor. Comprobar que `proxy_params` incluye
`proxy_set_header Host $http_host;`. Si no lo lleva —o si prefieres no depender de
ello— se fija el dominio a mano en `.env`:

```
QR_BASE_URL=https://gym.tudominio.com
```

**2. Ese enlace es público y tiene que seguir siéndolo.** El socio no tiene cuenta en el
sistema: no hay sesión con la que autenticar esa petición. Cae bajo `location /api/`, que
ya está limitado a 10 r/s, y el propio endpoint lleva su throttle de 20/min. Lo que lo
hace seguro no es el secreto de la URL sino los 96 bits de azar del token; no añadir ahí
ninguna regla de nginx que exija cabeceras de sesión o el enlace dejará de abrir.

Prueba después de recargar nginx, desde fuera del servidor:

```bash
curl -sI https://gym.tudominio.com/api/accesos/qr/<token-de-un-socio>.png | head -3
# HTTP/2 200 ... content-type: image/png
```

```bash
sudo ln -s /etc/nginx/sites-available/gymaccess /etc/nginx/sites-enabled/
sudo nginx -t                 # <-- si esto falla, NO recargar
sudo systemctl reload nginx
```

**Verificación — en este orden, y el primero es el que importa**

```bash
curl -sI https://mxritual.com | head -1                 # el spa SIGUE vivo
curl -sI https://gym.tudominio.com | head -1            # 200
curl -s -o /dev/null -w '%{http_code}\n' https://gym.tudominio.com/api/socios/   # 401
```

Si mxritual.com cayó: `sudo rm /etc/nginx/sites-enabled/gymaccess && sudo systemctl reload nginx`.

---

## Paso 7 · TLS, firewall y Cloudflare

**TLS**: certificado *Origin* de Cloudflare o Let's Encrypt (`certbot --nginx -d
gym.tudominio.com`). En Cloudflare, modo **Full (strict)** — nunca "Flexible".

**DNS**: registro A hacia el droplet con el **proxy activado (nube naranja)**. En gris
solo hace DNS y no protege de nada.

**Firewall**:

```bash
sudo ufw default deny incoming
sudo ufw allow OpenSSH
sudo ufw allow 80,443/tcp
sudo ufw enable
sudo ufw status verbose
```

Si se usa Cloudflare, restringir 80/443 a sus rangos (https://www.cloudflare.com/ips/):
si el atacante conoce la IP real del droplet, la ataca directo y se salta la protección.

**Verificación** — desde fuera del droplet:

```bash
nmap -Pn 143.110.197.117            # solo 22/80/443; NUNCA 8001 ni 5432
```

Que `8001` y `5432` no aparezcan es la comprobación que cierra el despliegue.

---

## Paso 8 · Backups

Postgres en un contenedor sin respaldo fuera del droplet es tan frágil como el SQLite que
sustituye.

```bash
sudo tee /usr/local/bin/backup-gymaccess.sh >/dev/null <<'EOF'
#!/bin/bash
set -euo pipefail
cd /opt/gymaccess
FECHA=$(date +%F)
docker compose exec -T db pg_dump -U gymaccess gymaccess | gzip > /var/backups/gymaccess-$FECHA.sql.gz
find /var/backups -name 'gymaccess-*.sql.gz' -mtime +14 -delete
EOF
sudo chmod +x /usr/local/bin/backup-gymaccess.sh
sudo mkdir -p /var/backups
# Diario a las 3:00
echo '0 3 * * * /usr/local/bin/backup-gymaccess.sh' | sudo crontab -
```

**Falta la mitad**: un backup que vive en el mismo disco que la base no protege de que el
droplet muera. Copiarlo a DO Spaces o similar.

**Verificación — restaurar, no solo generar.** Un backup que nunca se restauró no es un
backup:

```bash
sudo /usr/local/bin/backup-gymaccess.sh
zcat /var/backups/gymaccess-$(date +%F).sql.gz | head -20    # tiene SQL real
```

---

## Paso 9 · Verificación final, con el negocio de verdad

Los `curl` dicen que el servidor responde; esto dice que el gimnasio puede operar.

1. Entrar a `https://gym.tudominio.com` e iniciar sesión como recepción.
2. Buscar un socio por nombre.
3. **Hacer un check-in real con un QR** y ver que la puerta responde.
4. Registrar un pago y comprobar que aparece en el corte.
5. Comprobar que la foto de un socio carga (valida el `alias` de `/media/`).

Y las tres comprobaciones de seguridad que motivaron todo esto:

```bash
# El panel de Django no debe existir
curl -s -o /dev/null -w '%{http_code}\n' https://gym.tudominio.com/admin/     # 404

# Un origen ajeno no debe poder llamar a la API
curl -sI -H 'Origin: https://malicioso.com' https://gym.tudominio.com/api/socios/ | grep -i access-control
# no debe aparecer Access-Control-Allow-Origin

# El check-in rechaza a un socio dado de baja
# (probar con un socio inactivo: debe responder "socio dado de baja")
```

---

## Si algo sale mal

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `port is already allocated` | `BACKEND_PORT=8000`, que es del spa | Ponerlo en 8001 |
| mxritual.com caído tras nginx | vhost nuevo con error | `rm /etc/nginx/sites-enabled/gymaccess && systemctl reload nginx` |
| Bucle de redirección | falta `X-Forwarded-Proto` en `proxy_params` | Añadirlo, o `DJANGO_SSL_REDIRECT=0` mientras se arregla |
| `ImproperlyConfigured` al arrancar | falta `DJANGO_SECRET_KEY` o `DJANGO_CORS_ORIGINS` | Es el comportamiento correcto: llenarlas |
| 401 en todo tras suspender un gym | funciona como debe | Reactivar desde `/api/saas/tenants/<id>/reactivar/` |
| Datos con `Ã©` en vez de `é` | `dumpdata` sin `PYTHONUTF8=1` | Rehacer la migración desde el respaldo |

**Vuelta atrás completa**: `docker compose down`, quitar el symlink de nginx, recargar
nginx. gymAccess desaparece y el spa no se entera. La base queda en su volumen; para
borrarla también, `docker compose down -v` (irreversible).

---

## Lo que este plan deja pendiente a propósito

- **Redis para el throttling.** Con 3 workers de gunicorn, cada uno lleva su propio
  contador en memoria y el límite real se triplica. Los límites siguen funcionando, solo
  que más laxos de lo que dicen.
- **Rotación de refresh tokens.** La blacklist está instalada pero la rotación apagada:
  el frontend reintenta `/auth/refresh/` unas 15 veces cuando el token vence, y con
  rotación eso cerraría sesiones de usuarios reales. Se enciende al arreglar ese bucle.
- **`/media/` sin autenticar.** Las fotos de socios se sirven por URL directa a quien la
  conozca. Restringirlo requiere `internal` + `X-Accel-Redirect` en nginx y una vista que
  lo autorice.
- **Huellas en claro.** `MetodoAcceso.token` guarda el template biométrico sin cifrar,
  que es dato personal *sensible* bajo la LFPDPPP.
- **Monitoreo.** UptimeRobot y Sentry (planes gratuitos) para enterarse de un 500 sin
  revisar logs a mano.

Detalle de estos y del resto en `auditoria_seguridad_2026-08-23.md`.
