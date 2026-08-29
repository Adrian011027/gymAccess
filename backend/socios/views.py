from datetime import timedelta
from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from accesos.models import MetodoAcceso, generar_token_qr
from gyms.models import Sucursal
from tienda.models import Venta
from usuarios.models import Usuario
from usuarios.permissions import ROLES_ADMIN, AdminOSoloLectura, EsAdminGym
from usuarios.scoping import SucursalScopedMixin
from .models import AjusteMembresia, Plan, Socio, Membresia, Pago, Gasto
from .serializers import (
    AjusteMembresiaSerializer, AjusteVencimientoInputSerializer,
    PlanSerializer, SocioSerializer, MembresiaSerializer,
    PagoSerializer, GastoSerializer
)


class PlanViewSet(viewsets.ModelViewSet):
    serializer_class = PlanSerializer
    permission_classes = [permissions.IsAuthenticated, AdminOSoloLectura]

    def get_queryset(self):
        return Plan.objects.filter(
            gym_id=self.request.user.gym_id, activo=True
        ).prefetch_related('precios_sucursal')

    def perform_create(self, serializer):
        """El gym lo pone el servidor.

        `PlanSerializer` es `fields = '__all__'` y no había `perform_create`: un POST
        con `gym` ajeno se guardaba con 201 en el catálogo del negocio de al lado y
        desaparecía de la vista de quien lo creó, así que el atacado lo veía aparecer
        sin explicación.
        """
        serializer.save(gym_id=self.request.user.gym_id)

    def perform_update(self, serializer):
        # Un plan no se muda de gimnasio: el PATCH es la misma escritura cruzada.
        serializer.save(gym_id=serializer.instance.gym_id)


class SocioViewSet(SucursalScopedMixin, viewsets.ModelViewSet):
    """El listado se acota a la sucursal del usuario; la búsqueda no.

    Antes el listado no se acotaba en absoluto, para que recepción pudiera atender al
    socio de otro local que viene de visita. El efecto es que recepción abría /socios y
    veía el padrón entero del negocio, que no es lo que debe tener delante.

    Se resuelve separando los dos casos: sin `?buscar=`, cada quien ve su sucursal.
    Con `?buscar=`, se recorre el gym completo, porque encontrar al visitante en el
    mostrador es justamente el caso que el alcance estricto rompería. El detalle de un
    socio (`retrieve`/`update`) tampoco se acota: si la búsqueda lo encontró, abrirlo
    tiene que funcionar. Quién puede *entrar* a qué sucursal lo sigue decidiendo el
    check-in; esto es solo qué se ve en pantalla.
    """

    serializer_class = SocioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        # Dar de baja a un socio es del dueño, no del mostrador. Recepción sigue
        # pudiendo dar de alta y editar; eliminar no. Se hace aquí y no solo
        # ocultando el botón: un botón escondido no es un permiso, el endpoint
        # seguiría contestando a un DELETE hecho a mano.
        if self.action == 'destroy':
            return [permissions.IsAuthenticated(), EsAdminGym()]
        return super().get_permissions()

    def get_queryset(self):
        qs = Socio.objects.filter(
            gym_id=self.request.user.gym_id
        ).select_related('sucursal').prefetch_related('metodos_acceso')
        # `restaurar` tiene que poder alcanzar justamente al que está eliminado, y el
        # resto de acciones de detalle operan sobre socios vivos: filtrarlas aquí
        # devolvería 404 al intentar deshacer una baja.
        if self.action == 'restaurar':
            return qs
        # Sin una forma de listarlos, `restaurar` seria inalcanzable: nadie sabria que
        # id pedir. Solo para admins, y nunca por defecto.
        ve_bajas = (
            self.action == 'list'
            and self.request.query_params.get('incluir_eliminados') == '1'
            and self.request.user.rol in ROLES_ADMIN
        )
        if not ve_bajas:
            qs = qs.vivos()
        if self.action != 'list':
            return qs

        buscar = self.request.query_params.get('buscar', '').strip()
        if not buscar:
            return self.scope_sucursal(qs)

        # Cada palabra debe aparecer en algún campo, no la cadena entera en uno solo:
        # si no, "Juan Pérez" no encuentra a nadie, porque ningún `nombre` contiene el
        # apellido. `numero_socio` es entero y `icontains` obligaría a castear en SQL,
        # así que se compara exacto y solo cuando lo tecleado son dígitos.
        criterio = models.Q()
        for palabra in buscar.split():
            parcial = (
                models.Q(nombre__icontains=palabra)
                | models.Q(apellido__icontains=palabra)
                | models.Q(email__icontains=palabra)
            )
            if palabra.isdigit():
                parcial |= models.Q(numero_socio=int(palabra))
            criterio &= parcial
        return qs.filter(criterio)

    @transaction.atomic
    def perform_create(self, serializer):
        # Atómico porque el consentimiento se valida después de tener el socio (hace
        # falta su gym y su edad para saber qué exigir). Sin esto, un alta sin la
        # casilla marcada devolvía 400 pero dejaba el socio ya creado.
        acepta_aviso = serializer.validated_data.pop('acepta_aviso', False)
        gym_id = self.request.user.gym_id
        if not gym_id:
            # Un superadmin sin gym debe decir explícitamente en qué gym da de alta;
            # Socio.gym es NOT NULL, así que guardar sin gym revienta en el INSERT.
            gym = serializer.validated_data.get('gym')
            if not gym:
                raise ValidationError(
                    {'gym': 'El usuario no tiene gym asignado: indica el gym del socio.'}
                )
            gym_id = gym.id
        # Un socio dado de alta en una caja se registra en esa sucursal salvo que
        # indiquen otra. El dueño (sin sucursal) sí puede elegirla; recepción no puede
        # darlo de alta en el local de al lado ahora que el alta expone el campo.
        self.validar_escritura(serializer.validated_data.get('sucursal'))
        extra = {}
        if serializer.validated_data.get('sucursal') is None and self.sucursal_id:
            extra['sucursal_id'] = self.sucursal_id
        # `select_for_update` serializa a los que compiten por el mismo consecutivo
        # (en SQLite es inerte, pero deja el código correcto para cuando el gym pase
        # a Postgres). El registro nunca revienta por choque: se sirve un número por
        # vez dentro de esta transacción.
        ultimo = (
            Socio.objects.select_for_update()
            .filter(gym_id=gym_id)
            .aggregate(m=models.Max('numero_socio'))['m']
        )
        extra['numero_socio'] = (ultimo or 999) + 1
        socio = serializer.save(gym_id=gym_id, **extra)
        # Cada socio nuevo recibe su código de acceso automáticamente
        MetodoAcceso.objects.create(
            socio=socio,
            tipo='qr',
            token=generar_token_qr(socio.id),
        )
        self.registrar_consentimiento(socio, acepta_aviso)

    def registrar_consentimiento(self, socio, acepta_aviso):
        """Guarda la evidencia de que el socio aceptó el aviso de privacidad vigente.

        Solo se exige si el gym ya publicó uno: no se puede consentir un documento
        que no existe, y obligarlo antes dejaría el alta bloqueada sin salida.
        """
        from legal.models import ConsentimientoSocio, DocumentoLegal
        from legal.views import ip_de

        aviso = DocumentoLegal.vigente(DocumentoLegal.AVISO_PRIVACIDAD, socio.gym_id)
        if not aviso:
            return
        if not acepta_aviso:
            raise ValidationError({
                'acepta_aviso': 'Falta la aceptación del aviso de privacidad por parte '
                                'del socio o de su tutor.',
            })
        ConsentimientoSocio.objects.create(
            socio=socio,
            documento=aviso,
            otorgado_por='tutor' if socio.es_menor else 'socio',
            medio='mostrador',
            tutor_nombre=socio.tutor_nombre,
            tutor_parentesco=socio.tutor_parentesco,
            ip=ip_de(self.request),
            capturado_por=self.request.user,
        )

    def perform_update(self, serializer):
        serializer.validated_data.pop('acepta_aviso', None)
        if 'sucursal' in serializer.validated_data:
            self.validar_escritura(serializer.validated_data.get('sucursal'))
        serializer.save()

    def perform_destroy(self, instance):
        """Baja lógica del socio: no se borra la fila.

        Un DELETE real arrastraba por cascada `Membresia` -> `Pago` (que la obligación
        fiscal manda conservar 5 años), `ConsentimientoSocio` (la evidencia de que
        aceptó el aviso, que es lo único que convierte el aviso en defensa ante el
        INAI) y `Acceso` (la bitácora de quién entró al local). Se marca la baja y se
        desactivan sus métodos de acceso, que es el efecto que se busca: deja de
        aparecer y deja de abrir la puerta.

        No se anonimiza: eso es el derecho de cancelación (`cancelar-datos`), es
        irreversible y exige contraseña de admin. Esto es reversible con `restaurar`.
        """
        # Inalcanzable por la API (`get_queryset` ya filtro los eliminados, asi que un
        # segundo DELETE da 404 antes de llegar aqui). Se deja como red por si alguien
        # llama a `perform_destroy` desde otro sitio: borrar dos veces pisaria
        # `eliminado_por` y la fecha original de la baja.
        if instance.eliminado_en:
            raise ValidationError({'socio': 'Este socio ya estaba dado de baja.'})
        with transaction.atomic():
            instance.eliminado_en = timezone.now()
            instance.eliminado_por = self.request.user
            # `activo=False` además de la marca de baja: los conteos del panel y del
            # SaaS filtran por `activo`, y sin esto un socio eliminado seguiría
            # sumando como socio activo del gym.
            instance.activo = False
            instance.save(update_fields=['eliminado_en', 'eliminado_por', 'activo'])
            # El QR deja de abrir: el check-in busca `MetodoAcceso.activo=True`.
            instance.metodos_acceso.update(activo=False)

    @action(detail=True, methods=['post'],
            permission_classes=[permissions.IsAuthenticated, EsAdminGym])
    def restaurar(self, request, pk=None):
        """Deshace la baja lógica. Sin esto, `destroy` sería irreversible en la práctica."""
        socio = self.get_object()
        if not socio.eliminado_en:
            raise ValidationError({'socio': 'Este socio no está dado de baja.'})
        with transaction.atomic():
            socio.eliminado_en = None
            socio.eliminado_por = None
            socio.activo = True
            socio.save(update_fields=['eliminado_en', 'eliminado_por', 'activo'])
            # Se reactiva solo el QR: si tenía otros métodos desactivados a mano antes
            # de la baja, reactivarlos todos revertiría decisiones que nadie pidió
            # deshacer.
            socio.metodos_acceso.filter(tipo='qr').update(activo=True)
        return Response(SocioSerializer(socio).data, status=status.HTTP_200_OK)

    # --- Derechos ARCO (LFPDPPP) -------------------------------------------------
    # El socio puede pedir ver sus datos y pedir que se borren. La ley da 20 días
    # hábiles para responder; atenderlo a mano sobre la base de datos es lento y
    # propenso a dejarse cosas fuera, así que se resuelve desde el sistema.

    @action(detail=True, methods=['get'], url_path='datos-personales',
            permission_classes=[permissions.IsAuthenticated, EsAdminGym])
    def datos_personales(self, request, pk=None):
        """Acceso: todo lo que el gym guarda de este socio, en un solo documento."""
        socio = self.get_object()
        return Response({
            'generado_en': timezone.now(),
            'identificacion': {
                'nombre': socio.nombre,
                'apellido': socio.apellido,
                'email': socio.email,
                'telefono': socio.telefono,
                'fecha_nacimiento': socio.fecha_nacimiento,
                'edad': socio.edad(),
                'sexo': socio.get_sexo_display() if socio.sexo else None,
                'foto': socio.foto.url if socio.foto else None,
                'sucursal': socio.sucursal.nombre if socio.sucursal else None,
                'alta': socio.creado_en,
                'activo': socio.activo,
            },
            'tutor': {
                'nombre': socio.tutor_nombre,
                'parentesco': socio.tutor_parentesco,
                'telefono': socio.tutor_telefono,
            } if socio.tutor_nombre else None,
            'metodos_acceso': [
                {'tipo': m.get_tipo_display(), 'activo': m.activo, 'alta': m.creado_en}
                for m in socio.metodos_acceso.all()
            ],
            'membresias': [
                {
                    'plan': m.plan.nombre, 'sucursal': m.sucursal.nombre,
                    'inicio': m.fecha_inicio, 'fin': m.fecha_fin, 'estado': m.estado,
                }
                for m in socio.membresias.select_related('plan', 'sucursal')
            ],
            'pagos': [
                {'monto': p.monto, 'metodo': p.get_metodo_display(), 'fecha': p.fecha}
                for m in socio.membresias.all() for p in m.pagos.all()
            ],
            'accesos': [
                {'sucursal': a.sucursal.nombre, 'resultado': a.resultado, 'fecha': a.timestamp}
                for a in socio.accesos.select_related('sucursal').order_by('-timestamp')[:500]
            ],
            'consentimientos': [
                {
                    'documento': c.documento.titulo, 'version': c.documento.version,
                    'aceptado_en': c.aceptado_en, 'otorgado_por': c.get_otorgado_por_display(),
                }
                for c in socio.consentimientos.select_related('documento')
            ],
        })

    @action(detail=True, methods=['post'], url_path='cancelar-datos',
            permission_classes=[permissions.IsAuthenticated, EsAdminGym])
    def cancelar_datos(self, request, pk=None):
        """Cancelación: borra los datos personales y conserva el histórico anonimizado.

        No se elimina la fila: de ella cuelgan pagos que la obligación fiscal manda
        conservar (CFF art. 30, cinco años). Borrar el socio arrastraría los pagos por
        cascada y descuadraría la contabilidad, así que se vacía lo que identifica a la
        persona y se deja el registro contable en pie.

        Exige la contraseña de un admin aunque quien la pida ya lo sea: es
        irreversible y la sesión abierta en el mostrador es el riesgo real.
        """
        from accesos.views import autorizador_del_gym

        socio = self.get_object()
        if socio.anonimizado_en:
            raise ValidationError({'socio': 'Los datos de este socio ya fueron cancelados.'})

        autorizador = autorizador_del_gym(request.user.gym_id, request.data.get('password'))
        if autorizador is None:
            raise PermissionDenied('Contraseña de autorización incorrecta.')

        with transaction.atomic():
            socio.nombre = 'Socio'
            socio.apellido = f'cancelado #{socio.id}'
            socio.email = ''
            socio.telefono = ''
            socio.fecha_nacimiento = None
            socio.sexo = ''
            socio.tutor_nombre = ''
            socio.tutor_parentesco = ''
            socio.tutor_telefono = ''
            if socio.foto:
                socio.foto.delete(save=False)
            socio.activo = False
            socio.anonimizado_en = timezone.now()
            socio.save()
            # El QR deja de abrir la puerta, pero la bitácora de accesos se conserva:
            # es registro de quién entró al local, no un dato de contacto.
            socio.metodos_acceso.update(activo=False)

        return Response({
            'socio': SocioSerializer(socio).data,
            'anonimizado_en': socio.anonimizado_en,
            'autorizado_por': autorizador.nombre,
        }, status=status.HTTP_200_OK)


class MembresiaViewSet(SucursalScopedMixin, viewsets.ModelViewSet):
    serializer_class = MembresiaSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # `socio__eliminado_en__isnull=True`: la membresia de un socio dado de baja
        # seguia apareciendo en "Por cobrar" de /pagos, de modo que recepcion veia una
        # deuda de alguien que ya no existe en el listado y no podia hacer nada con ella.
        return self.scope_sucursal(
            Membresia.objects.filter(
                socio__gym_id=self.request.user.gym_id,
                socio__eliminado_en__isnull=True,
            )
        ).select_related('socio', 'plan').prefetch_related(
            models.Prefetch(
                'plan__precios_sucursal',
                to_attr='precios_sucursal_prefetched',
            )
        )

    def _validar_pertenencia(self, serializer):
        """El queryset de lectura ya filtra por gym, pero la escritura no validaba nada:
        un POST con socio/plan/sucursal de otro negocio se guardaba con 201 y quedaba
        invisible para quien lo creó. Mismo patrón que PagoViewSet.perform_create.
        """
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
        # Y además, recepción solo firma membresías en su propia sucursal.
        self.validar_escritura(serializer.validated_data.get('sucursal'))

    def perform_create(self, serializer):
        self._validar_pertenencia(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self._validar_pertenencia(serializer)
        serializer.save()

    def get_throttles(self):
        # El ajuste verifica contraseñas: sin un límite propio se vuelve un banco de
        # pruebas de fuerza bruta contra las cuentas admin del gym.
        if self.action == 'ajustar_vencimiento':
            return [ScopedRateThrottle()]
        return super().get_throttles()

    throttle_scope = 'autorizacion'

    def _autorizador(self, password):
        """Devuelve el admin del gym cuya contraseña coincide, o None.

        Se prueba contra todos los admins del gym porque la UI solo pide la contraseña,
        sin decir de quién es. Se recorren todos aunque uno coincida antes: cortar en el
        primer acierto haría que el tiempo de respuesta delate qué cuenta acertó.
        """
        if not password:
            return None
        encontrado = None
        for admin in Usuario.objects.filter(
            gym_id=self.request.user.gym_id, rol__in=ROLES_ADMIN, is_active=True,
        ).order_by('id'):
            if admin.check_password(password) and encontrado is None:
                encontrado = admin
        return encontrado

    @action(detail=True, methods=['post'], url_path='ajustar-vencimiento')
    def ajustar_vencimiento(self, request, pk=None):
        """Mueve la fecha de próximo pago. Exige la contraseña de un admin del gym
        incluso si quien la pide ya es admin: la sesión abierta y desatendida en el
        mostrador es justamente el riesgo que esto cubre."""
        membresia = self.get_object()   # get_queryset ya acota al gym del usuario
        entrada = AjusteVencimientoInputSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data

        autorizador = self._autorizador(datos['password'])
        if autorizador is None:
            raise PermissionDenied('Contraseña de autorización incorrecta.')

        nueva = datos['fecha_fin']
        if nueva < membresia.fecha_inicio:
            raise ValidationError(
                {'fecha_fin': 'La fecha de vencimiento no puede ser anterior al inicio '
                              f'de la membresía ({membresia.fecha_inicio}).'}
            )

        anterior_fecha = membresia.fecha_fin
        anterior_estado = membresia.estado

        # El estado sigue a la fecha, o el cambio no tiene efecto: `vigentes()` exige
        # estado='activa', así que extender una vencida sin reactivarla no abre la puerta.
        # 'suspendida' y 'pendiente_pago' son bloqueos deliberados y no se tocan aquí.
        nuevo_estado = anterior_estado
        hoy = timezone.localdate()
        if anterior_estado in ('activa', 'vencida'):
            nuevo_estado = 'activa' if nueva >= hoy else 'vencida'

        with transaction.atomic():
            membresia.fecha_fin = nueva
            membresia.estado = nuevo_estado
            membresia.save(update_fields=['fecha_fin', 'estado'])
            ajuste = AjusteMembresia.objects.create(
                membresia=membresia,
                fecha_anterior=anterior_fecha,
                fecha_nueva=nueva,
                estado_anterior=anterior_estado,
                estado_nuevo=nuevo_estado,
                motivo=datos.get('motivo', ''),
                solicitado_por=request.user,
                autorizado_por=autorizador,
            )

        return Response({
            'membresia': MembresiaSerializer(membresia).data,
            'ajuste': AjusteMembresiaSerializer(ajuste).data,
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def ajustes(self, request, pk=None):
        """Bitácora de la membresía. Una auditoría que nadie puede leer no es auditoría."""
        membresia = self.get_object()
        return Response(AjusteMembresiaSerializer(
            membresia.ajustes.select_related('solicitado_por', 'autorizado_por'), many=True,
        ).data)


class PagoViewSet(SucursalScopedMixin, viewsets.ModelViewSet):
    serializer_class = PagoSerializer
    permission_classes = [permissions.IsAuthenticated]
    sucursal_lookup = 'membresia__sucursal'

    def get_queryset(self):
        return self.scope_sucursal(
            Pago.objects.filter(membresia__socio__gym_id=self.request.user.gym_id)
        )

    def perform_create(self, serializer):
        membresia = serializer.validated_data.get('membresia')
        if not membresia or membresia.socio.gym_id != self.request.user.gym_id:
            raise ValidationError({'membresia': 'Membresía no encontrada'})
        if self.sucursal_id is not None and membresia.sucursal_id != self.sucursal_id:
            raise ValidationError({'membresia': 'Membresía no encontrada'})

        pago = serializer.save(registrado_por=self.request.user)

        # El pago reactiva la membresía y recorre el período según el plan
        plan = membresia.plan
        hoy = timezone.localdate()
        membresia.fecha_inicio = hoy
        membresia.fecha_fin = hoy + timedelta(days=plan.duracion_dias) if plan.duracion_dias else None
        if plan.num_clases:
            membresia.clases_restantes = plan.num_clases
        membresia.estado = 'activa'
        membresia.save()
        return pago

    @action(detail=False, methods=['get'])
    def corte(self, request):
        """Corte de caja de un día: qué entró, por dónde entró y qué debe haber en el cajón.

        Junta las tres fuentes de dinero del día en una sola pantalla porque el cajón
        es uno solo: cobros de membresía, ventas de tienda y gastos pagados desde la
        caja. Hasta ahora recepción tenía los cobros en Pagos y las ventas en el POS,
        sin ningún lugar donde se sumaran, así que al cerrar no había forma de saber
        cuánto se hizo en el día ni cuánto efectivo debía haber.

        `?fecha=AAAA-MM-DD` (default hoy) y `?sucursal=<id>` (solo el dueño; a
        recepción se le ignora y siempre ve su propia caja).
        """
        dia = self._fecha_de_corte(request)
        objetivo = self.sucursal_id or self.sucursal_solicitada()
        gym_id = request.user.gym_id

        pagos = self.get_queryset().filter(fecha__date=dia).select_related(
            'membresia__socio', 'membresia__plan', 'registrado_por',
        )

        ventas = Venta.objects.filter(gym_id=gym_id, fecha__date=dia)
        gastos = Gasto.objects.filter(gym_id=gym_id, fecha=dia)
        if objetivo is not None:
            ventas = ventas.filter(sucursal_id=objetivo)
            # Solo los gastos de ESTA sucursal. Los que se guardaron sin sucursal son
            # del negocio entero (renta del corporativo, contador) y no salieron de
            # este cajón: sumarlos aquí los contaría una vez por cada local.
            gastos = gastos.filter(sucursal_id=objetivo)
        ventas = ventas.select_related('vendido_por').prefetch_related('items__producto')
        gastos = gastos.select_related('registrado_por')

        movimientos = []
        for p in pagos:
            movimientos.append({
                'tipo': 'membresia',
                'fecha': p.fecha,
                'concepto': f'{p.membresia.socio} · {p.membresia.plan.nombre}',
                'metodo': p.metodo,
                'monto': p.monto,
                'signo': 1,
                'registrado_por': getattr(p.registrado_por, 'nombre', None),
                'referencia': p.referencia,
            })
        for v in ventas:
            detalle = ', '.join(f'{i.cantidad}× {i.producto.nombre}' for i in v.items.all())
            movimientos.append({
                'tipo': 'tienda',
                'fecha': v.fecha,
                'concepto': detalle or f'Venta #{v.id}',
                'metodo': v.metodo,
                'monto': v.total,
                'signo': 1,
                'registrado_por': getattr(v.vendido_por, 'nombre', None),
                'referencia': f'#{v.id}',
            })
        for g in gastos:
            movimientos.append({
                'tipo': 'gasto',
                # Gasto solo guarda el día, no la hora: va sin hora y al final del día.
                'fecha': None,
                'concepto': f'{g.get_categoria_display()} · {g.descripcion}',
                'metodo': g.metodo,
                'monto': g.monto,
                'signo': -1,
                'registrado_por': getattr(g.registrado_por, 'nombre', None),
                'referencia': '',
            })
        movimientos.sort(key=lambda m: (m['fecha'] is None, m['fecha'] or timezone.now()))

        cobros = self._desglosar(m for m in movimientos if m['signo'] > 0)
        membresias = self._desglosar(m for m in movimientos if m['tipo'] == 'membresia')
        tienda = self._desglosar(m for m in movimientos if m['tipo'] == 'tienda')
        egresos = self._desglosar(m for m in movimientos if m['signo'] < 0)

        sucursal = Sucursal.objects.filter(id=objetivo).first() if objetivo else None

        return Response({
            'fecha': dia.isoformat(),
            'sucursal': {'id': sucursal.id, 'nombre': sucursal.nombre} if sucursal else None,
            'membresias': membresias,
            'tienda': tienda,
            'gastos': egresos,
            'ingresos': cobros,
            'neto': cobros['total'] - egresos['total'],
            # Lo que debe haber en el cajón al cerrar, sin contar el fondo de apertura:
            # solo el efectivo se toca a mano; tarjeta y transferencia no pasan por ahí.
            'efectivo_esperado': cobros['por_metodo']['efectivo'] - egresos['por_metodo']['efectivo'],
            'movimientos': movimientos,
        })

    def _fecha_de_corte(self, request):
        valor = request.query_params.get('fecha')
        if not valor:
            return timezone.localdate()
        fecha = parse_date(valor)
        if fecha is None:
            raise ValidationError({'fecha': 'Usa el formato AAAA-MM-DD.'})
        return fecha

    @staticmethod
    def _desglosar(movimientos):
        """Total y desglose por método. En Python y no con aggregate() porque son tres
        modelos distintos y un día de caja son decenas de renglones, no millones."""
        por_metodo = {m: Decimal('0') for m, _ in Pago.METODO_CHOICES}
        total = Decimal('0')
        num = 0
        for mov in movimientos:
            monto = Decimal(mov['monto'])
            total += monto
            num += 1
            if mov['metodo'] in por_metodo:
                por_metodo[mov['metodo']] += monto
        return {'total': total, 'num': num, 'por_metodo': por_metodo}


class GastoViewSet(SucursalScopedMixin, viewsets.ModelViewSet):
    serializer_class = GastoSerializer
    permission_classes = [permissions.IsAuthenticated, EsAdminGym]

    def get_queryset(self):
        qs = Gasto.objects.filter(gym_id=self.request.user.gym_id)
        objetivo = self.sucursal_id or self.sucursal_solicitada()
        if objetivo is None:
            return qs
        # Los gastos sin sucursal son del negocio entero (contador, publicidad) y
        # cuentan para cualquier local.
        return qs.filter(models.Q(sucursal_id=objetivo) | models.Q(sucursal__isnull=True))

    def perform_create(self, serializer):
        self.validar_escritura(serializer.validated_data.get('sucursal'))
        # Sin sucursal el gasto es del negocio y no entra al corte de ninguna caja;
        # quien está parado en una sucursal lo carga a la suya por defecto.
        sucursal = self.sucursal_por_defecto(serializer.validated_data.get('sucursal'))
        serializer.save(
            gym_id=self.request.user.gym_id,
            sucursal=sucursal,
            registrado_por=self.request.user,
        )

    def perform_update(self, serializer):
        # El alta validaba la sucursal y fijaba el gym; la edición no hacía ninguna
        # de las dos cosas, que es la mitad del agujero por la que se cuela un gasto
        # movido al negocio de al lado.
        if 'sucursal' in serializer.validated_data:
            self.validar_escritura(serializer.validated_data.get('sucursal'))
        serializer.save(gym_id=serializer.instance.gym_id)
