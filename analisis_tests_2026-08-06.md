# Análisis de GymAccess — 6 de agosto de 2026

Sesión de arranque de entorno, verificación de credenciales y auditoría por módulos
con cobertura de tests automatizados.

---

## 1. Arranque del entorno: conflicto de puerto

### Síntoma

El login desde el frontend devolvía "credenciales inválidas" con los dos usuarios del
seed, aun siendo correctos.

### Causa raíz

El contenedor Docker `saas_agenda_backend` (de otro proyecto) publica `0.0.0.0:8000` y
`[::]:8000`. Django solo alcanzó a enlazar `127.0.0.1:8000`. En Windows, `localhost`
resuelve a `::1` antes que a `127.0.0.1`, así que el proxy de Vite (`/api` →
`localhost:8000`) entregaba todas las peticiones al backend de `saas_agenda`.

El mensaje `"Usuario/email y contraseña son requeridos."` que aparecía en pantalla no
existe en este repositorio: venía de la otra aplicación.

### Solución aplicada

| Cambio | Detalle |
|---|---|
| `frontend/vite.config.js:11` | Proxy `/api` → `http://127.0.0.1:8001` (antes `http://localhost:8000`) |
| Backend | Corre en `127.0.0.1:8001` |

Los contenedores de `saas_agenda` quedaron intactos (8000 / 3000 / 8080).

### Estado final

- Backend GymAccess → `http://127.0.0.1:8001`
- Frontend → `http://localhost:5173`
- Login verificado end-to-end a través del proxy: `200 OK` + tokens JWT.

### Pendiente

`backend/test.http:4` sigue apuntando a `http://localhost:8000`. Si se usa desde el REST
Client de VS Code, pegará contra Docker. Cambiar `@baseUrl` a `http://127.0.0.1:8001`.

---

## 2. Credenciales

Verificadas contra los hashes de `backend/db.sqlite3` con `check_password()`.

| Rol | Email | Password |
|---|---|---|
| admin (superuser) | `diego@round3boxing.com` | `Diego1234` |
| recepcion | `recepcion@round3boxing.com` | `Recepcion123` |

Solo existen esos dos usuarios en la tabla `usuarios`. Los passwords se guardan como
`pbkdf2_sha256$1200000$...` (no reversibles); los valores en claro salieron de
`backend/test.http`, generados por `manage.py seed_demo`.

> **Nota de seguridad:** `backend/test.http` está commiteado con passwords en claro. Es
> un seed de desarrollo local, así que el riesgo es bajo, pero si esa base o esos
> usuarios llegan a producción hay que cambiar ambos passwords y sacar el archivo del
> repositorio.

---

## 3. Cobertura de tests

### Antes

68 tests, todos en verde.

### Después

**249 tests** (181 nuevos), organizados por módulo:

| Archivo | Tests | Módulo cubierto |
|---|---|---|
| `socios/tests_membresias.py` | 47 | Socios · Membresías · Pagos · Check-in cruzado |
| `usuarios/tests_roles.py` | 37 | Matriz de permisos por rol · Sesión/JWT |
| `accesos/tests_dashboard.py` | 34 | Stats · Bitácora · Feeds de Reportes · Check-in malformado |
| `notificaciones/tests.py` | 32 | Campanita · Historial · Retención 15 días |
| `gyms/tests_clases.py` | 31 | Clases · Equipamiento · Sucursales |
| *(existentes)* | 68 | Auth · Throttling · Multitenant · CRUD base |

Correr la suite:

```bash
python manage.py test --settings=gymaccess.test_settings
```

Los 8 bugs encontrados están marcados con `@unittest.expectedFailure` y un docstring que
explica causa, archivo, línea y arreglo propuesto. La suite queda verde; cuando se
arregle un bug, su marcador salta a *unexpected success* y avisa que ya se puede quitar
el decorador.

**Estado de verificación:** cada módulo se corrió por separado y pasó
(47 ✅ · 37 ✅ · 32 ✅ · 31 ✅ · 30 ✅ en su momento). La última corrida completa
verificada dio **249 tests, 7 expected failures, 1 fallo real**; ese fallo era un test
mal planteado (asumía que SQLite valida la FK dentro de la transacción de test) y se
reescribió como el hallazgo #5. **La suite completa no se ha vuelto a correr después de
ese cambio.** Resultado esperado: 249 tests, 8 expected failures, 0 fallos.

---

## 4. Respuesta a la duda sobre membresías no activas

> *"No estoy seguro si se muestran las membresías que no están activas en el apartado de
> socios."*

**El socio siempre aparece en la lista**, sin importar el estado de su membresía. Se
verificó con los seis casos: activa, vencida, suspendida, pendiente de pago, sin
membresía y dado de baja.

**Lo que no se muestra es el plan.** El campo `membresia_activa` viene en `null` para
vencida, suspendida y pendiente de pago, así que:

- La columna **PLAN** muestra "Sin plan".
- La columna **PRÓX. PAGO** muestra "—".
- Un socio moroso se ve idéntico a un socio nuevo que nunca ha comprado plan.

**El filtro Activos/Inactivos no ayuda.** `Socios.jsx:132` filtra por `socio.activo` (la
baja administrativa del socio), no por el estado de su membresía. Desde esa pantalla no
hay forma de aislar a los morosos.

---

## 5. Bugs encontrados

Los tres primeros se confirmaron ejecutando el código real, no solo por lectura.

| # | Severidad | Ubicación | Descripción |
|---|---|---|---|
| 1 | **Alta** | `socios/serializers.py:25` | `get_membresia_activa` filtra solo por `estado='activa'` y nunca compara `fecha_fin` contra hoy. Nada en el backend cambia el estado a `vencida` cuando pasa la fecha. |
| 2 | **Alta** | consecuencia de #1 | Socios y el kiosco dan veredictos distintos. **Comprobado:** la lista devolvió `fecha_fin: 2026-08-05` (ayer) marcada como activa; el check-in devolvió `403 denegado`. |
| 3 | Media | consecuencia de #1 | Una membresía que arranca la próxima semana ya se publica como activa. El check-in la rechaza por `fecha_inicio__lte=hoy`. |
| 4 | **Alta** | `socios/views.py:46-51` | `MembresiaViewSet` filtra el queryset de lectura por gym pero no valida nada en la escritura: no hay `perform_create` ni `validate()`. **Comprobado:** un POST con socio, plan y sucursal de otro gym devolvió `201` y creó la membresía. Comparar con `PagoViewSet.perform_create` (`socios/views.py:62-64`), que sí valida. |
| 5 | Media | `accesos/views.py:67, 110-116` | Check-in acepta el `sucursal_id` que manda el cliente sin comprobar que pertenezca al gym del usuario. El acceso queda registrado contra la sucursal de otro negocio y ensucia su bitácora y sus reportes. El QR sí está protegido. |
| 6 | Baja | `accesos/views.py:67, 90-116` | Check-in sin `sucursal_id` muere con `IntegrityError: NOT NULL constraint failed: accesos.sucursal_id` (500 en vez de 400). Ocurre si el gym no tiene sucursales dadas de alta y el selector de `CheckIn.jsx` queda vacío. |
| 7 | Baja | `notificaciones/views.py:16` | El viewset acepta POST pero el serializer marca `gym`/`tipo`/`mensaje` como read-only. El POST pasa la validación vacío y muere en el INSERT (500 en vez de 400). No hay fuga: la notificación nunca se crea. Arreglo: quitar `'post'` de `http_method_names`. |
| 8 | Baja | `socios/views.py:33-37` | La rama `else: serializer.save()` para usuarios sin gym choca con `Socio.gym` NOT NULL. Un superadmin sin gym que da de alta un socio recibe un 500. Solo afecta a superadmins; admin y recepción siempre tienen gym. |

### El efecto combinado que importa

El bug #1 se cruza con `Pagos.jsx:60`:

```js
const atrasados = membresias.filter(m => m.fecha_fin < hoy && m.estado !== 'activa')
```

Una membresía que expiró pero quedó con `estado='activa'` en la base:

- **no** aparece como morosa en Socios (bug #1),
- **no** aparece en Pagos → Atrasados (por el `estado !== 'activa'` de arriba),
- pero **sí** se le niega la entrada en la puerta.

Es decir: el socio deja de pagar, desaparece de todos los tableros de cobranza y se
entera del problema cuando no puede entrar. Nadie lo persigue.

---

## 6. Recomendaciones

### Prioridad 1 — afectan dinero

1. **Corregir `get_membresia_activa`** para que aplique el mismo filtro de fechas que el
   check-in:

   ```python
   def get_membresia_activa(self, obj):
       hoy = timezone.localdate()
       m = obj.membresias.filter(
           estado='activa', fecha_inicio__lte=hoy,
       ).filter(
           Q(fecha_fin__gte=hoy) | Q(fecha_fin__isnull=True)
       ).first()
   ```

   Mejor aún: extraer ese predicado a un manager o a un método del modelo `Membresia`
   para que serializer y check-in compartan una sola definición de "vigente".

2. **Agregar validación de escritura a `MembresiaViewSet`**, siguiendo el patrón de
   `PagoViewSet.perform_create`: confirmar que `socio`, `plan` y `sucursal` pertenezcan
   al gym del usuario.

### Prioridad 2 — higiene operativa

3. **Job que marque vencidas.** Hoy nada mueve `estado` de `activa` a `vencida` cuando
   pasa `fecha_fin`. Un comando de management corrido por cron (como ya existe
   `limpiar_notificaciones`) resolvería la causa de fondo de los bugs #1 a #3.

4. **Validar `sucursal_id` en el check-in** contra las sucursales del gym: cierra #5 y #6
   de una sola vez.

5. **Filtro por estado de membresía en la pantalla de Socios.** Los datos ya viajan en la
   respuesta; falta el control en la UI para poder listar morosos.

### Prioridad 3 — robustez

6. Quitar `'post'` de `http_method_names` en `NotificacionViewSet` (#7).
7. Validar la ausencia de gym en `SocioViewSet.perform_create` (#8).

---

## 7. Observaciones que no son bugs

Comportamientos actuales que conviene tener presentes; no se tocaron porque pueden ser
decisiones de negocio deliberadas.

- **Dar de baja a un socio no le cierra la puerta.** El check-in solo mira la membresía,
  nunca `Socio.activo`. Un socio marcado como inactivo con membresía vigente entra sin
  problema. (Cubierto por
  `test_socio_dado_de_baja_con_membresia_activa_entra`.)
- **Clases no tiene restricción de rol.** `ClaseViewSet` usa solo `IsAuthenticated`, así
  que recepción y coach pueden crear, editar y borrar clases. Equipamiento y Gastos sí
  están reservados a admin.
- **El rol `coach` no está contemplado en `ROLES_ADMIN`**, así que hereda exactamente los
  mismos permisos que recepción.
- **No hay validación de sobrecupo en clases:** nada impide que `inscritos` supere a
  `cupo_max`.
- **Las notificaciones se purgan a los 15 días.** El viewset purga solo las del gym del
  usuario al listar; el comando `limpiar_notificaciones` barre todos los gyms.
