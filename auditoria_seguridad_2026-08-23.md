# Auditoría de seguridad — 23 de agosto de 2026

Complementa `consideraciones_produccion.md`, que sigue vigente: ese documento cubre
la **infraestructura** (servidor, TLS, firewall, backups). Éste cubre lo que aquel no
mira, que es **el código**: permisos, aislamiento entre inquilinos y endpoints.

Todo lo marcado como *verificado* se ejecutó contra la API corriendo, no se dedujo
leyendo. Los artefactos de prueba se borraron al terminar (ver «Rastro de la auditoría»).

**Resumen: la infraestructura estaba bien pensada; la capa de autorización no.** Ningún
hallazgo crítico se arregla con nginx, TLS ni Cloudflare — todos se explotan con un
token legítimo y peticiones HTTP normales.

---

## ESTADO — arreglado el mismo día

| Hallazgo | Estado | Dónde |
|---|---|---|
| 1 · Escalada a superadmin | ✅ | `usuarios/serializers.py::_validar_autoridad` |
| 2 · `gym` escribible | ✅ | ídem |
| 3 · Escritura cruzada (sucursal, plan, gasto) | ✅ | `gyms/views.py`, `socios/views.py` |
| 4 · Borrado del gym en cascada | ✅ | `gyms/views.py` (sin `destroy` ni `create`) |
| 5 · Contraseñas sin validar | ✅ | `validate_password` + 4 validadores |
| 6 · La suspensión no suspendía | ✅ | `usuarios/authentication.py` (nuevo) |
| 7 · Admin de gym como superusuario Django | ✅ | migración `usuarios/0006` + `DJANGO_ADMIN_URL` |
| 8 · Check-in ignoraba `socio.activo` | ✅ | `accesos/views.py::CheckInView` |
| 9 · Cancelar datos no cerraba la puerta | ✅ | `MetodoAccesoViewSet` a solo lectura + `AsignarQRView` |
| 10 · JWT irrevocables | ⚠️ parcial | access 8 h → 1 h y `token_blacklist` instalada; **rotación apagada** hasta arreglar el bucle de refresh del frontend |
| 11 · Token QR predecible | ✅ | `accesos/models.py::generar_token_qr` (`secrets`) |
| 12 · Fotos sin autenticar | ❌ | pendiente, se resuelve en nginx |
| 13 · Throttle por proceso | ❌ | pendiente, necesita Redis |
| 14 · CORS abierto por defecto | ✅ | falla cerrado con `DEBUG=False` |
| 15 · SECRET_KEY con fallback | ✅ | `ImproperlyConfigured` si falta |
| 16 · `X-Forwarded-For` falsificable | ✅ | `legal/views.py::ip_de` + `DJANGO_TRAS_PROXY` |

**Verificación**: 417 tests en verde, de los cuales 19 son nuevos y específicos de estos
hallazgos (`usuarios/tests_seguridad.py`). Corren contra SQLite y contra PostgreSQL 17
real dentro del contenedor. El exploit original se reprodujo contra el stack ya
arreglado: `403 → PATCH 400 → 403`.

Un test que afirmaba el comportamiento roto (`test_socio_dado_de_baja_..._entra`, cuyo
docstring decía «documenta el comportamiento actual») se invirtió en vez de borrarse.

---

## Lo primero, porque cambia el orden de todo lo demás

El sistema es **multi-inquilino**: un solo despliegue sirve a varios gimnasios que son
negocios distintos y competidores entre sí. Eso convierte cualquier fuga entre gyms en
un incidente con datos personales de terceros (LFPDPPP), no en un bug de permisos.

Y hay tres fronteras, no una:

| Frontera | Qué separa | Estado |
|---|---|---|
| Gym ↔ Gym | Round3Boxing de sus competidores | **rota** (hallazgos 1–4) |
| Dueño del SaaS ↔ dueño de un gym | tú de tus clientes | **rota** (hallazgo 1) |
| Sucursal ↔ Sucursal | Estrella de San Sebastián | sólida (`SucursalScopedMixin`) |

El scoping por sucursal está bien hecho y bien razonado. El scoping por gym se dejó
implícito en los `get_queryset` y nadie cerró la escritura.

---

## CRÍTICOS

### 1. Cualquier admin de gym se asciende a superadmin y se queda con el SaaS entero

`UsuarioSerializer` (`usuarios/serializers.py:35`) expone `rol` como campo escribible, y
`UsuarioViewSet` sólo exige `EsAdminGym`. El admin de un gimnasio está dentro de su
propio `get_queryset`, así que **puede editarse a sí mismo**.

Verificado, en tres peticiones y sin volver a iniciar sesión:

```
GET   /api/saas/resumen/                      -> 403   (correcto)
PATCH /api/usuarios/10/  {"rol":"superadmin"} -> 200   <-- aquí se rompe
GET   /api/saas/resumen/                      -> 200   con el MISMO token
```

El token ni siquiera hay que renovarlo: `EsSuperAdmin` lee `request.user.rol` de la base,
que JWTAuthentication acaba de cargar. El ascenso surte efecto en la siguiente petición.

Lo que se obtiene después:

```
GET  /api/saas/tenants/              -> lista de TODOS los clientes con su admin
POST /api/saas/tenants/3/impersonar/ -> JWT del dueño del gym vecino
GET  /api/socios/  (con ese JWT)     -> 200, datos personales de sus socios
```

Es decir: **el cliente que te paga una mensualidad puede volverse el dueño del SaaS,
suplantar a sus competidores y leer sus padrones de socios.** La bitácora `AccesoSoporte`
registra la suplantación, pero registra al atacante como si fuera soporte legítimo.

**Arreglo**: `rol` no puede ser un campo abierto. Nadie se edita el propio rol, y sólo un
superadmin puede otorgar `superadmin`.

---

### 2. `gym` es escribible: el admin se muda al gimnasio de al lado

`perform_create` fuerza `gym_id` para quien no es superadmin, pero **`perform_update` no
existe**. El campo `gym` viaja en el serializer sin custodia.

Verificado:

```
PATCH /api/usuarios/10/  {"gym":3}  -> 200
GET   /api/gyms/  (mismo token)     -> 200, devuelve [(3, 'GymVecino AUDIT')]
```

A partir de ahí todo el scoping por gym trabaja *a su favor*: es un admin legítimo del
gym 3 y ve sus socios, sus pagos y su caja. No hace falta el hallazgo 1 para esto.

**Arreglo**: `gym` de sólo lectura salvo para superadmin, y validar en `perform_update`.

---

### 3. Escritura cruzada: crear sucursales y planes dentro de otro gimnasio

`SucursalViewSet` y `PlanViewSet` filtran la **lectura** por gym pero no tienen
`perform_create`, y sus serializers son `fields = '__all__'` con `gym` escribible.

Verificado desde el admin del gym 1:

```
POST /api/gyms/sucursales/  {"nombre":"Sucursal inyectada","gym":3}  -> 201
POST /api/socios/planes/    {"nombre":"Plan inyectado","gym":3,...}  -> 201
```

El registro se crea en el negocio ajeno y **desaparece de la vista de quien lo creó**
(su `get_queryset` lo excluye), así que el atacado lo ve aparecer en su catálogo sin
explicación. Es el mismo agujero que `MembresiaViewSet._validar_pertenencia` ya tapó
para socio/plan/sucursal: el patrón correcto ya existe en el código, sólo no se aplicó aquí.

`GastoViewSet.perform_update` tiene la misma forma (valida al crear, no al editar).

---

### 4. El dueño de un gym puede borrar su gimnasio entero, con la contabilidad dentro

`GymViewSet` usa `AdminOSoloLectura`, que permite cualquier método a un `admin`. `DELETE`
incluido. `Gym` cae en cascada sobre sucursales, socios, membresías, **pagos**, accesos y
usuarios.

Verificado contra un gym desechable:

```
DELETE /api/gyms/3/  -> 204
gyms que quedan: [(1, 'Round3Boxing')]
usuarios del gym 3 que quedan: 0
```

Esto **contradice directamente** la decisión ya tomada en el panel del SaaS, donde el
DELETE está prohibido y responde explicando que de un gym cuelgan pagos que el CFF
obliga a conservar cinco años (`saas/views.py:80`). Se cerró la puerta del panel y se
dejó abierta la del inquilino, que es la que un cliente enfadado usaría.

**Arreglo**: `GymViewSet` sin `destroy`, y `SucursalViewSet` a baja lógica (`activa=False`).

---

### 5. Las contraseñas no se validan: `"1"` es una contraseña aceptada

`AUTH_PASSWORD_VALIDATORS` está configurado, pero **nunca se ejecuta**: `UsuarioSerializer`
declara `password` como un `CharField` suelto y llama a `set_password()` a mano, sin pasar
por `validate_password()`. Los validadores de Django sólo corren si alguien los invoca.

Verificado:

```
POST /api/usuarios/   {"password":"1", ...}  -> 201
POST /api/auth/login/ {"password":"1", ...}  -> 200  (entra)
```

Con throttle de 10/min por IP, una contraseña de un carácter cae al primer intento.
Y `AUTH_PASSWORD_VALIDATORS` sólo tiene `MinimumLengthValidator`: aunque se ejecutara,
faltan el de contraseñas comunes y el de similitud con el usuario.

---

### 6. Suspender a un cliente moroso no lo suspende

Es la única palanca comercial del panel SaaS y no corta nada. `Gym.activo = False` sólo
saca al gym de `GymViewSet.get_queryset`; el resto de los ViewSets filtran por `gym_id`
sin mirar `gym.activo`, y el login no lo consulta.

Verificado con el gym 1 suspendido:

```
POST /api/saas/tenants/1/suspender/  -> 200
GET  /api/socios/    (recepción)     -> 200   sigue trabajando
POST /api/auth/login/                -> 200   sigue entrando
```

El cliente que dejó de pagar sigue operando con normalidad; lo único que pierde es la
pantalla de configuración del gym.

**Arreglo**: rechazar la autenticación de usuarios cuyo gym esté inactivo. Un solo punto
(`LoginSerializer.validate` más una comprobación en el permiso base) cubre todos los endpoints.

---

### 7. El admin de un gimnasio es superusuario de Django

```
admin@admin.com          rol=superadmin  gym=None  is_staff=True  is_superuser=True
diego@round3boxing.com   rol=admin       gym=1     is_staff=True  is_superuser=True
```

`is_superuser=True` en el dueño de **un** gimnasio le da el panel `/admin/` sobre **todos**
los modelos de **todos** los inquilinos, saltándose por completo la capa de permisos que
audita este documento. `/admin/login/` responde 200 y su formulario **no pasa por el
throttling de DRF** (los límites de `REST_FRAMEWORK` sólo aplican a vistas DRF), así que
además es la superficie de fuerza bruta menos protegida del sistema.

**Arreglo**: `is_staff=is_superuser=False` para todo lo que no sea el dueño del SaaS;
mover el admin a una ruta no adivinable y, mejor, no exponerlo a internet.

---

## ALTOS

### 8. El check-in ignora `socio.activo`

Ya verificado y documentado por separado: un socio dado de baja con membresía vigente
entra (`acceso: permitido`). `CheckInView` no mira `socio.activo` en ningún punto.
El `motivo_denegado='suspendido'` existe en el modelo y ningún código lo escribe.

### 9. Cancelar los datos de un socio no le cierra la puerta de forma estable

Dos caminos deshacen `cancelar_datos`:

- **Recepción puede reactivar el QR.** `MetodoAccesoViewSet` es un `ModelViewSet` completo
  con sólo `IsAuthenticated`, sin `perform_create` ni validación de gym.
  Verificado: `PATCH /api/accesos/metodos/18/ {"activo":true}` como recepción → **200**.
- **«Asignar QR» le crea uno nuevo.** `AsignarQRView` busca un QR `activo=True`, no
  encuentra ninguno (la cancelación los apagó) y **crea uno nuevo, activo**.

Encontrado en la base real: el socio 18, con los datos cancelados, **tenía un segundo QR
activo** (`R3B-QR-00018-4871`) creado después de la cancelación, y un acceso permitido
registrado hoy. La cancelación de datos se deshizo sola.

Además `MetodoAccesoSerializer` es `__all__`: `socio` y `token` son escribibles, así que
un empleado puede fijar el token que quiera o apuntarlo al socio de otro gym.

### 10. Los JWT no se pueden revocar

`SIMPLE_JWT` no incluye `token_blacklist`. Un access token vive 8 h y un refresh 7 días,
y **no hay forma de invalidarlos**: ni al dar de baja a un empleado (su access sigue
sirviendo hasta 8 h), ni al cerrar una sesión de soporte, ni si un token se filtra.
Combinado con el hallazgo 1, un atacante que se ascendió conserva su token aunque le
reviertan el rol.

**Arreglo mínimo**: bajar `ACCESS_TOKEN_LIFETIME` a 30–60 min (ya recomendado en
`consideraciones_produccion.md`) y añadir `rest_framework_simplejwt.token_blacklist`.

---

## MEDIOS

| # | Hallazgo | Detalle |
|---|---|---|
| 11 | **Token QR predecible** | `R3B-QR-{socio.id:05d}-{random(1000,9999)}`: 9 000 combinaciones por socio, con el id secuencial. No lo explota un anónimo (el check-in exige token de empleado) pero sí cualquier empleado, y el formato se lee en la credencial impresa. Usar `secrets.token_urlsafe(16)`. |
| 12 | **Fotos de socios sin autenticar** | `/media/` se sirve por URL directa. Quien adivine o filtre la ruta ve la foto de un socio sin sesión. En producción `static()` no sirve nada y hay que resolverlo en nginx (`internal` + `X-Accel-Redirect`) si se quiere restringir. |
| 13 | **Throttle en memoria por proceso** | Ya anotado en `consideraciones_produccion.md`: con 3 workers de gunicorn el límite real se triplica. Necesita Redis. |
| 14 | **CORS abierto si falta la variable** | `settings.py:135`: sin `DJANGO_CORS_ORIGINS` cae en `CORS_ALLOW_ALL_ORIGINS = True`. El default inseguro debería ser al revés: fallar si no está definida cuando `DEBUG=False`. |
| 15 | **SECRET_KEY con fallback embebido** | `os.environ.get(...)` con la llave de desarrollo como valor por defecto: si la variable no se exporta, el servidor arranca igual y firma tokens con una llave que está en el repo. Debe ser `os.environ['DJANGO_SECRET_KEY']`, que revienta el arranque. |
| 16 | **`X-Forwarded-For` sin filtrar** | `legal/views.py:ip_de` toma el primer valor de la cabecera tal cual. Es correcto detrás de nginx, pero **falsificable** por el cliente: la evidencia de consentimiento (LFPDPPP) y la bitácora de soporte guardan la IP que el atacante quiera. Hay que confiar sólo en el último salto conocido. |

---

## Lo que está bien y conviene no romper

- **Sin SQL crudo en todo el backend**: cero `.raw()`, `.extra()` y `cursor()`. No hay superficie de inyección SQL.
- **`.gitignore` correcto**: `.env`, `*.sqlite3`, `backups/` y `backend/media/` excluidos. `git ls-files` no devuelve ningún secreto versionado.
- **Dependencias al día**: Django 6.0.6, DRF 3.17.1, simplejwt 5.5.1, Pillow 12.2.0.
- **Scoping por sucursal**: `SucursalScopedMixin` valida lectura *y* escritura, y `sucursal_solicitada()` ignora el `?sucursal=` de quien está atado a una. Es el modelo a copiar para arreglar el scoping por gym.
- **Endpoints cerrados sin token**: `/api/socios/` y `/api/saas/resumen/` responden 401.
- **Throttling diferenciado ya pensado**: login 10/min, autorización 5/min, check-in 60/min.
- **Bitácoras que existen porque alguien pensó en la auditoría**: `AjusteMembresia`, `AccesoSoporte`, `ConsentimientoSocio`.

---

## Sobre la base de datos

**No está segura, pero no por SQLite en sí.** El riesgo real está por encima:

1. Los hallazgos 1–4 permiten leer y escribir datos de otro inquilino **usando la API tal
   como está diseñada**. Cifrar el disco o cambiar a PostgreSQL no cambia nada de eso.
2. `db.sqlite3` es un archivo: cualquiera con acceso al sistema de archivos del droplet
   (o a un backup mal guardado) se lo lleva entero, con los hashes de contraseñas y los
   datos personales de todos los socios. Con MySQL/PostgreSQL al menos hay autenticación
   de por medio.
3. **Datos biométricos en claro**: `MetodoAcceso.token` guarda el template de la huella
   sin cifrar, y es dato personal *sensible* según la LFPDPPP — el nivel que exige
   consentimiento expreso y medidas reforzadas. Hoy lo lee cualquier empleado por
   `GET /api/accesos/metodos/`.
4. SQLite además no aguanta la concurrencia de varios kioscos escribiendo a la vez
   (`database is locked`), que es el punto que ya levantaba `consideraciones_produccion.md`.

---

## Qué falta para producción, por archivo

`consideraciones_produccion.md` cubre servidor, TLS, firewall, Cloudflare y backups. Lo
que hay que tocar **en el repositorio**, además de `.env` y `settings.py`:

| Archivo | Cambio | Por qué |
|---|---|---|
| `usuarios/serializers.py` | `rol` y `gym` controlados; `validate_password` en `password` | Hallazgos 1, 2, 5 |
| `usuarios/views.py` | `perform_update` que valide gym y rol; prohibir editarse el propio rol | Hallazgos 1, 2 |
| `usuarios/permissions.py` | Permiso base que rechace usuarios de gym inactivo | Hallazgo 6 |
| `gyms/views.py` | Quitar `destroy` de `GymViewSet`; `perform_create/update` en `SucursalViewSet` | Hallazgos 3, 4 |
| `gyms/serializers.py` | `gym` de sólo lectura en `SucursalSerializer` | Hallazgo 3 |
| `socios/views.py` | `perform_create` en `PlanViewSet`; `perform_update` en `GastoViewSet` | Hallazgo 3 |
| `accesos/views.py` | Validar `socio.activo` en el check-in; validar gym en `MetodoAccesoViewSet`; `secrets` para el token QR | Hallazgos 8, 9, 11 |
| `accesos/serializers.py` | `socio` y `token` de sólo lectura | Hallazgo 9 |
| `legal/views.py` | `ip_de` que no confíe en la cabecera cruda | Hallazgo 16 |
| `gymaccess/urls.py` | Mover `/admin/` a una ruta no adivinable | Hallazgo 7 |
| `gymaccess/settings.py` | SECRET_KEY sin fallback; CORS que falle cerrado; JWT más corto y con blacklist; validadores de contraseña; cabeceras de seguridad | Hallazgos 5, 10, 14, 15 |
| `frontend/src/api/axios.js` | URL base por `VITE_API_URL` | Ya anotado en el doc de producción |
| *(nuevo)* `.env.example` | Plantilla de las variables sin valores | Hoy no hay forma de saber qué exportar |
| *(nuevo)* migración de datos | `is_staff=is_superuser=False` salvo el dueño del SaaS | Hallazgo 7 |
| *(nuevo)* tests | Uno por hallazgo crítico | Sin test, el arreglo se revierte en el próximo refactor |

### Salida de `manage.py check --deploy`

Con `DJANGO_DEBUG=0`, Django señala 5 avisos por su cuenta: falta `SECURE_HSTS_SECONDS`,
`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE` y `CSRF_COOKIE_SECURE`, y la `SECRET_KEY`
sigue siendo la `django-insecure-` autogenerada. Todos están cubiertos por el checklist
de `consideraciones_produccion.md`; ninguno de los críticos de este documento aparece ahí,
que es justo por qué esa herramienta no basta.

---

## Orden sugerido

1. **Antes de exponer nada a internet**: hallazgos 1, 2, 3, 4, 7 (el aislamiento entre
   inquilinos y el borrado en cascada). Son los que convierten un cliente en un incidente.
2. **Antes de cobrar la primera mensualidad**: hallazgo 6 (si no, no puedes cortarle a
   quien no paga) y hallazgo 5.
3. **Antes de que entre el primer socio real**: hallazgos 8 y 9 (la puerta).
4. Después: 10–16, más el checklist de infraestructura que ya estaba escrito.

---

## Rastro de la auditoría

Todo se ejecutó contra la base de desarrollo (`backend/db.sqlite3`). Creado y **borrado**
al terminar: usuarios `audit.admin@round3boxing.com` (id 10) y `debil@round3boxing.com`
(id 12); gym «GymVecino AUDIT» (id 3) con su sucursal, su admin y el plan inyectado —el
gym lo eliminó la propia prueba del hallazgo 4 y el resto cayó en cascada—.

La base quedó con **1 gym, 2 sucursales, 8 usuarios y 1 plan**, igual que antes.

Dos cosas que no quedaron exactamente como estaban, y conviene saberlo:

- **Se borró un registro de acceso preexistente del socio 18** (una entrada permitida de
  hoy). Se eliminó junto con el acceso que generó la prueba del hallazgo 9, al no haberlos
  distinguido antes de borrar. No se recreó: inventar una fila en una bitácora es peor que
  la fila que falta.
- **El socio 25 («ZZTest Inactivo», San Sebastián) sigue en la base** a propósito, para
  volver a probar el arreglo del hallazgo 8.

El QR del socio 18 se dejó como se encontró: el método 18 inactivo y **el método 24
activo**, que es precisamente el hallazgo 9. No se «arregló» a mano porque la decisión
sobre un socio con los datos cancelados es del negocio, no de la auditoría.
