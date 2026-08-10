# Resultados de ejecución — casos A5 a A10

**Fecha:** 10 de agosto de 2026
**Entorno:** backend `127.0.0.1:8001`, frontend `localhost:5173`, `DEBUG=True`, SQLite local.
**Casos:** los definidos en `casos_prueba_manuales_2026-08-10.md`.

## Resumen

| Caso | Bug | Severidad | Resultado | Veredicto |
|---|---|---|---|---|
| A5 | #3 Membresía futura publicada como activa | Media | `200` en lista / `403` en puerta | **CONFIRMADO** |
| A6 | #4 Escritura cruzada entre gyms | **Alta** | `201 Created` | **CONFIRMADO — peor de lo documentado** |
| A7 | #5 Check-in acepta sucursal ajena | Media | `200` permitido, registro en gym ajeno | **CONFIRMADO** |
| A8 | #6 Check-in sin sucursal | Baja | `500 IntegrityError` | **CONFIRMADO** |
| A9 | #7 POST a notificaciones | Baja | `500 IntegrityError`, sin fuga | **CONFIRMADO** |
| A10 | #8 Superadmin sin gym crea socio | Baja | `500 IntegrityError` | **CONFIRMADO** |

6 de 6 reproducidos. Ninguno resultó falso positivo.

Antes de ejecutar se respaldó `db.sqlite3`. Al terminar, todas las tablas volvieron a su
conteo original (delta 0 en Gym, Sucursal, Socio, Membresía, Plan, Pago, Usuario, Acceso,
Notificación). No quedó basura de pruebas en la base.

---

## A5 · Membresía futura se publica como activa (bug #3)

**Preparación:** socio `QA-Futura Test` (id 16), membresía con `fecha_inicio = 2026-08-17`
(7 días en el futuro), `fecha_fin = 2026-09-16`, `estado = 'activa'`.

**Lista de socios** — `GET /api/socios/`:

```json
"membresia_activa": {"id": 16, "plan": "3 Meses", "fecha_fin": "2026-09-16", "estado": "activa"}
```

**Check-in** — `POST /api/accesos/checkin/`:

```json
{"acceso":"denegado","socio":"QA-Futura Test","motivo":"membresía no activa"}
HTTP 403
```

**Confirmado.** Recepción ve un plan vigente y cobra en consecuencia; la puerta lo rechaza.
Mismo origen que el bug #1: `get_membresia_activa` no aplica `fecha_inicio__lte=hoy`.

---

## A6 · Escritura cruzada entre gyms (bug #4) — el hallazgo más serio

**Preparación:** segundo gym `GymRival QA` (id 2) con sucursal (id 2), socio `Victima
Rival` (id 17) y plan `Rival Mensual` (id 6).

**Ataque** — autenticado como **admin de Round3Boxing (gym 1)**:

```
POST /api/socios/membresias/
{"socio":17,"plan":6,"sucursal":2,"fecha_inicio":"2026-08-10","fecha_fin":"2026-09-10","estado":"activa"}

HTTP 201
{"id":17,"socio_nombre":"Victima Rival","plan_nombre":"Rival Mensual","plan_precio":"500.00", ...}
```

Verificado en la BD: la membresía 17 quedó con `socio.gym_id = 2` y `sucursal.gym_id = 2`.
Es decir, **quedó escrita dentro de los datos del otro negocio**.

### Dos agravantes que el análisis del 6 de agosto no registraba

**1. La escritura es ciega.** El mismo usuario que la creó no puede leerla de vuelta:

```
GET /api/socios/membresias/17/   -> HTTP 404
GET /api/socios/membresias/      -> ids visibles: [1..15]  (la 17 no aparece)
```

La lectura sí filtra por gym. Resultado: el atacante escribe en la base del otro gym y el
registro le queda invisible; el gym víctima recibe una membresía activa que nunca creó,
sin rastro de quién la metió. Peor para auditoría que un cruce visible en ambos lados.

**2. No hace falta ser admin.** El mismo POST con el token de **recepción** también pasa:

```
HTTP 201  {"id":18,"socio_nombre":"Victima Rival", ...}
```

El rol de menor privilegio del sistema puede escribir en otro tenant.

### Control de contraste

`PagoViewSet` sí valida, como decía el análisis:

```
POST /api/socios/pagos/  {"membresia":17,...}
HTTP 400  {"membresia":"Membresía no encontrada"}
```

El patrón correcto ya existe en el código (`socios/views.py:62-64`); a
`MembresiaViewSet` simplemente no se le aplicó.

---

## A7 · Check-in acepta sucursal de otro gym (bug #5)

Socio propio (Sofía, gym 1) con `sucursal_id = 2` (sucursal del gym rival):

```json
{"acceso":"permitido","socio":"Sofía Martínez","plan":"3 Meses","vence":"2026-10-03"}
HTTP 200
```

Registro resultante en la BD:

```
acceso 54 | socio Sofía Martínez (gym 1) | sucursal Rival Centro (gym 2) | permitido
```

**Confirmado.** El token QR sí se valida contra el gym del usuario; la sucursal no. El
acceso queda contabilizado en la bitácora y los reportes del otro negocio.

---

## A8 · Check-in sin sucursal revienta (bug #6)

```
POST /api/accesos/checkin/  {"token":"R3B-QR-00004-2842"}
HTTP 500
IntegrityError: NOT NULL constraint failed: accesos.sucursal_id
```

**Confirmado.** Debería ser `400`. No se creó ningún registro de acceso.

---

## A9 · POST a notificaciones revienta (bug #7)

```
POST /api/notificaciones/  {"tipo":"pago_vencido","mensaje":"prueba QA"}
HTTP 500
IntegrityError: NOT NULL constraint failed: notificaciones.gym_id
```

**Confirmado, sin fuga.** Se verificó el conteo después del intento: la notificación
"prueba QA" nunca se creó. Solo existen las 4 generadas legítimamente por check-ins
denegados. Debería responder `405`.

---

## A10 · Superadmin sin gym crea socio (bug #8)

Usuario `super@qa.local`, `rol='superadmin'`, `gym=None`. Login correcto.

```
POST /api/socios/  {"nombre":"QA","apellido":"SinGym","email":"qa@singym.local"}
HTTP 500
IntegrityError: NOT NULL constraint failed: socios.gym_id
```

**Confirmado.** Solo afecta a superadmins sin gym; admin y recepción siempre tienen gym.

---

## Nota sobre los 500

Los tres `IntegrityError` (A8, A9, A10) se vieron con `DEBUG=True`, que devuelve el
traceback completo de Django en la respuesta HTTP. **En producción con `DEBUG=False` esas
mismas rutas devuelven un `500` genérico**, pero el fallo sigue ahí y sigue siendo un
error de servidor donde correspondía un `400`/`405`. Vale la pena confirmar antes de
desplegar que `DEBUG=False` y que `ALLOWED_HOSTS` deja de ser `['*']`
(`gymaccess/settings.py:8,10`).

---

## Prioridad sugerida tras la ejecución

1. **A6 (bug #4)** — sube de prioridad. Escritura cruzada entre tenants, ciega para el
   atacante, disponible desde el rol de recepción. El arreglo es copiar el patrón de
   `PagoViewSet.perform_create`.
2. **Bug #1 + A5/A7** — el predicado de "membresía vigente" debe vivir en un solo lugar
   (manager o método del modelo `Membresia`) y usarse tanto en el serializer como en el
   check-in. Cierra #1, #2 y #3 de una vez.
3. **A7 (bug #5)** — validar `sucursal_id` contra las sucursales del gym; cierra también A8.
4. **A9, A10** — respuestas correctas en lugar de 500.

---

## Estado del entorno al cerrar

- Suite automatizada: **249 tests · 8 expected failures · 0 fallos** (~6 min).
- Base de datos: restaurada, delta 0 en todas las tablas.
- Respaldo previo guardado como `db.sqlite3.bak-preA5A10` en el scratchpad de la sesión.
- Backend y frontend siguen corriendo.
