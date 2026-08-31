import io
from datetime import timedelta

import qrcode
from django.db import models, transaction
from django.db.models import Count
from django.db.models.functions import ExtractHour
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import escape
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control
from rest_framework import viewsets, permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from rest_framework.views import APIView
from .enlaces import url_qr
from .models import Acceso, MetodoAcceso, generar_token_qr
from .serializers import AccesoSerializer, MetodoAccesoSerializer, VisitaSerializer
from gyms.models import Sucursal
from socios.models import Membresia, Pago, Socio, siguiente_numero_socio
from notificaciones.models import Notificacion
from usuarios.models import Usuario
from usuarios.permissions import ROLES_ADMIN
from usuarios.scoping import SucursalScopedMixin


def autorizador_del_gym(gym_id, password):
    """El admin del gym cuya contraseña coincide, o None.

    Mismo criterio que el ajuste de vencimiento: se recorren todos los admins aunque
    uno coincida antes, para que el tiempo de respuesta no delate qué cuenta acertó.
    """
    if not password:
        return None
    encontrado = None
    for admin in Usuario.objects.filter(
        gym_id=gym_id, rol__in=ROLES_ADMIN, is_active=True,
    ).order_by('id'):
        if admin.check_password(password) and encontrado is None:
            encontrado = admin
    return encontrado


class MetodoAccesoViewSet(viewsets.ReadOnlyModelViewSet):
    """Solo lectura: los métodos de acceso se crean por su propio camino.

    Era un `ModelViewSet` completo con `fields = '__all__'` y solo `IsAuthenticated`,
    sin validar nada al escribir. Eso daba tres cosas a cualquier empleado:

    - **Revivir el QR de un socio con los datos cancelados**: un
      `PATCH {"activo": true}` deshacía la parte de `cancelar_datos` que le cierra la
      puerta. Verificado: devolvía 200.
    - **Fijar el token que quisiera**, es decir clonar la credencial de otro.
    - **Apuntar un método al socio de otro gimnasio**, porque el filtro por gym
      estaba solo en la lectura.

    El alta legítima pasa por `AsignarQRView` y `SincronizarHuellaView`, que sí
    comprueban que el socio sea de este gym. El frontend no usa este endpoint para
    escribir.
    """

    serializer_class = MetodoAccesoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MetodoAcceso.objects.filter(socio__gym_id=self.request.user.gym_id)


class AsignarQRView(APIView):
    """Devuelve el código QR del socio, creándolo si todavía no tiene.

    Los socios nuevos ya reciben uno al darse de alta (SocioViewSet.perform_create),
    pero los que vienen de una carga anterior pueden no tenerlo, y sin código el
    check-in del kiosco no puede identificarlos.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        socio_id = request.data.get('socio_id')
        if not socio_id:
            return Response(
                {'socio_id': 'Indica el socio.'}, status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            socio = Socio.objects.vivos().get(id=socio_id, gym_id=request.user.gym_id)
        except (Socio.DoesNotExist, ValueError, TypeError):
            return Response(
                {'socio_id': 'Socio no encontrado.'}, status=status.HTTP_404_NOT_FOUND,
            )

        # Un socio dado de baja no recibe credencial nueva. Sin esto, «Asignar QR»
        # deshacía `cancelar_datos` sin que nadie lo notara: esa cancelación apaga
        # los métodos existentes, así que la búsqueda de abajo no encontraba ninguno
        # activo y creaba uno nuevo, activo. Encontrado ocurrido de verdad en la base
        # de pruebas —un socio anonimizado con un QR emitido después de su
        # cancelación—.
        if not socio.activo:
            return Response(
                {'socio_id': 'El socio está dado de baja: reactívalo antes de darle '
                             'un código de acceso.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        metodo = socio.metodos_acceso.filter(tipo='qr', activo=True).first()
        if metodo:
            return Response(MetodoAccesoSerializer(metodo, context={'request': request}).data, status=status.HTTP_200_OK)

        # El token es único a nivel tabla: se reintenta ante una colisión del azar en
        # vez de devolver un 500 por IntegrityError.
        for _ in range(10):
            token = generar_token_qr(socio.id)
            if not MetodoAcceso.objects.filter(token=token).exists():
                metodo = MetodoAcceso.objects.create(socio=socio, tipo='qr', token=token)
                return Response(
                    MetodoAccesoSerializer(metodo, context={'request': request}).data, status=status.HTTP_201_CREATED,
                )
        return Response(
            {'error': 'No se pudo generar un código único, intenta de nuevo.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class SincronizarHuellaView(APIView):
    """Recibe el template ya capturado/matcheado por el agente local (SDK del lector)
    y lo asocia al socio como MetodoAcceso tipo huella."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        socio_id = request.data.get('socio_id')
        template = request.data.get('template')

        if not socio_id or not template:
            return Response({'error': 'socio_id y template son requeridos'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            socio = Socio.objects.vivos().get(id=socio_id, gym_id=request.user.gym_id)
        except Socio.DoesNotExist:
            return Response({'error': 'Socio no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        # Se excluye exactamente la fila que este `update_or_create` va a sobrescribir,
        # no todas las del socio: con `.exclude(socio=socio)` a secas, un template que
        # coincidiera con OTRO método del mismo socio (su propio QR) pasaba el control
        # y reventaba después contra el UNIQUE de la tabla con un 500. Sigue siendo
        # idempotente al resincronizar la misma huella del mismo socio.
        if MetodoAcceso.objects.filter(token=template).exclude(
            socio=socio, tipo='huella',
        ).exists():
            return Response({'error': 'Esta huella ya está registrada a otro socio'}, status=status.HTTP_409_CONFLICT)

        metodo, _ = MetodoAcceso.objects.update_or_create(
            socio=socio, tipo='huella',
            defaults={'token': template, 'activo': True},
        )
        return Response(MetodoAccesoSerializer(metodo, context={'request': request}).data, status=status.HTTP_200_OK)


class AccesoViewSet(SucursalScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = AccesoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.scope_sucursal(
            Acceso.objects.filter(socio__gym_id=self.request.user.gym_id)
        ).select_related('socio', 'sucursal').order_by('-timestamp')


class BuscarSocioView(APIView):
    """Busca socios por nombre para el check-in.

    Existe porque el socio que olvidó su código bloqueaba la puerta: recepción no
    tenía forma de identificarlo desde el kiosco y acababa entrando por la lista de
    socios, donde no se puede registrar el acceso.

    Devuelve el token del QR para que el alta del acceso siga pasando por el mismo
    camino que un escaneo: así la política de sucursal, la vigencia y la bitácora se
    aplican igual y no hay una segunda puerta con reglas propias.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'checkin'

    def get(self, request):
        termino = (request.query_params.get('q') or '').strip()
        if len(termino) < 2:
            return Response(
                {'q': 'Escribe al menos 2 letras del nombre.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        qs = Socio.objects.vivos().filter(
            gym_id=request.user.gym_id, activo=True,
        ).select_related('sucursal').prefetch_related('metodos_acceso')

        # Un código corto no es un nombre: "1001" no aparece en ningún apellido, así
        # que la búsqueda por palabras lo devolvía vacío y recepción concluía que el
        # socio no existía.
        if termino.isdigit() and len(termino) <= CheckInView.MAX_DIGITOS_NUMERO:
            qs = qs.filter(numero_socio=int(termino))
        else:
            # Se busca sobre "nombre apellido" completo para que "juan perez" encuentre
            # a Juan Pérez; palabra por palabra, porque nadie escribe el orden exacto.
            for palabra in termino.split():
                qs = qs.filter(
                    models.Q(nombre__icontains=palabra) | models.Q(apellido__icontains=palabra)
                )

        resultados = []
        for socio in qs.order_by('nombre', 'apellido')[:15]:
            metodo = next(
                (m for m in socio.metodos_acceso.all() if m.tipo == 'qr' and m.activo), None,
            )
            membresia = Membresia.objects.vigentes().filter(socio=socio).first()
            resultados.append({
                'id': socio.id,
                'nombre': f'{socio.nombre} {socio.apellido}',
                'numero_socio': socio.numero_socio,
                'token': metodo.token if metodo else None,
                'sucursal': socio.sucursal.nombre if socio.sucursal_id else None,
                'sucursal_id': socio.sucursal_id,
                # Se adelanta el estado para que recepción vea a quién va a rebotar la
                # puerta antes de pulsar, en vez de descubrirlo con el socio enfrente.
                'al_corriente': membresia is not None,
                'plan': membresia.plan.nombre if membresia else None,
                'vence': membresia.fecha_fin if membresia else None,
            })
        return Response(resultados)


class CheckInView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'checkin'

    # Tope del código corto. `numero_socio` es un PositiveIntegerField y un entero de
    # 30 cifras revienta la consulta en Postgres antes de llegar a comparar nada.
    MAX_DIGITOS_NUMERO = 9

    def post(self, request):
        codigo = str(request.data.get('token') or '').strip()
        sucursal_id = request.data.get('sucursal_id')

        identificado = self.identificar(codigo, request.user.gym_id)
        if identificado is None:
            return Response(
                {'error': 'Código no reconocido'}, status=status.HTTP_404_NOT_FOUND,
            )
        socio, metodo_usado = identificado

        # La sucursal viene del cliente: hay que comprobar que exista y que sea de este
        # gym antes de registrar nada. Sin esta validación el acceso se guardaba contra
        # la sucursal de otro negocio, y si faltaba el dato el INSERT reventaba con 500.
        if sucursal_id in (None, ''):
            return Response(
                {'sucursal_id': 'Indica la sucursal donde se registra el acceso.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            sucursal = Sucursal.objects.get(id=sucursal_id, gym_id=request.user.gym_id)
        except (Sucursal.DoesNotExist, ValueError, TypeError):
            return Response(
                {'sucursal_id': 'Sucursal no encontrada.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Recepción registra entradas en su puerta, no en la del otro local.
        propia = getattr(request.user, 'sucursal_id', None)
        if propia is not None and sucursal.id != propia:
            return Response(
                {'sucursal_id': 'Solo puedes registrar accesos en tu sucursal.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Un socio dado de baja no entra, tenga la membresía que tenga.
        #
        # Esta comprobación no existía: el check-in miraba la vigencia de la
        # membresía pero nunca `socio.activo`, así que alguien dado de baja con la
        # mensualidad todavía corriendo abría la puerta. Verificado antes del
        # arreglo: `acceso: permitido`.
        #
        # Va ANTES de la membresía a propósito. Si fuera después, a un socio de baja
        # y además vencido se le diría "membresía vencida", y en el mostrador eso se
        # atiende cobrándole —volviendo a activar a quien se quiso dar de baja—.
        #
        # `motivo_denegado='suspendido'` ya existía en el modelo desde el principio y
        # ningún código lo escribía nunca: la casilla estaba prevista, la regla no.
        if not socio.activo:
            Acceso.objects.create(
                socio=socio,
                sucursal=sucursal,
                metodo_usado=metodo_usado,
                resultado='denegado',
                motivo_denegado='suspendido',
            )
            return Response({
                'acceso': 'denegado',
                'socio': f'{socio.nombre} {socio.apellido}',
                'motivo': 'socio dado de baja: no tiene acceso',
            }, status=status.HTTP_403_FORBIDDEN)

        membresia = Membresia.objects.vigentes().filter(socio=socio).first()

        if not membresia:
            tiene_historial = Membresia.objects.filter(socio=socio).exists()
            motivo = 'membresia_vencida' if tiene_historial else 'sin_membresia'
            Acceso.objects.create(
                socio=socio,
                sucursal=sucursal,
                metodo_usado=metodo_usado,
                resultado='denegado',
                motivo_denegado=motivo,
            )
            if motivo == 'membresia_vencida' and socio.gym_id:
                Notificacion.objects.create(
                    gym_id=socio.gym_id,
                    tipo='pago_vencido',
                    mensaje=f'{socio.nombre} {socio.apellido} intentó ingresar con la membresía vencida',
                    link='/pagos?tab=atrasados',
                )
            return Response({
                'acceso': 'denegado',
                'socio': f'{socio.nombre} {socio.apellido}',
                'motivo': 'membresía no activa',
            }, status=status.HTTP_403_FORBIDDEN)

        # Un código solo abre la puerta una vez por día. Sin este límite, dos personas
        # se reparten el QR de una sola membresía y ambas entran gratis: la segunda
        # entrada del día es exactamente esa señal, la tenga quien la tenga en la mano.
        # Se cuenta a nivel gym, no por sucursal: compartir el código entre dos locales
        # distintos es el mismo abuso.
        ya_entro_hoy = Acceso.objects.filter(
            socio=socio, resultado='permitido', timestamp__date=timezone.localdate(),
        ).exists()
        if ya_entro_hoy:
            Acceso.objects.create(
                socio=socio,
                sucursal=sucursal,
                membresia=membresia,
                metodo_usado=metodo_usado,
                resultado='denegado',
                motivo_denegado='ya_registrado',
            )
            return Response({
                'acceso': 'denegado',
                'socio': f'{socio.nombre} {socio.apellido}',
                'motivo': 'ya se registró su acceso hoy: no puede entrar dos veces el mismo día',
            }, status=status.HTTP_403_FORBIDDEN)

        # El socio está al corriente, pero puede no ser de esta sucursal. Qué hacer en
        # ese caso lo decide el dueño en la configuración del gym: hay negocios donde
        # la membresía es de un local concreto y otros donde da igual.
        # Un socio sin sucursal no se puede contrastar contra nada, así que la política
        # no le aplica y entra a cualquier local aunque esté en 'bloqueado'. No se le
        # cierra la puerta —serían altas viejas legítimas—, pero se marca en la
        # respuesta para que recepción vea el hueco y le asigne sucursal.
        sin_sucursal = socio.sucursal_id is None
        visitante = (
            not sin_sucursal
            and socio.sucursal_id != sucursal.id
        )
        autorizador = None
        if visitante:
            politica = socio.gym.politica_visitantes
            if politica != 'libre':
                # Con 'autorizacion' basta con que quien está en el mostrador pulse
                # "Autorizar": no se pide contraseña. Queda registrado quién lo hizo,
                # así que el control es a posteriori (la bitácora), no en la puerta.
                autoriza_ahora = (
                    politica == 'autorizacion'
                    and str(request.data.get('autorizar', '')).lower() in ('1', 'true', 'sí', 'si')
                )
                if autoriza_ahora:
                    autorizador = request.user
                if politica == 'bloqueado' or not autoriza_ahora:
                    Acceso.objects.create(
                        socio=socio,
                        sucursal=sucursal,
                        membresia=membresia,
                        metodo_usado=metodo_usado,
                        resultado='denegado',
                        motivo_denegado='otra_sucursal',
                    )
                    return Response({
                        'acceso': 'denegado',
                        'socio': f'{socio.nombre} {socio.apellido}',
                        'motivo': 'pertenece a otra sucursal',
                        'sucursal_socio': socio.sucursal.nombre,
                        # Le dice al kiosco si tiene sentido ofrecer el override.
                        'requiere_autorizacion': politica == 'autorizacion',
                    }, status=status.HTTP_403_FORBIDDEN)

        Acceso.objects.create(
            socio=socio,
            sucursal=sucursal,
            membresia=membresia,
            metodo_usado=metodo_usado,
            resultado='permitido',
            autorizado_por=autorizador,
        )
        return Response({
            'acceso': 'permitido',
            'socio': f'{socio.nombre} {socio.apellido}',
            'foto': request.build_absolute_uri(socio.foto.url) if socio.foto else None,
            'plan': membresia.plan.nombre,
            'vence': membresia.fecha_fin,
            'visitante': visitante,
            'sin_sucursal': sin_sucursal,
            'sucursal_socio': socio.sucursal.nombre if socio.sucursal_id else None,
            'autorizado_por': autorizador.nombre if autorizador else None,
        })

    def identificar(self, codigo, gym_id):
        """Resuelve lo que llegó por el lector a (socio, cómo se identificó).

        Acepta dos cosas por el mismo campo: el token del QR y el número de socio
        corto (1001, 1002…). El corto existe para el que llega sin teléfono y sin
        credencial, que hasta ahora dejaba a recepción sin forma de registrarle la
        entrada desde el kiosco.

        Que el consecutivo abra la puerta no contradice el motivo por el que el token
        del QR lleva parte aleatoria: ese lo trae el socio y viaja por WhatsApp, así
        que tiene que ser inadivinable. El corto solo lo puede teclear personal ya
        autenticado en el mostrador, y la respuesta devuelve el nombre, de modo que un
        1002 por un 1001 se ve en la pantalla antes de que nadie cruce la puerta.

        Devuelve None si no corresponde a nadie de este gym.
        """
        if not codigo:
            return None

        metodo = MetodoAcceso.objects.select_related('socio').filter(
            token=codigo, activo=True, socio__gym_id=gym_id,
        ).first()
        if metodo:
            return metodo.socio, metodo.tipo

        if codigo.isdigit() and len(codigo) <= self.MAX_DIGITOS_NUMERO:
            socio = Socio.objects.vivos().filter(
                gym_id=gym_id, numero_socio=int(codigo),
            ).first()
            if socio:
                # 'manual' y no 'qr': la entrada se tecleó. Marcarla como escaneo
                # falsearía la única señal que dice cuántos socios llegan de verdad
                # con su código y cuántos hay que buscar a mano en el mostrador.
                return socio, 'manual'

        return None


class StatsView(SucursalScopedMixin, APIView):
    """Dashboard analytics: afluencia por hora + totales.

    Recepción ve los números de su sucursal; el dueño, los del gym completo, o los de
    una sucursal concreta con ?sucursal=.

    `?rango=hoy` cuenta solo las visitas de hoy. El default `semana` promedia una
    ventana móvil de 7 días (hoy incluido) en vez de la semana de calendario, para
    que el promedio no cambie de tamaño según qué día caiga "hoy" (un promedio de
    "lunes a hoy-martes" con 2 días de datos mentiría más que uno de 7 días fijos).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        gym_id = request.user.gym_id
        hoy = timezone.localdate()
        inicio_mes = hoy.replace(day=1)

        accesos_qs = self.scope_sucursal(Acceso.objects.filter(
            socio__gym_id=gym_id,
            resultado='permitido',
        ))

        rango = request.query_params.get('rango')
        if rango not in ('hoy', 'semana'):
            rango = 'semana'

        if rango == 'hoy':
            desde, dias = hoy, 1
        else:
            desde, dias = hoy - timedelta(days=6), 7

        por_hora_qs = (
            accesos_qs
            .filter(timestamp__date__gte=desde, timestamp__date__lte=hoy)
            .annotate(hora=ExtractHour('timestamp'))
            .values('hora')
            .annotate(total=Count('id'))
            .order_by('hora')
        )
        # `total` es la suma cruda en la ventana (compatible con lo que ya leían los
        # tests); `promedio` es lo que pinta la gráfica — en 'hoy' coincide con total
        # porque dias=1, así que el frontend puede usar un solo campo sin ramificar.
        horarios_concurridos = [
            {'hora': h['hora'], 'total': h['total'], 'promedio': round(h['total'] / dias, 1)}
            for h in por_hora_qs
        ]
        hora_pico = (
            max(horarios_concurridos, key=lambda h: h['promedio'])['hora']
            if horarios_concurridos else None
        )

        accesos_hoy = accesos_qs.filter(timestamp__date=hoy).count()
        accesos_mes = accesos_qs.filter(timestamp__date__gte=inicio_mes).count()

        return Response({
            'horarios_concurridos': horarios_concurridos,
            'rango': rango,
            'dias_considerados': dias,
            'hora_pico': hora_pico,
            'accesos_hoy': accesos_hoy,
            'accesos_mes': accesos_mes,
        })


class QRImagenView(APIView):
    """El QR de un socio como PNG, en una URL que se puede abrir sin sesión.

    Existe porque un enlace de WhatsApp (`wa.me`, `web.whatsapp.com/send`) solo acepta
    teléfono y texto: no hay forma de adjuntar una imagen desde la URL. Con esto el
    mensaje lleva un enlace que WhatsApp previsualiza, y el socio abre o guarda su
    código de una pulsación, sin que recepción tenga que pegar nada.

    **Es pública a propósito**, y eso merece explicación: el socio no tiene cuenta en
    el sistema, así que no hay sesión con la que autenticar la petición. Lo que la hace
    aceptable es que la URL lleva el token, y el token es el secreto: quien la tiene ya
    tiene la credencial, así que el enlace no expone nada que la imagen no expusiera.
    Los 96 bits de `secrets.token_urlsafe(12)` son los que impiden llegar aquí
    probando; el throttle está para que tampoco se pueda intentar en volumen.

    No se guarda ningún PNG en disco: se dibuja al vuelo. Un directorio de imágenes por
    socio se queda desincronizado en cuanto se reasigna un QR —el archivo viejo sigue
    ahí, y sigue abriendo la puerta— y obliga a respaldar y a montar un volumen para
    algo que se regenera en milisegundos.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'qr_publico'

    @method_decorator(cache_control(max_age=3600, private=True))
    def get(self, request, token):
        metodo = MetodoAcceso.objects.select_related('socio').filter(
            token=token, tipo='qr', activo=True,
        ).first()
        # Un QR revocado, o de un socio dado de baja o borrado, deja de servirse: si
        # no, el enlace sigue entregando una credencial que ya no vale y el socio se
        # presenta en la puerta con ella.
        if (
            metodo is None
            or metodo.socio.eliminado_en is not None
            or not metodo.socio.activo
        ):
            return HttpResponse(status=404)

        # box_size 20 deja el código sobre los 550 px. WhatsApp recomprime lo que pasa
        # por el chat, y un PNG de 350 px llega con los módulos lavados justo cuando el
        # socio lo enseña en la puerta desde la pantalla del teléfono.
        imagen = qrcode.make(token, box_size=20, border=4)
        buffer = io.BytesIO()
        imagen.save(buffer, format='PNG')
        # Sin nombre ni datos del socio en la respuesta: quien abra el enlace ve un
        # código, no a quién pertenece.
        return HttpResponse(buffer.getvalue(), content_type='image/png')


class QRPaginaView(APIView):
    """La página que abre el socio desde el chat: su código QR, a pantalla completa.

    El enlace del mensaje apunta aquí y no al `.png` directo por dos razones. Una, que
    varios navegadores móviles descargan una URL de imagen en vez de mostrarla, y el
    socio acaba con un archivo en la carpeta de descargas en vez de un código que
    enseñar en la puerta. Y dos, que WhatsApp previsualiza los enlaces leyendo las
    etiquetas Open Graph: con `og:image` apuntando al PNG, la miniatura del QR se ve
    en el chat sin que nadie abra nada.

    Deliberadamente NO lleva el nombre del socio ni ningún dato suyo: el enlace se
    reenvía con un toque, y lo único que debe viajar es el código. El nombre del
    gimnasio sí, porque orienta al socio y no es un dato personal de él.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'qr_publico'

    def get(self, request, token):
        metodo = MetodoAcceso.objects.select_related('socio__gym').filter(
            token=token, tipo='qr', activo=True,
        ).first()
        if (
            metodo is None
            or metodo.socio.eliminado_en is not None
            or not metodo.socio.activo
        ):
            return HttpResponse(
                '<!doctype html><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<body style="font-family:system-ui;text-align:center;padding:48px 24px">'
                '<h1 style="font-size:18px">Este código ya no está disponible</h1>'
                '<p style="color:#666;font-size:14px">Pídele uno nuevo a recepción.</p>',
                status=404, content_type='text/html; charset=utf-8',
            )

        gym = escape(metodo.socio.gym.nombre if metodo.socio.gym_id else 'tu gimnasio')
        png = url_qr(request, metodo.token, 'qr-imagen')
        return HttpResponse(f"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tu código de acceso</title>
<meta property="og:title" content="Tu código de acceso · {gym}">
<meta property="og:description" content="Muéstralo en la entrada para registrar tu acceso.">
<meta property="og:image" content="{png}">
<meta property="og:type" content="website">
</head>
<body style="margin:0;background:#0d1117;color:#fff;font-family:system-ui,-apple-system,sans-serif;
             min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px">
  <div style="text-align:center;max-width:420px;width:100%">
    <p style="font-size:12px;letter-spacing:.18em;color:#8b949e;margin:0 0 4px">{gym}</p>
    <h1 style="font-size:18px;font-weight:800;margin:0 0 20px">Tu código de acceso</h1>
    <!-- Fondo blanco propio: el QR sobre el fondo oscuro no lo lee ningún escáner. -->
    <div style="background:#fff;padding:16px;border-radius:16px;display:inline-block;width:100%;
                box-sizing:border-box">
      <img src="{png}" alt="Código QR de acceso"
           style="width:100%;height:auto;display:block;image-rendering:pixelated">
    </div>
    <p style="font-size:13px;color:#8b949e;line-height:1.5;margin:20px 0 0">
      Muéstralo en la entrada para registrar tu acceso.<br>
      Mantén pulsada la imagen para guardarla en tu teléfono.
    </p>
  </div>
</body></html>""", content_type='text/html; charset=utf-8')


class RegistrarVisitaView(APIView):
    """Da de alta al visitante de mostrador: cobra, lo deja entrar y lo registra.

    El que llega de la calle, paga el día y entra no existía en el sistema: recepción
    cobraba a mano y le abría la puerta, así que ese dinero no salía en el corte y esa
    persona no salía en la afluencia. Justo las dos cosas que el negocio mira al
    cerrar.

    Se crea como Socio marcado `es_visita`, y no como entidad aparte, por el dinero:
    `Pago` cuelga de una membresía y el corte de caja suma pagos de membresía. Con un
    modelo de visita independiente el cobro del día quedaría fuera del cierre —el
    agujero que el corte vino a tapar— o habría que sumarlo en dos sitios. De paso, el
    visitante que vuelve y se inscribe conserva su historial: se le quita la marca.
    """

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'checkin'

    def post(self, request):
        entrada = VisitaSerializer(data=request.data, context={'request': request})
        entrada.is_valid(raise_exception=True)
        v = entrada.validated_data
        sucursal, plan = v['sucursal'], v['plan']

        # Recepción cobra en su puerta. Igual que en la venta de tienda: sin esto, un
        # POST con la sucursal de al lado mete la visita y su cobro en el corte ajeno.
        propia = getattr(request.user, 'sucursal_id', None)
        if propia is not None and sucursal.id != propia:
            raise ValidationError(
                {'sucursal': 'Solo puedes registrar visitas en tu sucursal.'}
            )

        hoy = timezone.localdate()
        with transaction.atomic():
            socio = Socio.objects.create(
                gym_id=request.user.gym_id,
                sucursal=sucursal,
                nombre=v['nombre'].strip(),
                apellido=v.get('apellido', '').strip(),
                telefono=v.get('telefono', '').strip(),
                es_visita=True,
                numero_socio=siguiente_numero_socio(request.user.gym_id),
            )
            membresia = Membresia.objects.create(
                socio=socio, plan=plan, sucursal=sucursal,
                fecha_inicio=hoy,
                # Vale por hoy: mañana ya no está vigente y no vuelve a abrir la
                # puerta. Sin fecha_fin sería un pase indefinido pagado como un día.
                fecha_fin=hoy,
                estado='activa',
            )
            pago = Pago.objects.create(
                membresia=membresia, monto=v['monto'], metodo=v['metodo'],
                registrado_por=request.user,
            )
            acceso = Acceso.objects.create(
                socio=socio, sucursal=sucursal, membresia=membresia,
                metodo_usado='manual', resultado='permitido',
            )

        return Response({
            'socio_id': socio.id,
            'numero_socio': socio.numero_socio,
            'nombre': f'{socio.nombre} {socio.apellido}'.strip(),
            'plan': plan.nombre,
            'monto': pago.monto,
            'metodo': pago.metodo,
            'acceso_id': acceso.id,
            'sucursal': sucursal.nombre,
        }, status=status.HTTP_201_CREATED)
