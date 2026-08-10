# Casos de prueba manuales — GymAccess

**Fecha:** 10 de agosto de 2026
**Base:** hallazgos de `analisis_tests_2026-08-06.md`, reverificados contra el entorno vivo.

---

## 0. Entorno

| Servicio | URL |
|---|---|
| Backend Django | `http://127.0.0.1:8001` |
| Frontend Vite | `http://localhost:5173` |
| Endpoint de login | `POST /api/auth/login/` |

Arranque:

```bash
# backend (desde backend/)
../venv/Scripts/python.exe manage.py runserver 127.0.0.1:8001

# frontend (desde frontend/)
npm run dev
```

Credenciales:

| Rol | Email | Password |
|---|---|---|
| admin | `diego@round3boxing.com` | `Diego1234` |
| recepción | `recepcion@round3boxing.com` | `Recepcion123` |

> No uses el puerto 8000: lo ocupa el contenedor `saas_agenda_backend` de otro proyecto
> y en Windows `localhost` resuelve a `::1` primero. Todo lo que pegue a `localhost:8000`
> aterriza en la otra aplicación.

### Suite automatizada

```bash
cd backend
../venv/Scripts/python.exe manage.py test --settings=gymaccess.test_settings
```

Resultado verificado hoy: **249 tests · 8 expected failures · 0 fallos reales** (~6 min).
Los 8 *expected failures* son los bugs abiertos: la suite en verde **no** significa que
esos bugs estén arreglados.

### Datos de la BD al momento de escribir esto

Un solo gym (`Round3Boxing`, id 1) y una sucursal (`Matriz Centro`, id 1). Socios con
membresía **expirada pero con `estado='activa'`** — los conejillos de indias del bug #1:

| Socio | id | Plan | fecha_fin | Estado en BD |
|---|---|---|---|---|
| Carlos Ramírez | 1 | Regular | 2026-08-04 | `activa` |
| Ana | 2 | Estudiante | 2026-08-04 | `activa` |
| Luis | 3 | Pareja | 2026-07-29 | `activa` |
| Andrés | 11 | Regular | 2026-07-28 | `activa` |

Tokens QR útiles:

| Socio | Token | Situación |
|---|---|---|
| Carlos (id 1) | `R3B-QR-00001-4600` | vencido pero marcado activo |
| Sofía (id 4) | `R3B-QR-00004-2842` | vigente hasta 2026-10-03 |
| Valentina (id 6) | `R3B-QR-00006-1935` | `estado='vencida'` |

Helper para los casos por API:

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8001/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"diego@round3boxing.com","password":"Diego1234"}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['access'])")
```

---

## Bloque A — Bugs confirmados en vivo

### A1 · Membresía vencida se muestra como activa (bug #1, severidad alta)

1. Entra a `http://localhost:5173` como **admin**.
2. Ve a **Socios**.
3. Busca a **Carlos Ramírez**.

**Se observa hoy:** columna PLAN dice `Regular`, sin marca de vencimiento, aunque la
membresía terminó el 2026-08-04.
**Debería:** mostrarse como sin plan vigente o marcado como vencido.

Repite con Ana, Luis y Andrés — mismo comportamiento.

Comprobación por API:

```bash
curl -s http://127.0.0.1:8001/api/socios/ -H "Authorization: Bearer $TOKEN"
```

`membresia_activa` de Carlos viene poblado con `"fecha_fin": "2026-08-04", "estado": "activa"`.

---

### A2 · La lista y la puerta se contradicen (bug #2, severidad alta)

1. Con Socios abierto mostrando a Carlos como activo, ve a **Check-in**.
2. Ingresa el token `R3B-QR-00001-4600`, sucursal *Matriz Centro*.

**Se observa hoy:** `403` — "acceso denegado, membresía no activa".
**El problema:** la misma membresía es "activa" en una pantalla y "no activa" en la otra.

Contraste (los tres deben correrse seguidos para ver el patrón):

| Token | Socio | Resultado actual |
|---|---|---|
| `R3B-QR-00001-4600` | Carlos | `403` denegado ← contradice la lista |
| `R3B-QR-00004-2842` | Sofía | `200` permitido ← correcto |
| `R3B-QR-00006-1935` | Valentina | `403` denegado ← correcto |

---

### A3 · El moroso desaparece de cobranza (efecto combinado)

1. Ve a **Pagos → pestaña Atrasados**.
2. Busca a Carlos, Ana, Luis y Andrés.

**Se observa hoy:** ninguno aparece. `Pagos.jsx:60` filtra con
`m.fecha_fin < hoy && m.estado !== 'activa'`, y estas membresías siguen en `estado='activa'`.

Resultado neto: el socio no sale como moroso en Socios, no sale en Atrasados, y se entera
del problema cuando la puerta lo rechaza. **Este es el caso que cuesta dinero.**

---

### A4 · El filtro Activos/Inactivos no aísla morosos

1. En **Socios**, cambia el filtro a *Inactivos*.

**Se observa hoy:** lista vacía o solo bajas administrativas. `Socios.jsx:132` filtra por
`socio.activo`, no por el estado de la membresía. No hay forma de listar morosos desde esa
pantalla.

---

### A5 · Membresía futura ya cuenta como activa (bug #3, severidad media)

Preparación — crea una membresía que arranca la próxima semana:

```bash
cd backend
../venv/Scripts/python.exe -c "
import os,django,datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE','gymaccess.settings')
django.setup()
from socios.models import Membresia
from django.utils import timezone
hoy=timezone.localdate()
m=Membresia.objects.get(id=4)
m.pk=None
m.fecha_inicio=hoy+datetime.timedelta(days=7)
m.fecha_fin=hoy+datetime.timedelta(days=37)
m.estado='activa'
m.save()
print('membresia futura creada id',m.id,'socio',m.socio_id)
"
```

1. Abre **Socios** y busca al socio afectado (Sofía, id 4).
2. Manda check-in con `R3B-QR-00004-2842`.

**Se espera del bug:** la lista publica la membresía futura como vigente; el check-in la
rechaza por `fecha_inicio__lte=hoy`.

Limpieza: borra la membresía creada (`Membresia.objects.get(id=<nuevo_id>).delete()`).

---

### A6 · Escritura cruzada entre gyms en MembresiaViewSet (bug #4, severidad alta)

**Este es el hallazgo de seguridad más serio: fuga de aislamiento multitenant en escritura.**

Preparación — hace falta un segundo gym, hoy la BD solo tiene uno:

```bash
cd backend
../venv/Scripts/python.exe -c "
import os,django,datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE','gymaccess.settings')
django.setup()
from gyms.models import Gym, Sucursal
from socios.models import Socio, Plan
from django.utils import timezone
g,_=Gym.objects.get_or_create(nombre='GymRival QA')
s,_=Sucursal.objects.get_or_create(nombre='Rival Centro', gym=g)
soc,_=Socio.objects.get_or_create(nombre='Victima', apellido='Rival', gym=g)
p=Plan.objects.filter(gym=g).first() or Plan.objects.create(gym=g, nombre='Rival Mensual', precio=500, duracion_dias=30)
print('gym',g.id,'sucursal',s.id,'socio',soc.id,'plan',p.id)
"
```

Con los IDs que imprimió, autenticado como **admin de Round3Boxing** (gym 1):

```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8001/api/socios/membresias/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"socio":<ID_SOCIO_RIVAL>,"plan":<ID_PLAN_RIVAL>,"sucursal":<ID_SUCURSAL_RIVAL>,
       "fecha_inicio":"2026-08-10","fecha_fin":"2026-09-10","estado":"activa"}'
```

**Se espera del bug:** `201 Created`. El admin de un gym creó una membresía dentro del gym
de otro negocio. `socios/views.py:46-51` filtra el queryset de lectura por gym pero no
valida nada en la escritura.
**Debería:** `400` o `403`, como sí hace `PagoViewSet.perform_create` (`socios/views.py:62-64`).

Limpieza: borra la membresía creada y, si quieres, el gym `GymRival QA` con sus objetos.

---

### A7 · Check-in acepta sucursal de otro gym (bug #5, severidad media)

Con el gym rival del caso A6 ya creado, y su `sucursal_id`:

```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8001/api/accesos/checkin/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"token":"R3B-QR-00004-2842","sucursal_id":<ID_SUCURSAL_RIVAL>}'
```

**Se espera del bug:** `200` permitido. El acceso queda registrado contra la sucursal del
otro negocio y ensucia su bitácora y sus reportes. El token QR sí se valida contra el gym;
la sucursal no.
**Debería:** rechazar la sucursal por no pertenecer al gym del usuario.

Verifica el daño en **Reportes** y en la bitácora de accesos.

---

### A8 · Check-in sin sucursal revienta con 500 (bug #6, severidad baja)

```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8001/api/accesos/checkin/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"token":"R3B-QR-00004-2842"}'
```

**Se espera del bug:** `500` con
`IntegrityError: NOT NULL constraint failed: accesos.sucursal_id`.
**Debería:** `400` con mensaje claro.

En la UI esto pasa si el gym no tiene sucursales dadas de alta y el selector de
`CheckIn.jsx` queda vacío.

---

### A9 · POST a notificaciones revienta con 500 (bug #7, severidad baja)

```bash
curl -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8001/api/notificaciones/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"tipo":"pago_vencido","mensaje":"prueba"}'
```

**Se espera del bug:** `500`. El serializer marca `gym`/`tipo`/`mensaje` como read-only, la
validación pasa vacía y muere en el INSERT.
**Debería:** `405 Method Not Allowed` (quitar `'post'` de `http_method_names`).
**No hay fuga de datos:** la notificación nunca se crea. Confírmalo revisando la campanita.

---

### A10 · Superadmin sin gym da de alta un socio (bug #8, severidad baja)

Solo aplica a un superusuario **sin** `gym` asignado. Los dos usuarios del seed sí tienen
gym, así que este caso requiere crear uno:

```bash
cd backend
../venv/Scripts/python.exe -c "
import os,django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','gymaccess.settings')
django.setup()
from usuarios.models import Usuario
u=Usuario.objects.create_superuser(email='super@qa.local', password='SuperQA123', nombre='SuperQA')
u.gym=None; u.save()
print('creado', u.email)
"
```

Loguéate como `super@qa.local` / `SuperQA123` y crea un socio desde **Socios**.

**Se espera del bug:** `500`. La rama `else: serializer.save()` (`socios/views.py:33-37`)
choca con `Socio.gym` NOT NULL.

Limpieza: borra el usuario `super@qa.local` al terminar.

---

## Bloque B — Comportamientos a confirmar con el negocio

No son bugs necesariamente; pueden ser decisiones deliberadas. Corre los casos y decide.

### B1 · Dar de baja a un socio no le cierra la puerta

1. En **Socios**, marca a **Sofía** (id 4) como inactiva.
2. Manda check-in con `R3B-QR-00004-2842`.

**Se espera:** `200` permitido. El check-in solo mira la membresía, nunca `Socio.activo`.
**Pregunta al negocio:** ¿una baja administrativa debe bloquear el acceso?

Restaura a Sofía como activa al terminar.

### B2 · Recepción puede crear, editar y borrar clases

1. Cierra sesión y entra como **recepción**.
2. Ve a **Clases**. Crea una clase, edítala, bórrala.

**Se espera:** las tres operaciones funcionan. `ClaseViewSet` usa solo `IsAuthenticated`.
Contrasta: **Equipamiento** y **Gastos** sí están reservados a admin — verifica que
recepción no los vea o reciba `403`.

### B3 · El rol `coach` hereda permisos de recepción

`coach` no está en `ROLES_ADMIN`, así que tiene exactamente los mismos permisos que
recepción. Si existe un usuario coach, verifica que eso sea lo deseado.

### B4 · No hay validación de sobrecupo en clases

1. En **Clases**, crea una clase con `cupo_max = 2`.
2. Inscribe 3 o más socios.

**Se espera:** nada lo impide; `inscritos` supera a `cupo_max`.

### B5 · Notificaciones se purgan a los 15 días

El viewset purga solo las del gym del usuario al listar; el comando
`limpiar_notificaciones` barre todos los gyms. Verifica que la campanita no muestre nada
con más de 15 días.

---

## Bloque C — Regresión básica (debe seguir en verde)

| # | Caso | Esperado |
|---|---|---|
| C1 | Login admin desde el frontend | `200` + tokens JWT, entra al dashboard |
| C2 | Login recepción desde el frontend | `200`, entra sin acceso a Dashboard/Equipamiento/Reportes/Configuración |
| C3 | Login con password incorrecto | `401`, mensaje de credenciales inválidas |
| C4 | Check-in con token inexistente | `404` "Token inválido" |
| C5 | Check-in de socio vigente (Sofía) | `200` permitido, muestra plan y fecha de vencimiento |
| C6 | Check-in repetido muchas veces seguidas | El throttling `checkin` corta con `429` |
| C7 | Petición a `/api/socios/` sin token | `401` |
| C8 | Refresh token (`POST /api/auth/refresh/`) | `200` + nuevo access |
| C9 | Check-in denegado genera notificación | Campanita muestra "intentó ingresar con la membresía vencida" con link a `/pagos?tab=atrasados` |
| C10 | Dashboard, Reportes y bitácora cargan | Sin errores en consola, cifras coherentes con los accesos generados arriba |

Para C9, usa el token de Carlos (`R3B-QR-00001-4600`) y revisa la campanita enseguida.

---

## Orden sugerido

1. **C1–C10** primero: confirma que la base funciona.
2. **A1 → A2 → A3 → A4**: la cadena del bug #1, la que importa para cobranza. No requiere
   preparación de datos.
3. **A8, A9**: rápidos, solo curl.
4. **A5, A6, A7, A10**: requieren preparar y limpiar datos. Déjalos al final y **limpia
   después de cada uno**, sobre todo el gym rival de A6/A7.
5. **B1–B5**: conversación con el negocio, no arreglo inmediato.

## Después de arreglar un bug

Cada bug tiene su test marcado con `@unittest.expectedFailure`. Al arreglarlo, ese test
salta a *unexpected success* y la suite lo reporta — ahí se quita el decorador.
