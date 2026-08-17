# Plan de Regresión — GymAccess

> Documento de planeación. **Todavía no hay suite nueva escrita**: aquí está el inventario
> de módulos, los casos que hay que cubrir, y el reparto entre lo automático (yo) y lo
> manual (tú). La suite se construye después de que valides este plan.

Fecha: 2026-08-14 · Rama `main` · Commit base `9e861d9`

---

## Estado de avance (actualizado 2026-08-14, tras las 6 decisiones)

| | Al empezar | Ahora |
|---|---|---|
| Tests backend | 249 en 412 s | **289 en 7 s** |
| Cobertura backend (sin `seed_demo`) | 94 % | **96 %** |
| Tests frontend | 0 | **88** |
| Cobertura frontend | 0 % | **57 %** |

**Fases cerradas:** 0a (hasher), 0b (decisiones), 2 (comportamientos nuevos: coach,
anti-passback 4 h, fecha fija de cobro, socio inactivo bloquea), 3 (`marcar_membresias_vencidas`,
que estaba al 0 %), y la parte alta de 1 y 4 (infra Vitest+RTL+MSW, rutas×roles, CheckIn,
Pagos, Socios).

**Fases abiertas:** el resto de pantallas (Clases, Equipamiento, Notificaciones, Navbar,
Dashboard, Reportes, Configuración, Login), Playwright E2E, y la suite manual §8 cuando
llegue el lector QR.

**Decisiones tomadas** (§11 queda resuelto salvo lo que se pospuso):
1. Coach → aterriza en `/clases`, ve sólo sus clases en lectura, sin acceso a Pagos. `Clase.coach` migrado a llave real.
2. `clases_restantes` → **pospuesto** por decisión del dueño. Sigue siendo el hueco H1.
3. Anti-passback → **4 horas**, por socio, sólo cuentan los accesos permitidos.
4. Fecha de cobro → **fija por socio**, con 30 días de gracia antes de considerar reinscripción.
5. Socio `activo=False` → **no entra**, aunque tenga días pagados. Queda registrado como `suspendido`.
6. Orden → se descartó arrancar por el anillo de aislamiento: ya estaba cubierto al ~94 %.

---

## 1. Qué es este sistema, en una frase

Un SaaS multi-tenant de control de acceso y administración para gimnasios: Django 5 + DRF
con autenticación JWT en el backend, React 19 + Vite + Tailwind en el frontend, y un kiosco
de check-in que hoy funciona por teclado y mañana por lector QR.

**Multi-tenant** es la propiedad crítica: cada `Usuario` pertenece a un `Gym`, y *todo*
lo que se lee y se escribe debe quedar encerrado en ese gym. Si esa frontera se rompe,
un gimnasio ve los socios y el dinero de otro. Esa es la regresión más cara que existe
en este código, y por eso encabeza todas las listas de abajo.

---

## 2. Módulos

### 2.1 Backend — 5 apps Django, **14 módulos funcionales**

| # | Módulo | Ubicación | Superficie HTTP | Riesgo |
|---|--------|-----------|-----------------|--------|
| B1 | **Auth / JWT** | `usuarios/serializers.py::LoginSerializer`, `views.py::LoginView/RefreshView` | `POST /api/auth/login/`, `POST /api/auth/refresh/` | 🔴 Alto |
| B2 | **Usuarios y roles (RBAC)** | `usuarios/views.py::UsuarioViewSet`, `usuarios/permissions.py` | `/api/usuarios/` CRUD | 🔴 Alto |
| B3 | **Gyms y Sucursales** | `gyms/views.py::GymViewSet/SucursalViewSet` | `/api/gyms/`, `/api/gyms/sucursales/` | 🔴 Alto |
| B4 | **Clases** | `gyms/views.py::ClaseViewSet` | `/api/gyms/clases/` CRUD | 🟡 Medio |
| B5 | **Equipamiento** | `gyms/views.py::EquipamientoViewSet` | `/api/gyms/equipamiento/` CRUD | 🟡 Medio |
| B6 | **Planes** | `socios/views.py::PlanViewSet` | `/api/socios/planes/` CRUD | 🟠 Alto |
| B7 | **Socios** | `socios/views.py::SocioViewSet` | `/api/socios/` CRUD | 🔴 Alto |
| B8 | **Membresías** | `socios/views.py::MembresiaViewSet` + `MembresiaQuerySet.vigentes()` | `/api/socios/membresias/` CRUD | 🔴 Crítico |
| B9 | **Pagos** | `socios/views.py::PagoViewSet` | `/api/socios/pagos/` | 🔴 Crítico |
| B10 | **Gastos** | `socios/views.py::GastoViewSet` | `/api/socios/gastos/` | 🟠 Alto |
| B11 | **Métodos de acceso** | `accesos/views.py::MetodoAccesoViewSet`, `SincronizarHuellaView` | `/api/accesos/metodos/`, `/api/accesos/sincronizar-huella/` | 🔴 Alto |
| B12 | **Check-in (kiosco)** | `accesos/views.py::CheckInView` | `POST /api/accesos/checkin/` | 🔴 Crítico |
| B13 | **Accesos: historial + stats** | `accesos/views.py::AccesoViewSet/StatsView` | `/api/accesos/`, `/api/accesos/stats/` | 🟡 Medio |
| B14 | **Notificaciones** | `notificaciones/views.py::NotificacionViewSet` | `/api/notificaciones/` + acciones | 🟡 Medio |

Módulos transversales que no son endpoints pero sí rompen todo si cambian:

- **T1 — `MembresiaQuerySet.vigentes()`** (`socios/models.py`): la definición única de
  "este socio puede entrar hoy". La consumen el check-in (B12) y el serializer de Socios.
  Un cambio aquí mueve simultáneamente la puerta física y lo que ve recepción en pantalla.
- **T2 — `usuarios/permissions.py`**: `EsAdminGym` y `AdminOSoloLectura`. Dos clases de
  20 líneas que gobiernan quién escribe en 6 módulos.
- **T3 — Throttling** (`settings.py::DEFAULT_THROTTLE_RATES`): `login 10/min`,
  `checkin 60/min`, `anon 30/min`, `user 300/min`.
- **T4 — Comandos de mantenimiento**: `marcar_membresias_vencidas`, `limpiar_notificaciones`,
  `seed_demo`. Nadie los prueba hoy.

### 2.2 Frontend — **17 módulos** (12 pantallas + 5 transversales)

| # | Módulo | Archivo | Enrutado | Riesgo |
|---|--------|---------|----------|--------|
| F1 | **Login** | `pages/Login.jsx` | `/login` | 🔴 Alto |
| F2 | **AuthContext** (sesión, decode JWT, `isAdmin`) | `context/AuthContext.jsx` | transversal | 🔴 Crítico |
| F3 | **Cliente API** (interceptores, refresh 401) | `api/axios.js` | transversal | 🔴 Crítico |
| F4 | **Layout / guard de sesión** | `components/layout/Layout.jsx` | transversal | 🔴 Alto |
| F5 | **Router y guards por rol** | `App.jsx` (`HomeRedirect`, `AdminRoutes`) | transversal | 🔴 Alto |
| F6 | **Sidebar** (menú filtrado por rol) | `components/layout/Sidebar.jsx` | transversal | 🟠 Alto |
| F7 | **Navbar + campana de notificaciones** | `components/layout/Navbar.jsx` | transversal | 🟡 Medio |
| F8 | **Dashboard** | `pages/Dashboard.jsx` | `/dashboard` 🔒admin | 🟡 Medio |
| F9 | **Check-In (kiosco)** | `pages/CheckIn.jsx` | `/checkin` | 🔴 Crítico |
| F10 | **Socios** (alta, edición, huella, QR) | `pages/Socios.jsx` | `/socios` | 🔴 Crítico |
| F11 | **Clases** | `pages/Clases.jsx` | `/clases` | 🟡 Medio |
| F12 | **Equipamiento** | `pages/Equipamiento.jsx` | `/equipamiento` 🔒admin | 🟡 Medio |
| F13 | **Pagos** (cobros, atrasados, gastos) | `pages/Pagos.jsx` | `/pagos` | 🔴 Crítico |
| F14 | **Reportes** | `pages/Reportes.jsx` | `/reportes` 🔒admin | 🟠 Alto |
| F15 | **Configuración** (planes, usuarios) | `pages/Configuracion.jsx` | `/configuracion` 🔒admin | 🟠 Alto |
| F16 | **Notificaciones (historial)** | `pages/Notificaciones.jsx` | `/notificaciones` | 🟡 Medio |
| F17 | **Accesos / Membresías** | `pages/Accesos.jsx`, `pages/Membresias.jsx` | ❌ **sin ruta** | ⚪ Muerto |

---

## 3. Hallazgos del análisis (antes de escribir un solo test)

Estos salieron de leer el código, no de correrlo. Los pongo primero porque **cambian
qué tests hay que escribir**: no tiene sentido escribir un test de regresión que blinde
un comportamiento equivocado.

### 3.1 Bugs / huecos reales

| # | Hallazgo | Dónde | Impacto |
|---|----------|-------|---------|
| H1 | **`clases_restantes` nunca se valida ni se decrementa.** El modelo tiene el campo, `Acceso` tiene el motivo `clases_agotadas`, y `CheckInView` no lo mira. Un socio con paquete de 10 clases entra ilimitadamente. | `accesos/views.py::CheckInView` | 🔴 Un plan vendido no se cumple |
| H2 | **Sin anti-passback.** Escanear el mismo QR 20 veces registra 20 accesos permitidos. Rompe las estadísticas de aforo y permite prestar el código en la puerta. | `accesos/views.py::CheckInView` | 🔴 Dato de negocio corrupto |
| H3 | **`AuthContext` hace `JSON.parse(atob(...))` sin `try/catch`.** Un token corrupto o truncado en `localStorage` deja pantalla blanca sin forma de salir salvo limpiar el navegador. | `context/AuthContext.jsx:13` | 🔴 Usuario bloqueado |
| H4 | **`Accesos.jsx` y `Membresias.jsx` no están enrutadas.** Código muerto que además usa el tema claro viejo (`bg-white`, `text-gray-800`) — si alguien las enruta, rompen visualmente. | `App.jsx` | 🟡 Deuda |
| H5 | **`coach` y `recepcion` son indistinguibles en el frontend.** `isAdmin` es la única bifurcación. Un coach ve y usa Pagos igual que recepción, incluyendo cobrar. | `AuthContext.jsx:33` | 🟠 Permisos difusos |
| H6 | **`GymViewSet` permite a un admin de gym editar su propio Gym**, pero `SucursalViewSet` deja a cualquier admin crear sucursales sin validar que el `gym` del payload sea el suyo. | `gyms/views.py::SucursalViewSet` | 🟠 Fuga multi-tenant en escritura |
| H7 | **`Socios.jsx` asume `sucursales[0]`** al crear la membresía inicial. En un gym con 2+ sucursales, siempre la primera; si el array está vacío, manda `undefined`. | `pages/Socios.jsx:107` | 🟠 Dato incorrecto |
| H8 | **No hay validación de solape en Clases** (mismo profesor, mismo horario, mismos días) ni de `hora_fin > hora_inicio`. | `gyms/models.py::Clase` | 🟡 Dato inconsistente |
| H9 | **`inscritos` de Clase es un entero suelto**, no derivado de inscripciones reales. Nada impide `inscritos > cupo_max`. | `gyms/models.py::Clase` | 🟡 Dato inventado |
| H10 | **El refresh de axios no maneja carrera.** Si 4 peticiones dan 401 a la vez, se disparan 4 refresh; el último gana y los otros 3 pueden quedar con token viejo. | `api/axios.js:14` | 🟡 Logout aleatorio |
| H11 | **La suite tarda 412 s (7 min) con 4 workers para 249 tests.** `test_settings.py` no define `PASSWORD_HASHERS`, así que cada `create_user` corre PBKDF2 con ~1M de iteraciones. | `gymaccess/test_settings.py` | 🔴 **Bloquea todo este plan** |

> **Sobre H11 — es el hallazgo que hay que arreglar primero.** Una suite de regresión sólo
> sirve si se corre en cada cambio, y nadie corre una que tarda 7 minutos. Con los ~380
> tests de backend que propone este plan, serían ~10 minutos por push. El arreglo son
> tres líneas en `test_settings.py`:
>
> ```python
> PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
> ```
>
> Es seguro porque `test_settings.py` **sólo** se usa en tests (el CI lo fija con
> `DJANGO_SETTINGS_MODULE`); producción sigue con PBKDF2 intacto. Expectativa: bajar de
> 412 s a menos de 60 s. Hay que verificarlo midiendo, no asumiéndolo.

### 3.2 Lo que **sí** está bien resuelto (y hay que blindar para que no se rompa)

- El aislamiento multi-tenant en escritura de Membresías y Pagos (`_validar_pertenencia`)
  ya está hecho y comentado. Es exactamente el tipo de arreglo que una refactorización
  distraída deshace.
- `MembresiaQuerySet.vigentes()` unifica la definición de vigencia entre puerta y pantalla.
- `CheckInView` valida que la sucursal exista y sea del gym antes de insertar.
- Pagar renueva la membresía de verdad (`fecha_inicio`, `fecha_fin`, `clases_restantes`,
  `estado='activa'`) y `Pagos.jsx` toma el monto de `plan_precio`, no de un fijo.
- `NotificacionViewSet` bloquea el alta por API pero conserva las acciones POST.

---

## 4. Tipos de usuario y comportamiento esperado de la interfaz

El backend define 4 roles. El frontend hoy sólo distingue 2. Esta tabla es **la
especificación** contra la que se escriben los tests de rol — incluye lo que *debería*
pasar, no sólo lo que pasa hoy.

| Rol | Quién es | Aterriza en | Menú visible | Puede escribir | Estado actual |
|-----|----------|-------------|-------------|----------------|---------------|
| **`superadmin`** | Tú, el proveedor del SaaS | `/dashboard` | Todo | Todo, en todos los gyms | ✅ Implementado |
| **`admin`** | El dueño del gym | `/dashboard` | Todo | Todo, sólo su gym | ✅ Implementado |
| **`recepcion`** | Quien está en el mostrador | `/checkin` | Check-In, Socios, Clases, Pagos, Notificaciones | Socios, membresías, cobrar pagos, check-in | ✅ Implementado |
| **`coach`** | El entrenador | `/checkin` ⚠️ | Idéntico a recepción ⚠️ | Idéntico a recepción ⚠️ | ❌ **No diferenciado** |

**Propuesta para `coach`** (a validar contigo antes de escribir los tests):
aterriza en `/clases`; ve Check-In, Socios (sólo lectura), Clases y Notificaciones;
**no** ve Pagos ni puede cobrar. Un entrenador no debería tener acceso a la caja.

**Reglas transversales de interfaz que todo rol debe cumplir:**

1. Sin token → cualquier ruta redirige a `/login`.
2. Con token de no-admin → `/dashboard`, `/reportes`, `/equipamiento`, `/configuracion`
   redirigen a `/checkin` (no muestran un 403 feo, no parpadean el contenido antes de redirigir).
3. El menú lateral nunca muestra un link al que ese rol no puede entrar.
4. Un 403 del backend nunca deja la pantalla en blanco: se muestra un mensaje.
5. Token expirado a mitad de sesión → refresh transparente; si el refresh falla → `/login`
   sin perder datos que el usuario estaba escribiendo (o avisando antes de perderlos).

---

## 5. Estado actual de la cobertura

**249 tests automáticos existentes**, todos en el backend, todos DRF/`APITestCase`.
Los corrí completos hoy: **249/249 pasan (OK)**, en 412 s con `--parallel 4`. La base
está verde — el problema es el tiempo (ver H11).

| Archivo | Tests | Cubre |
|---------|-------|-------|
| `socios/tests_membresias.py` | 47 | B8, B9, T1 |
| `usuarios/tests_roles.py` | 37 | B2, T2 |
| `accesos/tests_dashboard.py` | 34 | B13 |
| `notificaciones/tests.py` | 32 | B14 |
| `gyms/tests_clases.py` | 31 | B4 |
| `gyms/tests.py` | 26 | B3, B5 |
| `accesos/tests.py` | 20 | B11, B12 |
| `socios/tests.py` | 18 | B6, B7 |
| `usuarios/tests.py` | 4 | B1 |

**Cobertura del frontend: 0.** No hay Vitest, ni Testing Library, ni Playwright.
El CI (`.github/workflows/ci.yml`) sólo corre `oxlint` y `vite build` — eso detecta
código que no compila, no comportamiento que se rompió.

**El hueco real, entonces, es:**
1. Todo el frontend (17 módulos, 0 tests).
2. Los flujos end-to-end que cruzan módulos (cobrar → renovar → entrar por la puerta).
3. Los comandos de mantenimiento (T4).
4. Los bugs H1–H10, que no tienen test porque no están arreglados.

---

## 6. Plan de tests — Backend

### 6.1 Estrategia

Tres anillos, del más barato al más caro:

- **Anillo 1 — Contrato de aislamiento (multi-tenant).** Un test parametrizado por cada
  uno de los 14 módulos: "usuario del gym A no ve / no escribe / no borra nada del gym B".
  Es repetitivo a propósito: es la red que atrapa la regresión más cara.
- **Anillo 2 — Reglas de negocio por módulo.** Casos de borde de fechas, montos, estados.
- **Anillo 3 — Flujos end-to-end de API.** Secuencias multi-módulo dentro de un solo test.

### 6.2 Casos por módulo

#### B1 — Auth / JWT
- `A-B1-01` Login con credenciales válidas devuelve `access` + `refresh`.
- `A-B1-02` El `access` contiene `nombre`, `email`, `rol`, `gym_id` en el payload.
- `A-B1-03` Login con password incorrecto → 401.
- `A-B1-04` Login con email inexistente → 401 (mismo mensaje que el anterior: no filtra si el email existe).
- `A-B1-05` Login de usuario `is_active=False` → 401.
- `A-B1-06` Refresh con token válido devuelve nuevo `access`.
- `A-B1-07` Refresh con token basura → 401.
- `A-B1-08` **Throttle**: el intento 11 de login en un minuto desde la misma IP → 429.
- `A-B1-09` Petición a cualquier endpoint sin `Authorization` → 401.
- `A-B1-10` Petición con `Bearer` malformado → 401.

#### B2 — Usuarios y roles
- `A-B2-01..04` `recepcion` y `coach` reciben 403 en GET/POST/PATCH/DELETE de `/api/usuarios/`.
- `A-B2-05` `admin` lista sólo usuarios de su gym.
- `A-B2-06` `superadmin` lista usuarios de todos los gyms.
- `A-B2-07` `admin` crea usuario → se le fuerza su `gym_id` aunque mande otro en el payload.
- `A-B2-08` `superadmin` crea usuario con `gym` explícito → se respeta.
- `A-B2-09` La password se guarda hasheada (`check_password` pasa, `user.password != texto`).
- `A-B2-10` PATCH con `password` re-hashea; PATCH sin `password` no la borra.
- `A-B2-11` `admin` del gym A no puede PATCH/DELETE un usuario del gym B → 404.
- `A-B2-12` El serializer nunca devuelve `password` en la respuesta.
- `A-B2-13` Email duplicado → 400.

#### B3 — Gyms y Sucursales
- `A-B3-01` `admin` ve sólo su gym; `superadmin` ve todos.
- `A-B3-02` `recepcion` puede leer el gym pero POST/PATCH → 403 (`AdminOSoloLectura`).
- `A-B3-03` Gym con `activo=False` no aparece en el listado.
- `A-B3-04` **(cubre H6)** `admin` del gym A crea sucursal con `gym: B` en el payload → 400.
- `A-B3-05` **(cubre H6)** `admin` del gym A hace PATCH a sucursal del gym B → 404.
- `A-B3-06` Sucursal con `activa=False` no aparece en el listado.
- `A-B3-07` El serializer de Gym anida sus sucursales.

#### B4 — Clases
- `A-B4-01..03` Aislamiento: listar / editar / borrar sólo dentro del gym.
- `A-B4-04` `perform_create` fuerza el `gym_id` del usuario, ignorando el payload.
- `A-B4-05` Clase con `activa=False` desaparece del listado.
- `A-B4-06` `tipo_display` y `nivel_display` salen traducidos.
- `A-B4-07` `tipo` inválido → 400.
- `A-B4-08` **(cubre H8)** `hora_fin` anterior a `hora_inicio` → 400. *(requiere arreglar H8)*
- `A-B4-09` **(cubre H8)** Solape del mismo profesor en el mismo día y horario → 400. *(requiere H8)*
- `A-B4-10` **(cubre H9)** `inscritos > cupo_max` → 400. *(requiere H9)*
- `A-B4-11` Cualquier rol autenticado puede crear clase (hoy no hay `AdminOSoloLectura` aquí — confirmar si es intencional).

#### B5 — Equipamiento
- `A-B5-01..03` Aislamiento en listar / editar / borrar.
- `A-B5-04` `recepcion` y `coach` → 403 en todo (`EsAdminGym`).
- `A-B5-05` Crear equipamiento genera notificación tipo `inventario` con el nombre.
- `A-B5-06` Editar genera notificación.
- `A-B5-07` Borrar genera notificación **antes** de borrar (y la notificación sobrevive).
- `A-B5-08` La notificación se crea en el gym correcto, no en otro.

#### B6 — Planes
- `A-B6-01..03` Aislamiento.
- `A-B6-04` `recepcion` lee planes (los necesita para dar de alta socios) pero no los escribe → 403.
- `A-B6-05` Plan `activo=False` no aparece.
- `A-B6-06` Precio negativo → 400.
- `A-B6-07` Plan tipo `clases` sin `num_clases` → 400 (o documentar que se permite).
- `A-B6-08` Plan tipo `mensual` sin `duracion_dias` → la membresía queda sin `fecha_fin` = acceso perpetuo. **Test que documenta el riesgo.**

#### B7 — Socios
- `A-B7-01..03` Aislamiento en listar / editar / borrar.
- `A-B7-04` Crear socio genera automáticamente un `MetodoAcceso` tipo `qr`.
- `A-B7-05` El token QR generado es único entre dos socios creados seguidos.
- `A-B7-06` `codigo_acceso` en el serializer devuelve el token del método activo.
- `A-B7-07` Si el método QR se desactiva, `codigo_acceso` → `null`.
- `A-B7-08` `superadmin` sin gym crea socio sin indicar `gym` → 400 con mensaje claro.
- `A-B7-09` `superadmin` sin gym crea socio indicando `gym` → 201 en ese gym.
- `A-B7-10` `membresia_activa` refleja `vigentes()`, no `estado='activa'` a secas.
- `A-B7-11` Socio con membresía `estado='activa'` pero `fecha_fin` de ayer → `membresia_activa: null`.
- `A-B7-12` Socio con membresía cuya `fecha_inicio` es mañana → `membresia_activa: null`.
- `A-B7-13` Email inválido → 400.
- `A-B7-14` Socio con `activo=False` **sí** aparece en el listado (la pantalla los cuenta como inactivos).

#### B8 — Membresías 🔴
- `A-B8-01..03` Aislamiento en lectura.
- `A-B8-04` POST con `socio` de otro gym → 400.
- `A-B8-05` POST con `plan` de otro gym → 400.
- `A-B8-06` POST con `sucursal` de otro gym → 400.
- `A-B8-07` POST con los tres de otro gym → 400 con los tres errores.
- `A-B8-08` PATCH que intenta mover la membresía a un socio de otro gym → 400.
- `A-B8-09..16` **`vigentes()` — matriz de fechas.** Para cada combinación:
  | Caso | `estado` | `fecha_inicio` | `fecha_fin` | ¿Vigente? |
  |------|----------|----------------|-------------|-----------|
  | 09 | activa | ayer | mañana | ✅ |
  | 10 | activa | hoy | hoy | ✅ (límites inclusivos) |
  | 11 | activa | ayer | ayer | ❌ |
  | 12 | activa | mañana | pasado | ❌ |
  | 13 | activa | ayer | `null` | ✅ (perpetua) |
  | 14 | vencida | ayer | mañana | ❌ |
  | 15 | suspendida | ayer | mañana | ❌ |
  | 16 | pendiente_pago | ayer | mañana | ❌ |
- `A-B8-17` `caducadas()` devuelve exactamente las `activa` con `fecha_fin` pasada.
- `A-B8-18` Un socio con 2 membresías vigentes: `vigentes().first()` es determinista (definir el orden — hoy no hay `order_by` y el resultado depende del motor de BD).
- `A-B8-19` No se puede borrar un `Plan` que tiene membresías (`on_delete=PROTECT`) → el DELETE devuelve error controlado, no 500.

#### B9 — Pagos 🔴
- `A-B9-01..02` Aislamiento en lectura; POST contra membresía de otro gym → 400.
- `A-B9-03` `registrado_por` se llena solo con el usuario autenticado, ignorando el payload.
- `A-B9-04` **Pagar renueva**: `fecha_inicio = hoy`, `fecha_fin = hoy + plan.duracion_dias`, `estado = 'activa'`.
- `A-B9-05` Pagar un plan sin `duracion_dias` deja `fecha_fin = null`.
- `A-B9-06` Pagar un plan de clases resetea `clases_restantes = plan.num_clases`.
- `A-B9-07` Pagar una membresía **vencida** la reactiva y el socio puede entrar inmediatamente después (cruza a B12).
- `A-B9-08` Pagar una membresía **vigente** la renueva desde hoy — ⚠️ **esto le quita días al socio.** Test que fija el comportamiento actual; decidir si debe extenderse desde `fecha_fin` en vez de desde hoy.
- `A-B9-09` Monto negativo → 400.
- `A-B9-10` Monto distinto al precio del plan → se acepta (pagos parciales). Documentar.
- `A-B9-11` Dos pagos seguidos a la misma membresía no duplican el período.
- `A-B9-12` `fecha` es de sólo lectura: mandarla en el payload no la cambia.

#### B10 — Gastos
- `A-B10-01..03` Aislamiento.
- `A-B10-04` `recepcion` y `coach` → 403 (`EsAdminGym`).
- `A-B10-05` `gym` y `registrado_por` se fuerzan del usuario.
- `A-B10-06` Categoría inválida → 400.
- `A-B10-07` Monto negativo → 400.

#### B11 — Métodos de acceso
- `A-B11-01` Aislamiento: sólo métodos de socios del propio gym.
- `A-B11-02` `sincronizar-huella` sin `socio_id` → 400; sin `template` → 400.
- `A-B11-03` Socio de otro gym → 404.
- `A-B11-04` Template ya registrado a otro socio → 409.
- `A-B11-05` Re-sincronizar al **mismo** socio actualiza en vez de duplicar (`update_or_create`).
- `A-B11-06` Un socio no puede tener 2 métodos tipo huella.
- `A-B11-07` `token` es único a nivel BD entre gyms distintos (colisión → error controlado, no 500).

#### B12 — Check-in 🔴
- `A-B12-01` Token válido + membresía vigente → 200 `permitido`, con `socio`, `plan`, `vence`.
- `A-B12-02` Se crea el registro `Acceso` con `resultado='permitido'` y la membresía ligada.
- `A-B12-03` Token inexistente → 404 `Token inválido`.
- `A-B12-04` Token de un socio de **otro gym** → 404 (no 403: no confirma que el token existe).
- `A-B12-05` Token con `activo=False` → 404.
- `A-B12-06` Socio **sin ninguna membresía** → 403, motivo `sin_membresia`.
- `A-B12-07` Socio con membresía vencida → 403, motivo `membresia_vencida`.
- `A-B12-08` El caso 07 **genera notificación** `pago_vencido` con link `/pagos?tab=atrasados`.
- `A-B12-09` El caso 06 **no** genera notificación.
- `A-B12-10` `sucursal_id` ausente → 400 (no 500).
- `A-B12-11` `sucursal_id` vacío `''` → 400.
- `A-B12-12` `sucursal_id` no numérico → 400.
- `A-B12-13` `sucursal_id` de otro gym → 400.
- `A-B12-14` Membresía suspendida → 403.
- `A-B12-15` Socio con `activo=False` pero membresía vigente → **hoy entra.** ⚠️ Definir si debe.
- `A-B12-16` **Throttle**: petición 61 en un minuto → 429.
- `A-B12-17` Sin autenticar → 401.
- `A-B12-18` **(cubre H1)** Plan de clases con `clases_restantes=1`: primera entrada permitida y decrementa a 0. *(requiere arreglar H1)*
- `A-B12-19` **(cubre H1)** `clases_restantes=0` → 403 motivo `clases_agotadas`. *(requiere H1)*
- `A-B12-20` **(cubre H2)** Segundo escaneo dentro de N minutos → respuesta idempotente sin duplicar el `Acceso`. *(requiere H2)*

#### B13 — Accesos: historial y stats
- `A-B13-01` Aislamiento del historial.
- `A-B13-02` Orden descendente por `timestamp`.
- `A-B13-03` `AccesoViewSet` es read-only: POST/PATCH/DELETE → 405.
- `A-B13-04` `stats` cuenta sólo `resultado='permitido'`.
- `A-B13-05` `accesos_hoy` respeta la zona horaria `America/Mexico_City` (acceso a las 23:30 hora local cuenta hoy, no mañana en UTC).
- `A-B13-06` `accesos_mes` arranca el día 1.
- `A-B13-07` `horarios_concurridos` agrupa por hora local, no UTC.
- `A-B13-08` Gym sin accesos → ceros y lista vacía, no error.

#### B14 — Notificaciones
- `A-B14-01` Aislamiento.
- `A-B14-02` POST directo → 405.
- `A-B14-03` `list` excluye archivadas; `historial` las incluye.
- `A-B14-04` `marcar-todas-leidas` sólo afecta al propio gym.
- `A-B14-05` `limpiar` marca `archivada=True` y `leida=True`, y siguen en el historial.
- `A-B14-06` Notificación de más de 15 días se purga al listar.
- `A-B14-07` La purga **no** toca las de otro gym.
- `A-B14-08` PATCH sólo puede cambiar `leida`/`archivada`; `mensaje` es de sólo lectura.
- `A-B14-09` Una de exactamente 15 días — definir si se purga o sobrevive (hoy el límite es estricto).

#### T4 — Comandos de mantenimiento
- `A-T4-01` `marcar_membresias_vencidas` cambia a `vencida` sólo las `activa` con fecha pasada.
- `A-T4-02` No toca las perpetuas (`fecha_fin=null`).
- `A-T4-03` Correrlo dos veces es idempotente.
- `A-T4-04` `limpiar_notificaciones` borra > 15 días en todos los gyms.
- `A-T4-05` `seed_demo` corre sin error sobre BD vacía y es re-ejecutable.

### 6.3 Flujos end-to-end de API (anillo 3)

- `E2E-01 — Ciclo de vida del socio`: crear socio → recibe QR → crear membresía → check-in permitido → adelantar el reloj más allá de `fecha_fin` → check-in denegado → se genera notificación → registrar pago → check-in permitido otra vez.
- `E2E-02 — Aislamiento total`: montar dos gyms completos con datos espejo; recorrer los 14 módulos con el usuario del gym A y verificar que ninguna respuesta contiene un ID del gym B.
- `E2E-03 — Escalada de privilegios`: `recepcion` intenta los 9 endpoints de admin; los 9 devuelven 403/404 y ninguno modifica datos.
- `E2E-04 — Paquete de clases`: plan de 10 clases → 10 check-ins permitidos → el 11 denegado → pagar → vuelve a 10. *(requiere H1)*
- `E2E-05 — Cierre de mes`: pagos y gastos de dos meses → los totales de reportes cuadran exactamente con la suma de los registros.

---

## 7. Plan de tests — Frontend

### 7.1 Stack propuesto

| Capa | Herramienta | Para qué |
|------|-------------|----------|
| Unitario / componente | **Vitest + React Testing Library + MSW** | Lógica de F2–F7, render de pantallas con API simulada |
| End-to-end | **Playwright** | Flujos reales contra el backend de verdad, multi-rol |
| Visual | Playwright screenshots | Sólo en Login, CheckIn y Dashboard (donde el diseño *es* el producto) |

**MSW** (Mock Service Worker) intercepta las llamadas HTTP: los tests de componente
corren sin backend levantado, lo que los hace rápidos y deterministas. Playwright corre
contra el sistema completo y es lo que atrapa las roturas de integración.

### 7.2 Casos por módulo

#### F2 — AuthContext 🔴
- `A-F2-01` Sin token en `localStorage` → `user = null`, `loading = false`.
- `A-F2-02` Token válido → `user` se hidrata con el payload decodificado.
- `A-F2-03` **(cubre H3)** Token corrupto (`"abc"`) → `user = null` y redirige a login, **sin excepción**. *(requiere arreglar H3)*
- `A-F2-04` **(cubre H3)** Token con base64 válido pero JSON inválido → mismo manejo. *(requiere H3)*
- `A-F2-05` `isAdmin` es `true` para `admin` y `superadmin`, `false` para `recepcion` y `coach`.
- `A-F2-06` `login()` guarda `access` y `refresh` y devuelve el payload.
- `A-F2-07` `logout()` limpia `localStorage` completo y pone `user = null`.
- `A-F2-08` Token expirado (`exp` en el pasado) → se detecta antes de renderizar. ⚠️ Hoy **no se valida `exp`**: se confía en el 401 del backend.

#### F3 — Cliente API 🔴
- `A-F3-01` Cada petición lleva `Authorization: Bearer`.
- `A-F3-02` Sin token en `localStorage`, no se manda el header.
- `A-F3-03` Un 401 dispara refresh y **reintenta la petición original** con el token nuevo.
- `A-F3-04` Refresh fallido → limpia storage y navega a `/login`.
- `A-F3-05` Un 401 **sin** refresh en storage → no entra en bucle, propaga el error.
- `A-F3-06` Un 403 **no** dispara refresh (no es un problema de token).
- `A-F3-07` **(cubre H10)** 4 peticiones con 401 simultáneo → **un solo** refresh, las 4 se reintentan. *(requiere arreglar H10)*
- `A-F3-08` Un 401 en la propia llamada de refresh no genera recursión infinita.

#### F5 + F6 — Router, guards y menú 🔴
Matriz de rutas × roles. Por cada rol (`superadmin`, `admin`, `recepcion`, `coach`) y cada
ruta, verificar destino final y que el link exista o no en el sidebar:

| Ruta | superadmin | admin | recepcion | coach (propuesto) |
|------|-----------|-------|-----------|-------------------|
| `/` | → `/dashboard` | → `/dashboard` | → `/checkin` | → `/clases` |
| `/dashboard` | ✅ | ✅ | → `/checkin` | → `/clases` |
| `/checkin` | ✅ | ✅ | ✅ | ✅ |
| `/socios` | ✅ | ✅ | ✅ | ✅ sólo lectura |
| `/clases` | ✅ | ✅ | ✅ | ✅ |
| `/pagos` | ✅ | ✅ | ✅ | → `/clases` |
| `/notificaciones` | ✅ | ✅ | ✅ | ✅ |
| `/equipamiento` | ✅ | ✅ | → `/checkin` | → `/clases` |
| `/reportes` | ✅ | ✅ | → `/checkin` | → `/clases` |
| `/configuracion` | ✅ | ✅ | → `/checkin` | → `/clases` |
| ruta inexistente | ⚠️ | ⚠️ | ⚠️ | ⚠️ |

- `A-F5-01..40` La matriz completa (4 roles × 10 rutas).
- `A-F5-41` Sin sesión, **cualquier** ruta protegida → `/login`.
- `A-F5-42` Mientras `loading=true` se ve "Cargando...", no un parpadeo del contenido.
- `A-F5-43` Ruta inexistente (`/asdf`) → hoy **pantalla en blanco**. Falta un 404. ⚠️
- `A-F5-44` El sidebar de `recepcion` tiene exactamente 5 links.
- `A-F5-45` El sidebar de `admin` tiene exactamente 8 links.
- `A-F5-46` El link activo se marca visualmente.
- `A-F5-47` "Cerrar sesión" limpia storage y lleva a `/login`.

#### F1 — Login
- `A-F1-01` Credenciales válidas de admin → navega a `/dashboard`.
- `A-F1-02` Credenciales válidas de recepción → navega a `/checkin`.
- `A-F1-03` Credenciales inválidas → toast "Credenciales incorrectas", sigue en `/login`.
- `A-F1-04` El botón se deshabilita mientras carga y dice "Verificando...".
- `A-F1-05` El toggle de ojo alterna `type` entre `password` y `text`.
- `A-F1-06` Campos vacíos → validación nativa, no se llama a la API.
- `A-F1-07` Un 429 (throttle) muestra un mensaje **distinto** al de credenciales malas. ⚠️ Hoy dice lo mismo.
- `A-F1-08` Backend caído → mensaje de error de conexión, no pantalla blanca.

#### F9 — Check-In 🔴
- `A-F9-01` Al montar, carga sucursales y preselecciona la primera.
- `A-F9-02` Sin sucursales → opción "Sin sucursales" y el submit no revienta.
- `A-F9-03` Enviar un token permitido → tarjeta verde "BIENVENIDO" con nombre, plan y vencimiento.
- `A-F9-04` Token denegado → tarjeta roja "ACCESO DENEGADO" con el motivo.
- `A-F9-05` Token inválido → tarjeta roja con "Token inválido".
- `A-F9-06` El input se limpia después de cada intento (crítico para el lector).
- `A-F9-07` El resultado se auto-limpia a los 6 s.
- `A-F9-08` Un segundo escaneo antes de los 6 s cancela el timer anterior.
- `A-F9-09` En escritorio, el foco vuelve al input tras cada scan.
- `A-F9-10` En táctil (`pointer: coarse`), **no** se fuerza el foco.
- `A-F9-11` Token con espacios se recorta antes de enviar.
- `A-F9-12` Submit con input vacío no llama a la API.
- `A-F9-13` Error de red → "Error de conexión".
- `A-F9-14` Con foto, se muestra la foto; sin foto, el emoji.
- `A-F9-15` `vence: null` → "Sin fecha límite".
- `A-F9-16` El reloj se actualiza y el `setInterval` se limpia al desmontar.
- `A-F9-17` Cambiar de sucursal manda el nuevo `sucursal_id`.

#### F10 — Socios 🔴
- `A-F10-01` Lista socios con su estado de membresía.
- `A-F10-02` Buscador filtra por nombre y por apellido.
- `A-F10-03` Alta de socio con plan → 2 llamadas: `POST /socios/` y `POST /socios/membresias/`.
- `A-F10-04` Alta sin plan → sólo 1 llamada.
- `A-F10-05` **(cubre H7)** Con 2 sucursales, la membresía usa la sucursal **elegida**, no `sucursales[0]`. *(requiere arreglar H7)*
- `A-F10-06` **(cubre H7)** Sin sucursales cargadas, el alta con plan se bloquea con mensaje claro. *(requiere H7)*
- `A-F10-07` Edición hace PATCH, no POST, y no crea membresía nueva.
- `A-F10-08` Fallo del POST → toast de error y el modal **no se cierra** (no se pierde lo escrito).
- `A-F10-09` El QR se renderiza con el `codigo_acceso` del socio.
- `A-F10-10` Socio sin `codigo_acceso` → no rompe el render del QR.
- `A-F10-11` Huella: sin `window.fingerprintAgent` → "Agente de huella no detectado".
- `A-F10-12` Huella: agente presente y éxito → estado ok + toast.
- `A-F10-13` Huella: 409 del backend → muestra "ya registrada a otro socio".
- `A-F10-14` Contadores de activos/inactivos cuadran con la lista.

#### F13 — Pagos 🔴
- `A-F13-01` Pestaña "Atrasados" lista exactamente las de `fecha_fin < hoy`.
- `A-F13-02` El modal de cobro precarga `plan_precio` como monto.
- `A-F13-03` Membresía sin `plan_precio` → monto vacío, no `undefined` en pantalla.
- `A-F13-04` Confirmar pago → POST y recarga membresías **y** pagos.
- `A-F13-05` Tras cobrar, la membresía sale de "Atrasados".
- `A-F13-06` Se puede editar el monto antes de confirmar (pago parcial).
- `A-F13-07` Fallo del POST → toast de error, el modal sigue abierto.
- `A-F13-08` `recepcion` **no** ve la pestaña Gastos ni el tile "Cobrado este mes".
- `A-F13-09` `admin` ve las 4 pestañas y los 4 tiles.
- `A-F13-10` `recepcion` no dispara `GET /socios/gastos/` (evita un 403 en consola).
- `A-F13-11` Alta de gasto → POST y recarga.
- `A-F13-12` Los totales se calculan sobre los datos cargados, sin números inventados.

#### F8 — Dashboard
- `A-F8-01` Renderiza con socios y stats cargados.
- `A-F8-02` Gym vacío → ceros y gráficas vacías, no `NaN` ni pantalla rota.
- `A-F8-03` Fallo de una de las dos llamadas → la otra sigue mostrándose.
- `A-F8-04` La gráfica de horarios refleja `horarios_concurridos`.
- `A-F8-05` Los conteos de socios activos/vencidos cuadran con `membresia_activa`.

#### F14 — Reportes
- `A-F14-01` Ingresos = suma de pagos del período; egresos = suma de gastos.
- `A-F14-02` Utilidad = ingresos − egresos, incluyendo negativa.
- `A-F14-03` Sin datos → ceros, no `NaN`.
- `A-F14-04` Cambiar de período recalcula.
- `A-F14-05` Los montos se formatean como moneda con separador de miles.

#### F15 — Configuración
- `A-F15-01` Lista planes activos.
- `A-F15-02` Alta / edición / baja de plan hacen POST / PATCH / DELETE.
- `A-F15-03` Borrar un plan con membresías → error controlado (`PROTECT`), no pantalla rota.
- `A-F15-04` Precio no numérico → validación antes de enviar.
- `A-F15-05` Sólo accesible a admin (cubierto también en F5).

#### F11 / F12 / F16 / F7 — Clases, Equipamiento, Notificaciones, Navbar
- `A-F11-01..05` Clases: listar, crear, editar, borrar con confirmación, fallo → toast.
- `A-F12-01..04` Equipamiento: CRUD + `recepcion` recibe 403 manejado.
- `A-F16-01..03` Historial: lista, incluye archivadas, vacío → mensaje.
- `A-F7-01` La campana muestra el conteo de no leídas.
- `A-F7-02` Abrir el dropdown lista las no archivadas.
- `A-F7-03` Click en una notificación la marca leída y navega a su `link`.
- `A-F7-04` "Marcar todas leídas" pone el contador en 0.
- `A-F7-05` "Limpiar" vacía el dropdown pero no el historial.
- `A-F7-06` El polling se detiene al desmontar (sin fugas).

### 7.3 End-to-end con Playwright

- `E2E-F1 — Jornada de recepción`: login como recepción → aterriza en check-in → escanea un socio al corriente (verde) → escanea uno vencido (rojo) → ve la notificación en la campana → va a Pagos → cobra → vuelve a check-in → ahora entra.
- `E2E-F2 — Jornada de admin`: login → dashboard con datos → alta de socio con plan → aparece su QR → alta de clase → alta de equipamiento (genera notificación) → reportes cuadran.
- `E2E-F3 — Frontera de roles`: login como recepción → escribir a mano `/dashboard`, `/reportes`, `/configuracion`, `/equipamiento` en la barra de direcciones → las 4 redirigen a `/checkin` y el sidebar nunca mostró esos links.
- `E2E-F4 — Sesión`: login → borrar `access` de `localStorage` a mano → la siguiente acción hace refresh transparente → borrar también `refresh` → la siguiente acción manda a `/login`.
- `E2E-F5 — Aislamiento visible`: dos gyms con datos; login como admin del gym A y confirmar que ningún nombre del gym B aparece en ninguna pantalla.
- `E2E-F6 — Responsive`: a 390 px de ancho, el sidebar es drawer, abre y cierra, y el check-in es usable con el teclado en pantalla.

---

## 8. Tests manuales (los que haces tú)

Estos no se automatizan de forma razonable: dependen de hardware físico, de percepción
visual, o de condiciones que sólo se dan en el local. Los dejo en formato de lista de
verificación para que los corras antes de cada release.

### 8.1 Lector QR — ⏳ pendiente hasta que tengas el equipo

El lector QR de kiosco se comporta como un **teclado HID**: "teclea" el código y manda
un Enter. Por eso `CheckIn.jsx` mantiene el foco pegado al input. Todo lo de abajo
prueba justamente esa suposición, y **ninguna de estas cosas la puede simular un test
automático** de forma confiable.

| # | Caso | Cómo se prueba | Qué debe pasar |
|---|------|----------------|----------------|
| M-QR-01 | Escaneo básico | Escanear el QR de un socio al corriente | Pantalla verde en < 1 s, sin tocar el teclado |
| M-QR-02 | El lector manda Enter | Escanear y no tocar nada | Se envía solo, sin dar click en "Verificar" |
| M-QR-03 | Velocidad del "tecleo" | Escanear un código largo | Llega completo, sin caracteres perdidos |
| M-QR-04 | Foco perdido | Dar click fuera, luego escanear | El foco vuelve solo y el scan funciona |
| M-QR-05 | Escaneos consecutivos | 5 socios seguidos, rápido | Los 5 se procesan, ninguno se pierde ni se mezcla |
| M-QR-06 | Doble escaneo del mismo | Escanear 2 veces seguidas al mismo socio | ⚠️ Hoy cuenta 2 accesos (H2) — verificar qué se decidió |
| M-QR-07 | QR dañado / sucio | Escanear un código rayado o mojado | No lee, o lee mal → "Token inválido" (no cuelga) |
| M-QR-08 | QR de otro gimnasio | Escanear un QR de otro tenant | "Token inválido" |
| M-QR-09 | QR desde pantalla de celular | El socio muestra el QR en su teléfono | Lee bien con brillo alto; anotar si falla con brillo bajo |
| M-QR-10 | Distancia y ángulo | Escanear a 5, 15 y 30 cm; inclinado | Documentar el rango que funciona |
| M-QR-11 | Layout de teclado | Verificar que el lector esté en teclado en inglés | Los guiones del token (`R3B-QR-...`) no salen cambiados |
| M-QR-12 | Reconexión USB | Desconectar y reconectar el lector | Vuelve a funcionar sin recargar la página |
| M-QR-13 | Kiosco 8 h seguidas | Dejar la pantalla abierta toda la jornada | No se degrada, no fuga memoria, el reloj sigue bien |
| M-QR-14 | Internet caído | Desconectar la red y escanear | Mensaje claro de conexión, no pantalla blanca |
| M-QR-15 | Internet intermitente | Cortar la red a mitad de un scan | No deja el botón trabado en "Verificando..." |

### 8.2 Lector de huella (DigitalPersona U.are.U 4500)

| # | Caso | Qué debe pasar |
|---|------|----------------|
| M-HU-01 | Registrar huella de un socio | "Huella sincronizada correctamente" |
| M-HU-02 | Registrar sin el agente corriendo | "Agente de huella no detectado en esta PC" |
| M-HU-03 | Misma huella a un segundo socio | Error 409 visible en pantalla |
| M-HU-04 | Re-registrar al mismo socio | Actualiza, no duplica |
| M-HU-05 | Entrar con huella | Check-in permitido, `metodo_usado='huella'` en el historial |
| M-HU-06 | Dedo mojado / sucio | No lee → mensaje claro, permite reintentar |
| M-HU-07 | Dedo equivocado | No permite el acceso |

### 8.3 Dispositivos, navegadores y percepción visual

| # | Caso | Qué revisar |
|---|------|-------------|
| M-UI-01 | Tablet del kiosco (la real) | El check-in se ve completo sin scroll; el teclado no tapa el resultado |
| M-UI-02 | Celular de la dueña | Todas las pantallas usables; el drawer abre y cierra |
| M-UI-03 | Monitor de la recepción | Sidebar colapsado y expandido, ambos legibles |
| M-UI-04 | Chrome, Safari, Firefox | Sin roturas visuales; ojo con Safari en iOS |
| M-UI-05 | Contraste a plena luz | Verde y rojo del check-in distinguibles a 2 m de distancia |
| M-UI-06 | Impresión de credencial con QR | El QR impreso se lee con el lector |
| M-UI-07 | Nombre muy largo | No desborda las tarjetas ni las tablas |
| M-UI-08 | Foto de socio muy pesada / vertical | Se recorta bien, no deforma la tarjeta |
| M-UI-09 | Gym recién creado, sin datos | Ninguna pantalla muestra `NaN`, `undefined` ni queda en blanco |

### 8.4 Operación real (una vez por release, en el gym)

| # | Caso | Qué revisar |
|---|------|-------------|
| M-OP-01 | Hora pico | 10 personas entrando en 2 minutos: el kiosco aguanta y no llega al throttle de 60/min |
| M-OP-02 | Corte de caja | Lo cobrado en el sistema cuadra peso a peso con el efectivo del cajón |
| M-OP-03 | Cierre de mes | Reportes vs. suma manual de pagos y gastos |
| M-OP-04 | Cambio de día a medianoche | Un acceso a las 23:55 y otro a las 00:05 caen en días distintos |
| M-OP-05 | Socio que reclama | El historial de accesos coincide con lo que la persona recuerda |
| M-OP-06 | Backup y restauración | Restaurar la BD en limpio y verificar que no se perdió nada |

---

## 9. Cómo se ejecuta esto para que sirva

Un plan de regresión sólo funciona si corre solo. La propuesta:

**Pirámide objetivo:**

```
      ▲  E2E Playwright        ~15 tests    (5 min)   → antes de cada release
     ▲▲  Componente Vitest    ~130 tests   (30 s)    → en cada push
    ▲▲▲  API Django           ~380 tests   (< 2 min) → en cada push  ⚠️ requiere H11
```

⚠️ Ese "< 2 min" de la base es **el objetivo, no el estado actual**: hoy 249 tests tardan
412 s, así que 380 tardarían ~10 min. Arreglar H11 es el requisito para que esta pirámide
sea realista.

**Puertas de calidad en CI** (`.github/workflows/ci.yml`, ampliando lo que ya existe):

| Puerta | Cuándo | Bloquea el merge |
|--------|--------|-----------------|
| `oxlint` + `vite build` | cada push | ✅ (ya existe) |
| Tests Django | cada push | ✅ (ya existe) |
| Tests Vitest | cada push | ✅ nuevo |
| Cobertura backend ≥ 80 % | cada push | ⚠️ avisa primero, bloquea después |
| Playwright E2E | PR a `main` | ✅ nuevo |
| Suite manual §8 | antes de release | 🖐️ checklist firmada por ti |

**Regla de oro para cada cambio futuro:** si tocas un módulo de la tabla §2, corres su
bloque de tests **más** el anillo 1 (aislamiento) completo. Si tocas T1, T2 o T3, corres
la suite entera sin excepción — son los tres puntos donde un cambio pequeño se propaga
a todo el sistema.

---

## 10. Orden de trabajo propuesto

Por prioridad de riesgo, no por facilidad:

| Fase | Qué | Por qué primero |
|------|-----|----------------|
| **0a** | **Arreglar H11** (hasher rápido en `test_settings.py`) y medir la mejora | 15 minutos de trabajo que hacen viable todo lo demás; sin esto la suite no se corre |
| **0b** | Decidir sobre H1, H2, H5, H7, H10 y el rol `coach` | No tiene sentido escribir tests que blinden un comportamiento que vamos a cambiar |
| **1** | Anillo 1 backend: aislamiento multi-tenant en los 14 módulos | Es la regresión más cara y la más fácil de reintroducir |
| **2** | B8, B9, B12 + T1 (membresías, pagos, check-in) | Es el corazón del negocio: quién entra y quién pagó |
| **3** | Montar Vitest + RTL + MSW; cubrir F2, F3, F5 | Sesión, token y permisos: si fallan, todo lo demás da igual |
| **4** | F9, F10, F13 (check-in, socios, pagos) | Las tres pantallas que se usan todos los días |
| **5** | Resto del backend (B1–B7, B10, B11, B13, B14, T4) | Cobertura de fondo |
| **6** | Resto del frontend (F1, F7, F8, F11, F12, F14–F16) | Cobertura de fondo |
| **7** | Playwright E2E + puertas de CI | El cierre: integración real y automatización |
| **8** | Ejecutar la suite manual §8 con el QR ya comprado | Lo que ningún test automático cubre |

**Totales estimados:** ~380 tests automáticos de backend (249 existentes + ~130 nuevos),
~130 de componente frontend, ~15 E2E, y ~37 casos manuales.

---

## 11. Lo que necesito que decidas antes de escribir la suite

1. **`coach`**: ¿la propuesta de §4 (aterriza en Clases, sin acceso a Pagos) o lo dejamos igual que recepción?
2. **H1 — clases restantes**: ¿el check-in debe decrementar y bloquear al agotarse? (Es un plan que ya vendes.)
3. **H2 — anti-passback**: ¿ventana de cuántos minutos? ¿5, 30, o "una entrada por día"?
4. **B9-08 — renovación**: pagar hoy una membresía que vence en 10 días, ¿pierde esos 10 días (comportamiento actual) o se le suman?
5. **B12-15**: un socio marcado `activo=False` con membresía vigente, ¿entra o no?
6. **Alcance de la fase 1**: ¿arranco por el anillo de aislamiento completo, o prefieres que empiece por B12 (check-in) porque el QR ya viene en camino?
