# Resumen de arreglos — GymAccess

**10 de agosto de 2026** · Rama `fix/aislamiento-multitenant-y-vigencia-membresias` · commit `0e95961`

8 bugs corregidos. Cada uno se reprodujo contra el servidor antes de tocar código y se
reverificó después. Suite: **249 tests, 0 fallos, 0 expected failures** (antes tenía 8).

---

## Qué se arregló

| # | Problema | Sev. | Antes | Después |
|---|---|---|---|---|
| 1 | Membresía vencida se mostraba como activa | Alta | plan vigente con fecha pasada | `null` |
| 2 | La lista y la puerta se contradecían | Alta | lista dice activa, puerta da `403` | coinciden |
| 3 | Membresía futura ya contaba como activa | Media | vigente desde el alta | `null` hasta su `fecha_inicio` |
| 4 | **Escritura cruzada entre gyms** | **Alta** | `201 Created` | `400 Bad Request` |
| 5 | Check-in aceptaba sucursal de otro gym | Media | `200` + registro ajeno | `400` |
| 6 | Check-in sin sucursal | Baja | `500 IntegrityError` | `400` |
| 7 | POST a notificaciones | Baja | `500 IntegrityError` | `405` |
| 8 | Superadmin sin gym daba de alta socio | Baja | `500 IntegrityError` | `400` |

---

## Lo que importa de cada bloque

### El agujero de seguridad (bug #4)

`MembresiaViewSet` filtraba la **lectura** por gym pero no validaba nada en la
**escritura**. Un POST con socio, plan y sucursal de otro negocio devolvía `201` y quedaba
guardado en sus datos.

Dos agravantes que la auditoría original no había registrado:

- **La escritura era ciega.** Quien la ejecutaba recibía `201` pero no podía leer el
  registro de vuelta (`404`), porque la lectura sí filtra. El otro gym recibía una
  membresía activa que nunca creó, sin rastro de origen.
- **No hacía falta ser admin.** El rol **recepción** también podía hacerlo.

Se agregó validación de pertenencia en `perform_create` **y** `perform_update` — la
auditoría sólo señalaba el alta, pero la edición tenía el mismo hueco.

### La causa raíz (bugs #1, #2 y #3)

No eran tres bugs: eran uno visto desde tres ángulos. Había **dos definiciones de
"membresía vigente"** conviviendo:

- el serializer de Socios miraba sólo `estado='activa'`,
- el check-in miraba estado **y** fechas.

Como nada movía el estado a `vencida` al pasar `fecha_fin`, divergían en cuanto una
membresía expiraba. El resultado costaba dinero: el socio dejaba de pagar, desaparecía de
Socios y de Pagos → Atrasados, y se enteraba cuando la puerta lo rechazaba. Nadie lo
perseguía.

Ahora hay **una sola definición**, en el modelo:

```python
Membresia.objects.vigentes()   # socios/models.py
```

La consumen el serializer y el check-in. Mientras vivan ahí no pueden volver a divergir.

### Los tres 500 (bugs #6, #7, #8)

Errores de servidor donde correspondía un rechazo limpio. Ahora devuelven `400` o `405`
con mensaje. Ninguno tenía fuga de datos.

---

## Dos hallazgos durante el arreglo

**El fix que proponía la auditoría para el #7 habría roto la aplicación.** Quitar `'post'`
de `http_method_names` deja en `405` a las acciones `marcar-todas-leidas` y `limpiar`, que
son POST del mismo viewset. Se cerró únicamente `create()`; ambas acciones siguen en `200`.

**Dos tests afirmaban el comportamiento roto.** Esperaban
`assertRaises(IntegrityError)` y se habrían roto al corregir los bugs. Se reescribieron
conservando su intención — nadie puede inyectar notificaciones, nadie puede dejar socios
huérfanos —; lo que cambió es que el rechazo ahora es limpio.

---

## Archivos tocados

| Archivo | Cambio |
|---|---|
| `backend/socios/models.py` | `MembresiaQuerySet.vigentes()` y `.caducadas()` — definición única |
| `backend/socios/serializers.py` | `get_membresia_activa` usa el predicado compartido |
| `backend/socios/views.py` | Validación de pertenencia en membresías; alta de socio sin gym |
| `backend/accesos/views.py` | Validación de sucursal en el check-in; usa el predicado compartido |
| `backend/notificaciones/views.py` | `create()` cerrado con `405` |
| `backend/socios/management/commands/marcar_membresias_vencidas.py` | **nuevo** — saneamiento |
| `backend/gymaccess/settings.py` | `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, CORS por entorno |
| `backend/test.http` | Puerto `8001` + advertencia sobre credenciales del seed |
| `frontend/src/pages/Pagos.jsx` | Filtro de atrasados corregido |
| 4 archivos de tests | 8 `@expectedFailure` eliminados; 2 tests reescritos |

---

## Pendiente (decisión tuya)

**1. Normalizar los datos existentes.** Hay 4 membresías marcadas como activas con fecha
vencida (Carlos, Ana, Luis, Andrés). No se ejecutó nada sobre tu base sin avisar:

```bash
python manage.py marcar_membresias_vencidas --dry-run   # ver qué haría
python manage.py marcar_membresias_vencidas             # aplicar
```

Conviene programarlo a diario, junto a `limpiar_notificaciones`.

**2. Antes de desplegar.** Exportar `DJANGO_SECRET_KEY` (una nueva), `DJANGO_DEBUG=0`,
`DJANGO_ALLOWED_HOSTS` y `DJANGO_CORS_ORIGINS`. Los valores por defecto siguen siendo los
de desarrollo, así que nada cambió localmente.

**3. El Bloque B no se tocó.** Son reglas de negocio, no defectos — decídelas y se
implementan:

- Dar de baja a un socio no le cierra la puerta (el check-in nunca mira `Socio.activo`).
- Clases no tiene restricción de rol: recepción y coach pueden crear, editar y borrar.
- El rol `coach` hereda exactamente los permisos de recepción.
- No hay validación de sobrecupo: `inscritos` puede superar a `cupo_max`.

---

## Documentos relacionados

| Archivo | Contenido |
|---|---|
| `reporte_correcciones_2026-08-10.md` | Antes/después detallado, con código y códigos HTTP |
| `resultados_pruebas_2026-08-10.md` | Evidencia de la reproducción de cada bug |
| `casos_prueba_manuales_2026-08-10.md` | Casos manuales para repetir la verificación |
| `analisis_tests_2026-08-06.md` | Auditoría original |
