# Reporte de correcciones — antes y después

**Fecha:** 10 de agosto de 2026
**Alcance:** los 8 bugs de `analisis_tests_2026-08-06.md`, verificados en
`resultados_pruebas_2026-08-10.md`, más la causa raíz que los originaba.

---

## 1. Resumen

| # | Bug | Sev. | Antes | Después |
|---|---|---|---|---|
| 1 | Membresía vencida se publica como activa | Alta | `membresia_activa` poblado con fecha pasada | `null` |
| 2 | Lista y puerta se contradicen | Alta | lista dice activa / puerta `403` | ambas coinciden |
| 3 | Membresía futura ya cuenta como activa | Media | publicada como vigente | `null` hasta `fecha_inicio` |
| 4 | Escritura cruzada entre gyms | **Alta** | `201 Created` | `400 Bad Request` |
| 5 | Check-in acepta sucursal ajena | Media | `200`, registro en gym ajeno | `400`, no se registra |
| 6 | Check-in sin sucursal | Baja | `500 IntegrityError` | `400` con mensaje |
| 7 | POST a notificaciones | Baja | `500 IntegrityError` | `405 Method Not Allowed` |
| 8 | Superadmin sin gym crea socio | Baja | `500 IntegrityError` | `400` con mensaje |

8 de 8 corregidos y verificados contra el servidor en ejecución.

---

## 2. La causa raíz

Los bugs #1, #2 y #3 no eran tres defectos: eran el mismo, visto desde tres ángulos. El
sistema tenía **dos definiciones distintas de "membresía vigente"**.

**Antes** — el serializer miraba sólo el estado:

```python
# socios/serializers.py
m = obj.membresias.filter(estado='activa').first()
```

…mientras el check-in miraba estado *y* fechas:

```python
# accesos/views.py
Membresia.objects.filter(socio=socio, estado='activa', fecha_inicio__lte=hoy).filter(
    Q(fecha_fin__gte=hoy) | Q(fecha_fin__isnull=True)
).first()
```

Como nada en el backend mueve `estado` de `activa` a `vencida` cuando pasa `fecha_fin`,
las dos definiciones divergían en cuanto expiraba una membresía.

**Después** — una sola definición, en el modelo:

```python
# socios/models.py
class MembresiaQuerySet(models.QuerySet):
    def vigentes(self, hoy=None):
        hoy = hoy or timezone.localdate()
        return self.filter(
            estado='activa',
            fecha_inicio__lte=hoy,
        ).filter(
            models.Q(fecha_fin__gte=hoy) | models.Q(fecha_fin__isnull=True)
        )
```

Serializer y check-in la consumen:

```python
m = obj.membresias.vigentes().first()                    # socios/serializers.py
membresia = Membresia.objects.vigentes().filter(socio=socio).first()   # accesos/views.py
```

Mientras vivan en un solo lugar no pueden volver a divergir.

### Y el saneamiento de los datos

Corregir la lectura no arregla las filas que ya están mal. Se agregó el comando que
faltaba, con el mismo patrón que `limpiar_notificaciones`:

```bash
python manage.py marcar_membresias_vencidas            # marca
python manage.py marcar_membresias_vencidas --dry-run  # sólo reporta
```

Programado por cron/tarea, mantiene `estado` alineado con las fechas. Con la definición
compartida ya no es *necesario* para que el sistema sea correcto — es higiene de datos.

> **Pendiente operativo:** la base actual tiene 4 membresías en ese estado (Carlos, Ana,
> Luis y Andrés). Corre el comando cuando quieras normalizarlas. No se ejecutó en esta
> sesión para no alterar tus datos sin aviso.

---

## 3. Cambio por cambio

### Bug #4 — escritura cruzada entre gyms (el más serio)

`MembresiaViewSet` filtraba la lectura por gym pero no validaba nada en la escritura.

**Antes:** no existía `perform_create`. Un POST con `socio`/`plan`/`sucursal` de otro
negocio devolvía `201` y quedaba escrito en los datos ajenos — y encima invisible para
quien lo creó, porque la lectura sí filtra.

**Después** (`socios/views.py`), siguiendo el patrón que ya usaba `PagoViewSet`:

```python
def _validar_pertenencia(self, serializer):
    gym_id = self.request.user.gym_id
    errores = {}
    for campo, mensaje in (
        ('socio', 'Socio no encontrado'),
        ('plan', 'Plan no encontrado'),
        ('sucursal', 'Sucursal no encontrada'),
    ):
        obj = serializer.validated_data.get(campo)
        if obj is not None and obj.gym_id != gym_id:
            errores[campo] = mensaje
    if errores:
        raise ValidationError(errores)
```

Se aplica en `perform_create` **y** en `perform_update` — el análisis original sólo
señalaba el alta, pero la edición tenía el mismo hueco.

### Bugs #5 y #6 — la sucursal del check-in

**Antes:** `sucursal_id` se tomaba del cliente y se pasaba crudo al `create()`. Si era de
otro gym, se registraba igual; si faltaba, reventaba el INSERT.

**Después** (`accesos/views.py`), una sola comprobación cierra ambos:

```python
if sucursal_id in (None, ''):
    return Response({'sucursal_id': 'Indica la sucursal donde se registra el acceso.'},
                    status=status.HTTP_400_BAD_REQUEST)
try:
    sucursal = Sucursal.objects.get(id=sucursal_id, gym_id=request.user.gym_id)
except (Sucursal.DoesNotExist, ValueError, TypeError):
    return Response({'sucursal_id': 'Sucursal no encontrada.'},
                    status=status.HTTP_400_BAD_REQUEST)
```

La validación va **después** de la del token, para no cambiar el `404` que ya devolvían
los tokens inválidos. El `Acceso` ahora se crea con el objeto validado (`sucursal=sucursal`),
no con el id crudo.

### Bug #7 — POST a notificaciones

El arreglo que proponía el análisis era quitar `'post'` de `http_method_names`. **Eso
habría roto la aplicación**: `marcar-todas-leidas` y `limpiar` son acciones POST del mismo
viewset, y `http_method_names` se evalúa en el `dispatch`, así que las habría dejado en
`405`.

Se cerró sólo el alta:

```python
def create(self, request, *args, **kwargs):
    raise MethodNotAllowed('POST')
```

Verificado que las dos acciones siguen respondiendo `200`.

### Bug #8 — superadmin sin gym

**Antes:** `else: serializer.save()` chocaba con `Socio.gym` NOT NULL.
**Después:** si el usuario no tiene gym, debe indicarlo explícitamente; si no, `400`.

```python
gym_id = self.request.user.gym_id
if not gym_id:
    gym = serializer.validated_data.get('gym')
    if not gym:
        raise ValidationError(
            {'gym': 'El usuario no tiene gym asignado: indica el gym del socio.'}
        )
    gym_id = gym.id
socio = serializer.save(gym_id=gym_id)
```

### Frontend — la pestaña Atrasados

`Pagos.jsx:60` filtraba `m.fecha_fin < hoy && m.estado !== 'activa'`. Como una fecha
pasada ya implica que la membresía no está vigente, la segunda cláusula sólo servía para
**excluir justamente a los morosos** que quedaron marcados como activos.

```js
// antes
const atrasados = membresias.filter(m => m.fecha_fin < hoy && m.estado !== 'activa')
// después
const atrasados = membresias.filter(m => m.fecha_fin && m.fecha_fin < hoy)
```

Ahora la pestaña es correcta aunque el comando de saneamiento no se haya ejecutado.

### Configuración para producción

`settings.py` tenía `SECRET_KEY` en el código, `DEBUG = True` y `ALLOWED_HOSTS = ['*']`
fijos. Se hicieron leíbles por entorno **sin cambiar el comportamiento en desarrollo**
(los valores por defecto son los de siempre):

| Variable | Por defecto (dev) | En producción |
|---|---|---|
| `DJANGO_SECRET_KEY` | la actual | una nueva, secreta |
| `DJANGO_DEBUG` | `True` | `0` |
| `DJANGO_ALLOWED_HOSTS` | `*` | el dominio real |
| `DJANGO_CORS_ORIGINS` | vacío → permite todo | los orígenes reales |

`test.http` apuntaba a `localhost:8000` (el contenedor de otro proyecto). Corregido a
`127.0.0.1:8001` y se le añadió la advertencia sobre las credenciales del seed.

---

## 4. Evidencia: mismas peticiones, antes y después

| Prueba | Antes | Después |
|---|---|---|
| `GET /api/socios/` → Carlos (venció 2026-08-04) | `{"plan":"Regular","fecha_fin":"2026-08-04","estado":"activa"}` | `null` |
| `POST /checkin/` Carlos | `403` | `403` (ahora coincide con la lista) |
| `GET /api/socios/` → Sofía (vigente) | activa | activa |
| `POST /checkin/` Sofía | `200` | `200` |
| `POST /membresias/` cruzado, admin | `201` | `400 {"socio":"Socio no encontrado", ...}` |
| `POST /membresias/` cruzado, recepción | `201` | `400` |
| `POST /checkin/` con sucursal ajena | `200` + registro en gym ajeno | `400 {"sucursal_id":"Sucursal no encontrada."}` |
| `POST /checkin/` sin sucursal | `500 NOT NULL constraint failed: accesos.sucursal_id` | `400 {"sucursal_id":"Indica la sucursal..."}` |
| `POST /notificaciones/` | `500 NOT NULL constraint failed: notificaciones.gym_id` | `405 {"detail":"Método \"POST\" no permitido."}` |
| `POST /socios/` superadmin sin gym | `500 NOT NULL constraint failed: socios.gym_id` | `400 {"gym":"El usuario no tiene gym asignado..."}` |

### Controles de no-regresión

Lo que **debía seguir funcionando** y se comprobó que sigue:

| Control | Resultado |
|---|---|
| Recepción crea membresía en **su propio** gym | `201` |
| `POST /notificaciones/marcar-todas-leidas/` | `200` |
| `POST /notificaciones/limpiar/` | `200` |
| Check-in de socio vigente en su sucursal | `200` |
| Token inválido sigue dando `404` (no `400`) | `404` |

Las pruebas se corrieron creando un gym rival temporal y un superadmin sin gym; **todos
los datos de prueba se eliminaron al terminar** y las nueve tablas quedaron en su conteo
original.

---

## 5. Suite automatizada

| | Antes | Después |
|---|---|---|
| Tests | 249 | 249 |
| Fallos reales | 0 | 0 |
| `expectedFailure` | **8** | **0** |

Los 8 decoradores `@unittest.expectedFailure` se eliminaron: esos tests ahora pasan porque
el comportamiento que describían quedó corregido.

Además hubo que reescribir **dos tests que afirmaban el comportamiento roto**:

- `notificaciones/tests.py::test_cliente_no_puede_inyectar_notificaciones` esperaba
  `assertRaises(IntegrityError)`; ahora espera `405`.
- `usuarios/tests_roles.py::test_superadmin_no_puede_crear_socios_huerfanos` esperaba
  `assertRaises(IntegrityError)`; ahora espera `400`.

En ambos casos se conservó la intención original (nadie puede inyectar notificaciones,
nadie puede dejar socios huérfanos); lo que cambió es que el rechazo ahora es limpio en
lugar de un error de servidor.

---

## 6. Lo que NO se tocó, y por qué

Los puntos del **Bloque B** son comportamientos que el análisis marcó como posibles
decisiones de negocio deliberadas. Cambiarlos sin confirmación alteraría reglas de
operación, no defectos:

- **Dar de baja a un socio no le cierra la puerta.** El check-in sólo mira la membresía,
  nunca `Socio.activo`. ¿Debe una baja administrativa bloquear el acceso?
- **Clases no tiene restricción de rol.** Recepción y coach pueden crear, editar y borrar
  clases. Equipamiento y Gastos sí están reservados a admin.
- **El rol `coach` hereda los permisos de recepción** (no está en `ROLES_ADMIN`).
- **No hay validación de sobrecupo:** `inscritos` puede superar a `cupo_max`.

También quedó fuera el **filtro por estado de membresía en la pantalla de Socios**
(recomendación 5 del análisis): es una función nueva de UI, no la corrección de un
defecto. La necesidad operativa —listar morosos— quedó cubierta por la pestaña
**Pagos → Atrasados**, que ahora sí los incluye.

Dime cuál de estos quieres y lo implemento.

---

## 7. Antes de desplegar

1. Exportar `DJANGO_SECRET_KEY` (una nueva), `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS` y
   `DJANGO_CORS_ORIGINS`.
2. Cambiar los passwords del seed si esa base llega al servidor.
3. Programar `marcar_membresias_vencidas` (diario) junto a `limpiar_notificaciones`.
