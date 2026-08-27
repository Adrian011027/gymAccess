# Estado de la sesión — 21 de agosto de 2026

Continúa `ESTADO_SESION_2026-08-20.md`, que sigue vigente para todo lo que no se
contradiga aquí. Mismo criterio: recoge **por qué**, no solo qué.

Nada commiteado. Todo el trabajo sigue en el working tree.

---

## La base se dejó limpia para pruebas

Round3Boxing (gym id 1) se vació y se resembró a petición del usuario. Se borró:

| Qué | Cuántos |
|---|---|
| Socios | 16 |
| Membresías / Pagos | 15 / 13 |
| Accesos / Métodos QR | 74 / 16 |
| Clases | 5 |
| Equipamiento | 17 |
| Gastos | 6 |
| Sucursal "Matriz Centro" | eliminada |

Membresías, pagos, accesos y QR **no se borraron uno a uno**: caen en cascada al
borrar el socio. El plan "Mensualidad Round3" ($499) sobrevivió a propósito.

**Respaldo previo**: `db.sqlite3.antes-de-limpiar` en el scratchpad de la sesión.
Es la única copia de los 16 socios originales.

Script de siembra: `seed_round3.py`, mismo scratchpad. Es idempotente en el staff
(`get_or_create` por email) pero **destructivo en el borrado**: no volver a correrlo
sin leerlo.

### Sucursales

`Estrella` (id 2) y `San Sebastián` (id 3). Ya no hay id 1.

### Staff — todos con contraseña `test1234`

| Email | Rol | Sucursal | Días |
|---|---|---|---|
| coach.ramirez@round3boxing.com | coach | Estrella | Lun · Mié · Vie |
| coach.mendoza@round3boxing.com | coach | Estrella | Mar · Jue · Sáb |
| coach.trejo@round3boxing.com | coach | San Sebastián | Lun · Mié · Vie |
| coach.salgado@round3boxing.com | coach | San Sebastián | Mar · Jue · Sáb |
| recepcion@round3boxing.com | recepción | Estrella | — |
| recepcion.sansebastian@round3boxing.com | recepción | San Sebastián | — |

`admin@admin.com` (superadmin) y `diego@round3boxing.com` (admin) también quedaron
en `test1234`.

A cada empleado se le puso `sucursales_permitidas` con su sucursal: el serializer
**rechaza** un `horario_semanal` que apunte a una sucursal que no esté en esa lista
(`usuarios/serializers.py:114`). Si se reasigna a alguien, hay que mover las dos.

### Tienda

| Producto | Categoría | Precio | Costo | Stock por sucursal |
|---|---|---|---|---|
| Vendas | accesorio | $120 | $70 | 20 |
| Bucal | accesorio | $150 | $90 | 15 |
| Agua 600ml | bebida | $20 | $10 | 60 |
| Powerade | bebida | $35 | $22 | 40 |

Precios y costos son inventados, plausibles para un box en MXN. Nadie los validó
contra la realidad del negocio.

Esto cierra el pendiente #2 del 20 de agosto (inventario en cero bloqueaba el POS).
El pendiente #1 (socio sin sucursal) desapareció con el borrado.

---

## Siguientes pasos

### 1. El alta de socio se rompe a partir de la segunda sucursal — SIGUE PENDIENTE

> **Estado:** el camino de *edición* ya lo hace bien (`aplicarPlan` usa la sucursal
> del socio). La línea del **alta** sigue sin arreglar. Lo de abajo describe el alta.

`frontend/src/pages/Socios.jsx:233` decide la sucursal de la membresía así:

```js
sucursal: socioData.sucursal || sucursales[0]?.id,
```

Cuando recepción deja el campo de sucursal vacío, `socioData.sucursal` va `null`.
El backend hace lo correcto y registra al socio en la sucursal de quien lo da de
alta (`socios/views.py:71`), pero el frontend nunca se entera: cae en
`sucursales[0]`, que es **Estrella para todos** porque la lista llega ordenada por id.

Reproducido como recepción de San Sebastián:

| Paso | Resultado |
|---|---|
| `POST /socios/` | 201 — socio en San Sebastián (id 3) |
| `POST /socios/membresias/` con `sucursal: 2` | **400** `"Solo puedes registrar movimientos en tu sucursal."` |

El socio queda creado **sin membresía** y aparece como "Sin plan". El toast dice
"Socio creado, pero no se pudo asignar el plan", que es fácil de leer como un fallo
menor cuando en realidad el alta quedó a medias.

**Arreglo**: usar la sucursal que el backend ya devolvió en el 201 (`socio.sucursal`)
en vez de adivinarla desde `sucursales[0]`.

Por qué no se había visto: la recepción de Estrella nunca lo sufre, porque para ella
`sucursales[0]` acierta por casualidad. El bug **solo existe desde que hay dos
sucursales**. Los socios 18 y 19 (Ángel Adrián, Hugo Mora) se dieron de alta en
Estrella y por eso sí tienen membresía.

Nota aparte: que el plan sea obligatorio en el alta **es deliberado**, no el bug
(`<select required>` en `Socios.jsx:631`).

### 2. Planes por sucursal o de cadena

Hoy `Plan` cuelga solo del gym, así que el catálogo y los precios son únicos para
todo el negocio. Se necesita que un plan sea de una sucursal concreta **o** de toda
la cadena.

**Diseño recomendado: FK `sucursal` nullable en `Plan`, donde nulo = toda la cadena.**

No es una invención: el codebase ya resuelve exactamente esto tres veces con esa
forma — `Clase`, `Equipamiento` y `Gasto` tienen el mismo campo con el comentario
"Nulo = todas las sucursales". Y `GastoViewSet.get_queryset` ya trae el patrón de
lectura:

```python
return qs.filter(models.Q(sucursal_id=objetivo) | models.Q(sucursal__isnull=True))
```

| Archivo | Cambio |
|---|---|
| `socios/models.py` | `sucursal = FK(Sucursal, null=True, blank=True, related_name='planes')` + migración |
| `socios/views.py` → `PlanViewSet.get_queryset` | Scoping como `GastoViewSet`: planes de cadena + los de la sucursal activa |
| `socios/views.py` → `PlanViewSet` | `validar_escritura` al crear/editar, para que nadie cree planes en el local de al lado |
| `socios/serializers.py` | Exponer `sucursal_nombre` en `PlanSerializer` |
| `socios/views.py` → `MembresiaViewSet._validar_pertenencia` | Rechazar un plan cuya sucursal no coincida con la de la membresía |
| `frontend/src/pages/Configuracion.jsx` | Selector "Todas las sucursales" / sucursal concreta en el alta de plan |
| `frontend/src/pages/Socios.jsx` | El desplegable ya lee `/socios/planes/`, se filtra solo — más el arreglo del punto 1 |

El renglón de `_validar_pertenencia` importa más de lo que parece: sin él nada
impide vender el plan de Estrella en San Sebastián, y el scoping de lectura no lo
detiene porque la escritura va por otro camino. Es el mismo agujero que ya se tapó
ahí para socio/plan/sucursal.

**Precio distinto por sucursal** sale de esto sin código extra: son dos filas,
"Mensualidad Estrella $499" y "Mensualidad San Sebastián $599". El costo honesto es
que un reporte agrupado por plan las cuenta como productos distintos.

**Alternativa descartada por ahora**: dejar `Plan` a nivel cadena y añadir una tabla
`PrecioPlanSucursal` que solo sobreescriba el precio. Más limpio para reportar, más
código, y deja sin resolver la pregunta de disponibilidad. Con dos sucursales no lo
vale; a diez, sí. Empezar por el FK **no cierra esa puerta**: la tabla de precios se
puede añadir encima después.

---

## Cosas que hay que saber antes de seguir

### El rol `coach` no existe en el frontend

`AuthContext.jsx:44` define `isAdmin` como `admin || superadmin`. Un coach cae en la
rama "no admin", aterriza en `/checkin` (`App.jsx:23`) y ve el mismo menú que
recepción. El rol existe en el modelo, en el JWT y en Empleados, pero **la UI no lo
distingue de recepción**. Ahora hay 4 coaches en la base, así que el hueco ya se nota.

### El login tiene throttle de 10/min por IP

`DEFAULT_THROTTLE_RATES.login` en `gymaccess/settings.py:111`. Probar varias cuentas
seguidas devuelve `429` y se lee como "credenciales incorrectas". Para verificar
contraseñas en lote conviene `authenticate()` en el shell, que no pasa por el throttle.

Relacionado y sin arreglar: el frontend reintenta `POST /api/auth/refresh/` en bucle
(~15 veces en un segundo) cuando el token está vencido, y él solo dispara el 429.
Se ve en el log del backend. Parece bug de cliente, no de servidor.

### El backend en background se muere solo

Lanzado como hijo de una tarea en background, el proceso se mata cada pocos minutos
sin crash ni traceback. El Vite sobrevive porque `npm run dev` lo deja como proceso
nieto. Si hace falta que aguante, lanzarlo desacoplado (`Start-Process` en PowerShell)
o directamente en una terminal propia.

---

## Hecho al final de la sesión

### Cambiar el plan desde editar socio

El bloqueo era del backend: `membresia_reciente` devolvía el **nombre** del plan y no
su id, así que un `<select>` no podía preseleccionarse. Se añadió `plan_id`
(`socios/serializers.py`) y el campo salió del `{!form.id && ...}` que lo escondía.

Dos caminos, los dos verificados contra la API:

| Caso | Llamada | Verificado |
|---|---|---|
| Socio con membresía | `PATCH /socios/membresias/<id>/` | 200 |
| Socio "Sin plan" | `POST /socios/membresias/` en **su** sucursal | 201, vigente hoy |

**Cambiar de plan no mueve la fecha de vencimiento**, a propósito. Se probó pasando
una membresía a un plan trimestral de 90 días: la vigencia se quedó donde estaba. Si
recalculara, bastaría con "cambiar de plan" a uno más largo para saltarse la
autorización con contraseña de *Próximo pago*. El período nuevo lo aplica el
siguiente pago (`PagoViewSet.perform_create`). La UI lo avisa al tocar el select.

### Las fechas iban en UTC

`new Date().toISOString()` da la fecha **UTC**. En México (UTC−6), después de las
18:00 devuelve *mañana*. Las membresías creadas de noche nacían con
`fecha_inicio` = mañana y `Membresia.vigentes()` (que exige `fecha_inicio <= hoy`)
las dejaba fuera: **el check-in rechazaba al socio que acababa de pagar**. Se
descubrió porque `membresia_activa` salía `null` con la membresía recién creada.

Arreglado con `fechaLocal()` / `enDias()` en `Socios.jsx`, en el alta y en la
edición. Las dos membresías que ya estaban mal se corrigieron a mano.

**Quedan dos sitios con el mismo patrón, sin tocar**: `Dashboard.jsx:70-71` (rangos
de los reportes) y `Legal.jsx:73` (`vigente_desde` — publicar un documento "mañana"
significa que hoy no obliga a nadie).

### Filtro por rol en Empleados

Chips con conteo (`Todos 8 · Admin 1 · Coach 4 · Recepción 2`). Solo se listan los
roles que existen en la plantilla. La etiqueta cruda (`recepcion`) pasó a legible.

### Panel del SaaS — bloque A

App nueva `backend/saas/`. Vive aparte y **no** extiende los ViewSets existentes: los
del resto del proyecto miran *dentro* de un gimnasio (`request.user.gym_id`), estos
miran *a través* de todos. Mezclar los dos alcances en una misma vista es como se
filtran datos de un cliente a otro.

| Endpoint | Qué hace |
|---|---|
| `GET /api/saas/resumen/` | Números del negocio: gyms, sucursales, empleados, socios, socios vigentes |
| `GET /api/saas/tenants/` | Gimnasios con sus contadores y su admin |
| `POST /api/saas/tenants/` | Alta completa: gym + primera sucursal + admin, en una transacción |
| `POST /api/saas/tenants/<id>/suspender/` · `/reactivar/` | Corta o restituye el acceso sin tocar datos |
| `POST /api/saas/tenants/<id>/impersonar/` | JWT del admin del gym para dar soporte |
| `GET /api/saas/tenants/<id>/accesos-soporte/` | Bitácora de esas entradas |

Decisiones que no se deducen del código:

- **`EsSuperAdmin` no reutiliza `ROLES_ADMIN`.** Esa tupla mete a `admin` y
  `superadmin` en el mismo saco; aquí `admin` es el dueño de *un* gimnasio y dejarlo
  entrar le daría los demás clientes del SaaS. Verificado: devuelve **403**.
- **`DELETE` de un tenant está prohibido** y responde 400 explicando que se suspenda.
  De un gym cuelgan pagos y bitácora de accesos que el CFF obliga a conservar cinco
  años; un borrado los arrastra por cascada.
- **Impersonar exige motivo** y escribe en `AccesoSoporte` (quién, a quién, motivo,
  IP, hora). Ver datos personales de socios ajenos no puede ser silencioso. El token
  lleva además `soporte: true` y `soporte_de`, para que el rastro viaje en él.
  Verificado: el token de soporte ve **solo** ese gimnasio y **no** puede volver a
  entrar al panel del SaaS (403).
- **Las anotaciones se llaman `num_*`.** `sucursales`, `socios` y `usuarios` ya son
  `related_name` en `Gym` y Django rechaza una anotación homónima; el serializer las
  reexpone con `source`.

Frontend: ruta `/saas` con guard `SaasRoutes` (solo `esSuperAdmin`), enlace propio en
el sidebar, y `HomeRedirect` manda al superadmin ahí en vez de al dashboard vacío.
`AuthContext` ganó `esSuperAdmin`, `enSoporte`, `entrarComoSoporte` y `volverAlPanel`
—el token del superadmin se guarda aparte para poder volver sin re-loguearse—. En
sesión de soporte, `Layout` pinta una franja naranja fija con la salida encima.

### Lo que sigue del panel

Bloques **B** (suscripciones y cobranza: `PlanSaaS`, `Suscripcion`, `PagoSaaS`,
morosidad, MRR — hoy no existe nada de esto en la base), **C** (uso contra los límites
del paquete contratado) y **D** (métricas del negocio: MRR, altas, bajas, churn).
El detalle está en `PRECIOS_Y_PAQUETES.md`.
