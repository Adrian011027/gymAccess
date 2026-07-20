# Consideraciones para migrar a producción

Checklist para desplegar gymAccess (Round3Boxing) en el droplet de Digital Ocean de forma segura.
Ordenado por prioridad: lo marcado como **[CRÍTICO]** debe hacerse **antes** de exponer el servidor a internet.

---

## 1. Configuración de Django (`backend/gymaccess/settings.py`)

### [CRÍTICO] Apagar DEBUG
```python
DEBUG = False
```
Con `DEBUG = True`, cualquier error muestra a un atacante el código, las rutas y las variables del servidor.

### [CRÍTICO] Mover la SECRET_KEY a variable de entorno
La llave actual está hardcodeada en el repo (y en el historial de git). En producción **genera una nueva**:
```python
import os
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
```
Generar una nueva llave:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
Nunca reutilices la que está en el repo: quien tenga la SECRET_KEY puede falsificar sesiones y tokens.

### [CRÍTICO] Restringir ALLOWED_HOSTS
```python
ALLOWED_HOSTS = ['api.tudominio.com', 'tudominio.com']
```
`['*']` permite ataques de HTTP Host header poisoning.

### [CRÍTICO] Restringir CORS
```python
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = ['https://tudominio.com']
```
Con `CORS_ALLOW_ALL_ORIGINS = True`, cualquier página web puede llamar a tu API desde el navegador de un usuario logueado.

### [CRÍTICO] Forzar HTTPS y cookies seguras
```python
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000          # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
# Si nginx/Cloudflare termina el TLS delante de Django:
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

### Recomendado
- **JWT**: reducir `ACCESS_TOKEN_LIFETIME` de 8 h a 30–60 min (el refresh de 7 días ya cubre la comodidad del usuario).
- **Cambiar la URL del admin**: `path('panel-r3b/', admin.site.urls)` en vez de `admin/` — los bots escanean `/admin/` constantemente.
- **Límite de tamaño de peticiones** (anti-payloads gigantes):
  ```python
  DATA_UPLOAD_MAX_MEMORY_SIZE = 2_621_440   # 2.5 MB (default, dejarlo explícito)
  FILE_UPLOAD_MAX_MEMORY_SIZE = 5_242_880   # 5 MB para fotos de socios
  ```

Verificación automática antes de desplegar:
```bash
python manage.py check --deploy
```

---

## 2. Base de datos

- **[CRÍTICO] Dejar SQLite** y migrar a MySQL o PostgreSQL (el bloque MySQL ya está comentado en `settings.py`). SQLite no maneja bien escrituras concurrentes (varios kioscos + dashboard al mismo tiempo).
- Usuario de BD **dedicado con contraseña fuerte desde variable de entorno** — no `root` / `Passw0rd1` como está en el bloque comentado.
- La BD debe escuchar **solo en localhost** (o red privada de DO), nunca expuesta a internet.
- **Backups automáticos**: dump diario + copia fuera del droplet (DO Spaces o similar):
  ```bash
  mysqldump gymaccess_db | gzip > backup_$(date +%F).sql.gz
  ```

---

## 3. Servidor de aplicación

- **[CRÍTICO] Nunca usar `runserver` en producción.** Usar gunicorn detrás de nginx:
  ```bash
  pip install gunicorn
  gunicorn gymaccess.wsgi:application --bind 127.0.0.1:8000 --workers 3
  ```
  (regla práctica: workers = 2 × núcleos + 1)
- Correr gunicorn como **servicio systemd** (reinicio automático si se cae o al rebootear el droplet).
- Correr como **usuario sin privilegios**, nunca root.
- **nginx delante** sirviendo:
  - `/static/` y `/media/` directamente (Django no debe servir archivos en producción; ejecutar `python manage.py collectstatic`).
  - Proxy a gunicorn para `/api/`.
  - El build de React (`npm run build`) como archivos estáticos.

### Rate limiting también en nginx (primera línea, antes de llegar a Django)
```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=login:10m rate=1r/s;

server {
    location /api/auth/ { limit_req zone=login burst=5 nodelay; proxy_pass http://127.0.0.1:8000; }
    location /api/      { limit_req zone=api   burst=20 nodelay; proxy_pass http://127.0.0.1:8000; }
    client_max_body_size 5M;
}
```
Esto complementa el throttling de DRF ya implementado: nginx descarta el exceso sin gastar CPU de Python.

---

## 4. Throttling de DRF (ya implementado en el código)

Ya configurado en `settings.py`: login/refresh 10/min por IP, check-in 60/min, usuarios 300/min, anónimos 30/min.

- **Pendiente para producción con varios workers**: los contadores usan caché local en memoria (por proceso). Con gunicorn y 3 workers, cada worker cuenta por separado (el límite real se triplica). Solución: Redis como caché compartida:
  ```python
  CACHES = {
      'default': {
          'BACKEND': 'django.core.cache.backends.redis.RedisCache',
          'LOCATION': 'redis://127.0.0.1:6379/1',
      }
  }
  ```
  (`apt install redis-server`; Redis solo en localhost.)

---

## 5. Firewall y acceso al droplet

- **[CRÍTICO] Firewall**: solo abrir 22 (SSH), 80 y 443. Todo lo demás cerrado (MySQL, Redis, gunicorn:8000 solo en localhost):
  ```bash
  ufw default deny incoming
  ufw allow OpenSSH
  ufw allow 80,443/tcp
  ufw enable
  ```
  O mejor: **DO Cloud Firewall** (panel de Digital Ocean), que filtra antes de que el tráfico llegue al droplet.
- **SSH**: solo con llave (deshabilitar `PasswordAuthentication` en `/etc/ssh/sshd_config`), y **fail2ban** para banear IPs que intenten fuerza bruta:
  ```bash
  apt install fail2ban
  ```
- Mantener el sistema actualizado: `apt update && apt upgrade` periódico, o `unattended-upgrades`.

---

## 6. Cloudflare — protección contra DDoS volumétrico y amplificación DNS

### ¿Se instala en el droplet? — NO
Cloudflare **no es un software que se instala en el servidor**: es un servicio que se coloca
**delante** del droplet a nivel DNS. Todo el tráfico de internet pasa primero por la red global de
Cloudflare, que absorbe los ataques volumétricos (cientos de Gbps) **antes de que un solo paquete
llegue a Digital Ocean**. Eso es algo que nada instalado dentro del droplet puede lograr, porque un
DDoS volumétrico satura el enlace de red del droplet, no su CPU.

Bonus: como el DNS lo gestiona Cloudflare, los ataques de **amplificación DNS contra tu dominio**
también los absorbe su infraestructura, no tu servidor.

### Cómo activarlo (plan gratuito, suficiente para esto)
1. Crear cuenta en cloudflare.com y **agregar tu dominio** (necesitas un dominio; con solo la IP del droplet no funciona).
2. Cloudflare te da 2 **nameservers** — cámbialos en donde compraste el dominio (GoDaddy, Namecheap, etc.).
3. En Cloudflare, crear el registro DNS apuntando al droplet **con el proxy activado (nube naranja)**:
   ```
   A    tudominio.com      -> IP_DEL_DROPLET   (Proxied ☁️ naranja)
   A    api.tudominio.com  -> IP_DEL_DROPLET   (Proxied ☁️ naranja)
   ```
   La nube naranja es lo que activa la protección; en gris solo hace DNS y no te protege.
4. **SSL/TLS → modo "Full (strict)"** y generar un *Origin Certificate* de Cloudflare para instalarlo en nginx (o usar Let's Encrypt en el droplet). Nunca usar modo "Flexible".
5. **[CRÍTICO] Ocultar la IP de origen**: si el atacante conoce la IP real del droplet, puede atacarla directo saltándose Cloudflare. Por eso:
   - Configurar el firewall (ufw o DO Cloud Firewall) para aceptar tráfico en 80/443 **solo desde los rangos de IP de Cloudflare** (lista oficial: https://www.cloudflare.com/ips/).
   - Si la IP del droplet ya fue pública con el dominio, considerar recrear el droplet o pedir IP nueva (una IP ya conocida sigue siendo atacable).
6. En Cloudflare activar:
   - **Bot Fight Mode** (gratis) — filtra bots automáticos.
   - **Rate limiting rules** (capa extra a la de nginx y DRF).
   - **"Under Attack Mode"** — botón de pánico si estás recibiendo un ataque activo.

### Resultado: defensa en 4 capas
| Capa | Detiene |
|---|---|
| 1. Cloudflare (fuera del droplet) | DDoS volumétrico, amplificación DNS, bots |
| 2. Firewall DO/ufw | Todo lo que no venga de Cloudflare por 80/443 |
| 3. nginx (`limit_req`) | Floods HTTP que pasen la capa 1 |
| 4. Throttling DRF (ya implementado) | Fuerza bruta de login, abuso con credenciales |

Nota: Digital Ocean incluye una mitigación DDoS básica gratuita a nivel de su red, pero no
sustituye a Cloudflare — es protección de "mejor esfuerzo" para la infraestructura de DO,
sin las reglas configurables ni la capacidad de absorción de una CDN global.

---

## 7. Frontend (React)

- Compilar para producción: `npm run build` y servir el resultado con nginx (no `npm run dev`).
- Apuntar la URL base de la API (`frontend/src/api/axios.js`) al dominio de producción vía variable de entorno de Vite (`VITE_API_URL`), no hardcodeada.
- Los tokens JWT viven en `localStorage`: aceptable por ahora, pero cualquier XSS podría leerlos. Mejora futura: cookies `httpOnly` + CSRF.

---

## 8. Logging y monitoreo

- Configurar `LOGGING` en Django para escribir errores a archivo (`/var/log/gymaccess/`) con rotación (`logrotate`).
- Monitorear los 429 (rate limit) y 401 repetidos: son la señal temprana de un ataque.
- Alertas de uptime gratuitas: UptimeRobot o el monitoring integrado de Digital Ocean (CPU, RAM, disco).
- Sentry (plan gratuito) para enterarte de errores 500 en producción sin revisar logs a mano.

---

## 9. Datos sensibles y cumplimiento

- Las **huellas** se guardan como templates en `MetodoAcceso.token`: son dato biométrico (dato personal sensible según la LFPDPPP en México). Mínimo: BD cifrada en reposo, acceso restringido y aviso de privacidad para los socios.
- Fotos de socios en `/media/`: nginx no debe listar directorios y conviene servirlas solo a usuarios autenticados si se vuelve requisito.
- No subir `db.sqlite3` ni `/media/` al repositorio.

---

## 10. Checklist rápido pre-lanzamiento

- [ ] `DEBUG = False`
- [ ] `SECRET_KEY` nueva y en variable de entorno
- [ ] `ALLOWED_HOSTS` y CORS restringidos al dominio real
- [ ] HTTPS forzado + HSTS + cookies seguras
- [ ] `python manage.py check --deploy` sin advertencias
- [ ] MySQL/PostgreSQL con usuario dedicado, solo localhost
- [ ] gunicorn + nginx + systemd (no runserver)
- [ ] `collectstatic` y build de React servidos por nginx
- [ ] Redis para caché de throttling (si hay más de 1 worker)
- [ ] ufw / DO Cloud Firewall: solo 22, 80, 443 — y 80/443 solo desde IPs de Cloudflare
- [ ] SSH solo con llave + fail2ban
- [ ] Cloudflare activo con proxy (nube naranja) y SSL Full (strict)
- [ ] Backups automáticos de BD fuera del droplet
- [ ] Logs con rotación + monitoreo de uptime
