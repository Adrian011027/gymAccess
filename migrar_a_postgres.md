# Migrar los datos de SQLite a Postgres

Pasos verificables. **Hay datos reales de Round3Boxing en `backend/db.sqlite3`**, así
que el orden importa: nada se borra hasta que los conteos cuadren.

---

## 1. Respaldo (antes que nada)

```bash
cp backend/db.sqlite3 backend/db.sqlite3.antes-de-postgres
```

Es la única copia. `*.sqlite3` está en `.gitignore`, así que no viaja al repo.

## 2. Poner al día la base SQLite antes de exportar

```bash
cd backend
python manage.py migrate --noinput
```

Parece innecesario —la base vieja "ya funciona"— pero `dumpdata` recorre **todos** los
modelos instalados, y `token_blacklist` se añadió a `INSTALLED_APPS` sin que sus
tablas existieran todavía en SQLite. Sin este paso el volcado muere con:

```
CommandError: Unable to serialize database: no such table: token_blacklist_blacklistedtoken
```

De paso aplica la migración `usuarios.0006`, que quita `is_superuser` a los admins de
gimnasio (hallazgo 7 de la auditoría).

## 3. Exportar desde SQLite

```bash
PYTHONUTF8=1 python manage.py dumpdata \
  --natural-foreign --natural-primary \
  --exclude contenttypes --exclude auth.permission \
  --exclude admin.logentry --exclude sessions.session \
  --exclude token_blacklist \
  --indent 2 -o ../datos_sqlite.json
```

**`PYTHONUTF8=1` no es opcional en Windows.** Sin él, `-o` escribe el archivo en la
codificación local (cp1252) y el volcado deja de ser UTF-8 válido. El fallo no
aparece al exportar sino mucho después, al importar, y con un mensaje que no señala
la causa:

```
UnicodeEncodeError: 'utf-8' codec can't encode character '\udce9' ... surrogates not allowed
```

`\udce9` es lo que queda de una `é`. Con datos en español —«Términos y Condiciones»,
«San Sebastián», «Núñez»— esto afecta a media base. Comprobado en esta migración: el
primer volcado salió con `T\xe9rminos` y hubo que rehacerlo.

`--exclude token_blacklist` porque son tokens de sesión: caducan solos y no tiene
sentido arrastrarlos.

Las demas exclusiones y las dos banderas tampoco son adorno:

| Qué | Por qué |
|---|---|
| `--exclude contenttypes` | Django los crea solos al migrar. Si además se importan, los ids chocan y `loaddata` muere con `IntegrityError` en la primera fila. Es el error más común de esta migración. |
| `--exclude auth.permission` | Igual: se generan en `migrate` a partir de los modelos. |
| `--natural-foreign --natural-primary` | Hace que las referencias viajen por su clave natural (el `app.modelo` del content type) en vez de por un id que en la base nueva será otro. |
| `--exclude admin.logentry` | Cuelga de contenttypes; sin él arrastra el problema de arriba. |
| `--exclude sessions.session` | Sesiones caducadas; nadie las echa de menos y traen basura. |

`datos_sqlite.json` ya está en `.gitignore` — **contiene hashes de contraseñas y datos
personales de socios**. Borrarlo cuando termine la migración.

## 4. Levantar Postgres y migrar el esquema

```bash
cp .env.example .env    # y rellenar SECRET_KEY, POSTGRES_PASSWORD, dominios
docker compose up -d db
docker compose run --rm backend python manage.py migrate --noinput
```

`migrate` crea las tablas vacías y, con ellas, los contenttypes y permisos que
acabamos de excluir del dump.

## 5. Importar

```bash
docker compose exec -T backend python manage.py loaddata --format=json - < datos_sqlite.json
```

Se pasa por **stdin** y no copiando el archivo al contenedor: `loaddata /tmp/datos.json`
responde `No fixture named 'datos' found` aunque el archivo esté ahí y sea legible
—trata el argumento como nombre de fixture, no como ruta—. Por stdin no hay ambigüedad
y además no deja una copia con datos personales dentro del contenedor.

`loaddata` reajusta las secuencias de Postgres al final, así que el siguiente socio
que se dé de alta no choca con un id ya usado. (Ese sí es un paso manual en una
migración hecha a mano, y es la segunda causa clásica de que "todo funcionó y al día
siguiente reventó".)

## 6. Verificar antes de confiar

Contar filas por tabla en las dos bases y comparar. **No basta con que `loaddata` no
dé error**: puede importar de menos si el dump se generó a medias.

```bash
docker compose exec -T backend python manage.py shell -c "
from django.apps import apps
for m in sorted(apps.get_models(), key=lambda m: m._meta.label):
    if m._meta.app_label in ('contenttypes','auth','admin','sessions','token_blacklist'):
        continue
    print(f'{m._meta.label:40} {m.objects.count()}')
"
```

Correr lo mismo contra SQLite (sin `docker compose`, con el venv) y comparar línea a
línea. Deben coincidir **todas**.

Comprobaciones concretas de este negocio, que es lo que de verdad dice si migró bien:

```bash
# Los socios, sus membresías vigentes y la caja del mes
docker compose exec -T backend python manage.py shell -c "
from socios.models import Socio, Membresia, Pago
print('socios:', Socio.objects.count())
print('vigentes:', Membresia.objects.vigentes().count())
print('pagos:', Pago.objects.count(), '| suma:', sum(p.monto for p in Pago.objects.all()))
"
```

Y una prueba de extremo a extremo: iniciar sesión y hacer un check-in real. Si el
login da 200 y la puerta responde, las contraseñas viajaron bien (los hashes son
texto y no se corrompen, pero conviene verlo antes que descubrirlo el lunes).

## 7. Arrancar

```bash
docker compose up -d
curl -i http://127.0.0.1:8001/api/socios/     # 401 sin token = está vivo y cerrado
```

## 8. Limpiar

```bash
rm datos_sqlite.json
```

El respaldo `db.sqlite3.antes-de-postgres` se conserva hasta que el sistema lleve
unos días corriendo sobre Postgres sin sobresaltos.

---

## Lo que esta migración NO hace

- **No arregla ninguno de los hallazgos de seguridad.** Esos son cambios de código y
  van aparte (ya aplicados: ver `auditoria_seguridad_2026-08-23.md`).
- **No cifra el template de la huella.** `MetodoAcceso.token` sigue guardando dato
  biométrico en claro, que es dato personal *sensible* bajo la LFPDPPP. Postgres
  mejora el control de acceso al archivo, no el contenido de la columna.
- **No configura backups.** Postgres en un contenedor sin `pg_dump` programado fuera
  del droplet es tan frágil como el SQLite que sustituye. Ver
  `consideraciones_produccion.md`.
