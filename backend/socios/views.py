from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from accesos.models import MetodoAcceso, generar_token_qr
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
    """Los socios NO se acotan por sucursal a propósito.

    El socio le paga al negocio, no al local: si recepción de Norte no pudiera ver al
    socio de Centro que viene de visita, no podría ni buscarlo ni atenderlo. Quién
    puede *entrar* a qué sucursal lo decide la política del gym en el check-in;
    aquí solo se expone de qué sucursal es, para que se note en pantalla.
    """

    serializer_class = SocioSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Socio.objects.filter(
            gym_id=self.request.user.gym_id
        ).select_related('sucursal').prefetch_related('metodos_acceso')

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
        return self.scope_sucursal(
            Membresia.objects.filter(socio__gym_id=self.request.user.gym_id)
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
        serializer.save(gym_id=self.request.user.gym_id, registrado_por=self.request.user)

    def perform_update(self, serializer):
        # El alta validaba la sucursal y fijaba el gym; la edición no hacía ninguna
        # de las dos cosas, que es la mitad del agujero por la que se cuela un gasto
        # movido al negocio de al lado.
        if 'sucursal' in serializer.validated_data:
            self.validar_escritura(serializer.validated_data.get('sucursal'))
        serializer.save(gym_id=serializer.instance.gym_id)
