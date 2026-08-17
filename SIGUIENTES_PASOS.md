# GymAccess — Siguientes pasos

> Continuación de [`PLAN_REGRESION.md`](PLAN_REGRESION.md). Ese documento es el plan
> completo (inventario de módulos y catálogo de casos); éste es la lista de trabajo
> pendiente, en orden, con el estado real medido.

Última actualización: **2026-08-14** · Rama `main` · Base `9e861d9` (+ cambios sin commitear)

---

## 0. Dónde estamos

| | Al empezar | Hoy |
|---|---|---|
| Tests backend | 249 en **412 s** | **289 en 7 s** |
| Cobertura backend (sin `seed_demo`) | 94 % | **96 %** |
| Tests frontend | 0 | **88** |
| Cobertura frontend | 0 % | **57 %** |
| CI | lint + build + tests Django | + **tests Vitest** |

**Cerrado:** hasher de tests, las 4 reglas de negocio nuevas (coach, anti-passback,
fecha fija de cobro, socio inactivo), `marcar_membresias_vencidas`, infraestructura de
tests del frontend, y las 3 pantallas de uso diario.

⚠️ **Nada está commiteado todavía.** Es lo primero de la lista.

---

## 1. Commitear lo que ya está hecho 🔴

Son bastantes cambios acumulados y ninguno está guardado. Conviene partirlo en commits
temáticos para que el historial sirva de algo:

| # | Commit sugerido | Qué incluye |
|---|-----------------|-------------|
| 1 | `perf(tests): hasher barato en test_settings` | `backend/gymaccess/test_settings.py` — 412 s → 3.9 s |
| 2 | `feat: fecha fija de cobro por socio` | `socios/models.py` (`sumar_meses`, `Plan.avanzar_periodo`, `Membresia.renovar`), `socios/views.py`, tests |
| 3 | `feat: anti-passback de 4h en el check-in` | `accesos/views.py`, `accesos/tests.py` |
| 4 | `feat: socio inactivo no entra` | `accesos/views.py`, `socios/tests_membresias.py` |
| 5 | `feat: rol coach con clases asignadas` | migración `0003_clase_coach`, `gyms/*`, `usuarios/permissions.py`, `App.jsx`, `Sidebar.jsx`, `AuthContext.jsx` |
| 6 | `fix: "Cobrado este mes" suma pagos reales` | `frontend/src/pages/Pagos.jsx` |
| 7 | `fix: token corrupto ya no deja pantalla en blanco` | `frontend/src/lib/jwt.js`, `AuthContext.jsx` |
| 8 | `test: suite de regresión del frontend` | `vite.config.js`, `src/test/*`, los 5 archivos `*.test.jsx`, `package.json`, `ci.yml` |
| 9 | `a11y: labels ligados en el formulario de socios` | `frontend/src/pages/Socios.jsx` |
| 10 | `docs: plan de regresión y siguientes pasos` | los dos `.md` |

Rama sugerida: `feat/suite-regresion-y-reglas-de-cobro`. **No hacer push a `main` directo.**

---

## 2. Producto: lo que el usuario final todavía no ve 🔴

Esto no son tests, es funcionalidad incompleta. Va antes que ampliar cobertura porque
afecta a quien usa el sistema hoy.

### 2.1 Mostrar la fecha de corte en Pagos

El backend ya calcula bien la fecha fija, pero **recepción no la ve**. Falta que la
pantalla diga "Próximo pago: 24 de septiembre" al cobrar y en el listado.

- Mostrar `fecha_fin` resultante en el modal de confirmación, **antes** de cobrar
  ("al confirmar, su próximo pago será el 24 de octubre").
- Columna "Próx. pago" en el listado de pendientes.
- Distinguir visualmente al que está dentro de los 30 días de gracia del que ya cuenta
  como reinscripción — son cobros distintos y recepción debe saberlo antes de cobrar.

### 2.2 Dejar editar la fecha de corte (sólo admin)

Fue una condición explícita de la regla: *"a menos que el admin edite esa fecha, es el
único caso que puede modificarla"*. El endpoint ya lo permite (`PATCH /socios/membresias/{id}/`)
y hay un test que lo cubre, pero **no hay UI**. Hoy sólo se puede hacer por API.

### 2.3 Enrutar o borrar `Accesos.jsx` y `Membresias.jsx`

Ambas al 0 % de cobertura porque no están en `App.jsx`. Además usan el tema claro viejo
(`bg-white`, `text-gray-800`): si alguien las enruta tal cual, desentonan con todo lo demás.
Decidir: se enrutan y se reestilizan, o se borran.

---

## 3. Terminar la suite del frontend 🟠

Estado por pantalla, ordenado por lo que falta:

| Módulo | Cobertura | Prioridad | Por qué |
|--------|-----------|-----------|---------|
| `Accesos.jsx` | **0 %** | ⚪ | Sin ruta — decidir primero (§2.3) |
| `Membresias.jsx` | **0 %** | ⚪ | Sin ruta — decidir primero (§2.3) |
| `Equipamiento.jsx` | **10 %** | 🟡 | CRUD simple, sólo admin |
| `Notificaciones.jsx` | **11 %** | 🟡 | Historial de lectura |
| `Login.jsx` | **28 %** | 🟠 | Puerta de entrada de todos |
| `Clases.jsx` | **31 %** | 🟠 | Ahora carga el rol coach |
| `Configuracion.jsx` | **44 %** | 🟠 | Alta de planes = precios |
| `Navbar.jsx` | **46 %** | 🟠 | Campana de notificaciones |
| `axios.js` | **53 %** | 🔴 | **Refresh de token, ver §3.1** |
| `Reportes.jsx` | **58 %** | 🟠 | Números que ve el dueño |
| `AuthContext.jsx` | **62 %** | 🟠 | Faltan las ramas de login/logout |
| `Dashboard.jsx` | **81 %** | 🟢 | Casi listo |
| `Socios.jsx` | **81 %** | 🟢 | Listo |
| `Pagos.jsx` | **74 %** | 🟢 | Listo |
| `CheckIn.jsx` | **86 %** | 🟢 | Listo |
| `Sidebar.jsx` | **88 %** | 🟢 | Listo |
| `Layout.jsx` | **89 %** | 🟢 | Listo |

### 3.1 `axios.js` es el más urgente de los que faltan

Las líneas 15–24 sin cubrir **son justo el interceptor de refresh**: lo que decide si a
alguien se le cierra la sesión a media jornada. Casos a cubrir (§7.2 `A-F3-*` del plan):

- Un 401 dispara refresh y **reintenta** la petición original.
- Refresh fallido → limpia storage y va a `/login`.
- Un 401 sin `refresh` en storage no entra en bucle.
- Un 403 **no** dispara refresh.
- **H10**: 4 peticiones con 401 simultáneo deben producir **un solo** refresh.
  Hoy dispara 4 en paralelo y los últimos 3 pueden quedar con token viejo — hay que
  arreglar el código, no sólo probarlo.

### 3.2 Casos específicos del rol coach que faltan

Ya está la matriz de rutas, pero no el comportamiento de las pantallas:
- `Clases.jsx` con rol coach: ve sólo sus clases y **sin** botones de editar/borrar.
- `Socios.jsx` con rol coach: sólo lectura.

---

## 4. End-to-end con Playwright 🟠

Es donde está el mayor retorno por test: atrapa lo que ningún test de componente ve,
porque cruza backend y frontend de verdad.

| Flujo | Qué recorre |
|-------|-------------|
| `E2E-01` **Jornada de recepción** | login → check-in → escanear al corriente (verde) → escanear vencido (rojo) → aparece la notificación → Pagos → cobrar → volver a escanear → entra |
| `E2E-02` **Jornada de admin** | login → dashboard → alta de socio con plan → ver su QR → alta de clase → alta de equipamiento (genera notificación) → reportes cuadran |
| `E2E-03` **Frontera de roles** | recepción escribe a mano `/dashboard`, `/reportes`, `/configuracion`, `/equipamiento` → las 4 rebotan |
| `E2E-04` **El coach** | login coach → aterriza en Clases → ve sólo las suyas → `/pagos` a mano lo rebota |
| `E2E-05` **Sesión** | borrar `access` de localStorage → refresh transparente → borrar `refresh` → va a login |
| `E2E-06` **Aislamiento visible** | dos gyms; admin del A no ve ni un dato del B en ninguna pantalla |
| `E2E-07` **Fecha fija de cobro** | socio con corte el 24 → cobrar el 19 → verificar en pantalla que sigue siendo el 24 |
| `E2E-08` **Responsive** | a 390 px: sidebar como drawer, check-in usable con teclado en pantalla |

Montaje: `npm i -D @playwright/test`, backend con `seed_demo` en BD de prueba,
`webServer` en la config para que levante front y back solos.

---

## 5. Puertas de CI 🟡

Sobre lo que ya existe en `.github/workflows/ci.yml`:

| Puerta | Estado |
|--------|--------|
| `oxlint` | ✅ ya está |
| `vite build` | ✅ ya está |
| Tests Django | ✅ ya está |
| Tests Vitest | ✅ **agregado hoy** |
| Cobertura backend ≥ 90 % | ⬜ pendiente (hoy 96 %, hay margen) |
| Cobertura frontend ≥ 70 % | ⬜ pendiente (hoy 57 %, primero §3) |
| Playwright E2E en PR | ⬜ pendiente (§4) |

---

## 6. Deuda técnica pendiente

Los hallazgos del plan que siguen abiertos, con lo que se decidió:

| # | Hallazgo | Estado |
|---|----------|--------|
| H1 | `clases_restantes` nunca se valida ni decrementa | ⏸️ **Pospuesto por decisión del dueño.** Un paquete de 10 clases da entradas ilimitadas hoy. Atender antes de vender paquetes de clases en serio |
| H2 | Anti-passback | ✅ Resuelto — ventana de 4 h |
| H3 | Token corrupto = pantalla blanca | ✅ Resuelto — `lib/jwt.js` |
| H4 | `Accesos.jsx` / `Membresias.jsx` sin ruta | ⬜ Pendiente (§2.3) |
| H5 | `coach` indistinguible de `recepcion` | ✅ Resuelto |
| H6 | `SucursalViewSet` no valida el gym al escribir | ⬜ **Pendiente** — fuga multi-tenant en escritura |
| H7 | `Socios.jsx` asume `sucursales[0]` | ⬜ **Pendiente** — inofensivo con 1 sucursal, incorrecto con 2+ |
| H8 | Clases sin validar solape ni `hora_fin > hora_inicio` | ⬜ Pendiente |
| H9 | `inscritos` puede superar `cupo_max` | ⬜ Pendiente |
| H10 | Refresh de axios sin control de carrera | ⬜ Pendiente (§3.1) |
| H11 | Suite lenta por PBKDF2 | ✅ Resuelto — 105× más rápida |

**Nuevo:** el `seed_demo.py` sigue al 0 % (97 líneas). No es urgente — es un comando de
demo — pero si se rompe, nadie se entera hasta que falla una presentación a un cliente.

---

## 7. Suite manual — cuando llegue el lector QR 🖐️

Los 37 casos están en [`PLAN_REGRESION.md` §8](PLAN_REGRESION.md). Resumen de bloques:

| Bloque | Casos | Cuándo |
|--------|-------|--------|
| **Lector QR** (`M-QR-01..15`) | 15 | ⏳ Al recibir el equipo |
| **Lector de huella** (`M-HU-01..07`) | 7 | Cuando esté el agente en la PC |
| **Dispositivos y visual** (`M-UI-01..09`) | 9 | Antes de cada release |
| **Operación real** (`M-OP-01..06`) | 6 | Una vez por release, en el gym |

Los tres que más importan al llegar el lector, porque el código asume cosas del hardware
que nadie ha verificado todavía:

- `M-QR-02` — que el lector mande Enter solo (todo `CheckIn.jsx` depende de eso).
- `M-QR-11` — que el lector esté en layout de teclado inglés: si no, los guiones de
  `R3B-QR-00001-1234` salen cambiados y ningún código funciona.
- `M-QR-13` — kiosco 8 h seguidas sin degradarse.

**Añadir a la lista manual** ahora que existen las reglas nuevas:

- `M-OP-07` — **Anti-passback**: escanear al mismo socio 3 veces en 10 minutos. La puerta
  abre las 3 veces, pero el historial registra **una** visita.
- `M-OP-08` — **Anti-passback, ventana larga**: entrar en la mañana y volver por la tarde
  (>4 h). Debe contar como dos visitas.
- `M-OP-09` — **Fecha fija de cobro**: cobrarle a un socio 5 días antes de su corte y
  verificar en pantalla que su próxima fecha no se movió.
- `M-OP-10` — **Reinscripción**: cobrarle a alguien vencido hace más de 30 días y
  verificar que su día de corte pasa a ser hoy.
- `M-OP-11` — **Veto**: marcar a un socio como inactivo con membresía vigente e intentar
  entrar. Debe rechazarlo con "socio suspendido".
- `M-OP-12` — **Coach**: entrar con una cuenta de coach y confirmar que no aparece Pagos
  por ningún lado, ni en el menú ni escribiendo `/pagos` a mano.

---

## 8. Orden recomendado

```
1. Commitear lo hecho (§1)                      ← primero, hay mucho sin guardar
2. Mostrar la fecha de corte en Pagos (§2.1)    ← lo usa recepción todos los días
3. axios.js + arreglar H10 (§3.1)               ← el que cierra sesiones sin motivo
4. Playwright E2E-01 y E2E-07 (§4)              ← mayor retorno por test
5. Resto de pantallas del frontend (§3)         ← mecánico
6. Puertas de cobertura en CI (§5)              ← cuando haya margen
7. Suite manual (§7)                            ← al llegar el lector QR
```

---

## Comandos

```bash
# Backend — 289 tests en ~7 s
cd backend
DJANGO_SETTINGS_MODULE=gymaccess.test_settings ../venv/Scripts/python.exe manage.py test

# Backend con cobertura
../venv/Scripts/python.exe -m coverage run --source='.' \
  --omit='*/migrations/*,*/venv/*,manage.py,*/tests*,*/seed_demo.py' manage.py test
../venv/Scripts/python.exe -m coverage report -m

# Frontend — 88 tests
cd frontend
npm test
npm run test:watch                              # durante el desarrollo
npm run test:coverage -- --no-file-parallelism  # el flag evita un flake del instrumentador
```
