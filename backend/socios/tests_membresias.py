"""Matriz de estados de membresía: qué ve el módulo de Socios y qué deja pasar el check-in.

Cubre la pregunta central: ¿un socio con membresía NO activa (vencida, suspendida,
pendiente de pago, o activa pero con fecha_fin ya pasada) se muestra correctamente
en el apartado de Socios y se comporta igual en el kiosco de acceso?
"""

from datetime import date, timedelta

from rest_framework import status

from accesos.models import Acceso, MetodoAcceso
from gyms.models import Sucursal
from gyms.tests import BaseAPITestCase
from socios.models import Plan, Socio, Membresia, Pago

HOY = date.today


class MembresiaBase(BaseAPITestCase):
    """Un socio por cada estado de membresía, más los casos frontera de fecha."""

    def setUp(self):
        super().setUp()
        self.plan = Plan.objects.create(
            gym=self.gym, nombre='Mensual', tipo='mensual', precio=500, duracion_dias=30,
        )

    def crear_socio(self, nombre, estado=None, fecha_inicio=None, fecha_fin=None,
                    activo=True, token=None):
        """Crea socio (+ membresía si se pasa estado) y su método de acceso QR."""
        socio = Socio.objects.create(
            gym=self.gym, nombre=nombre, apellido='Test', activo=activo,
        )
        MetodoAcceso.objects.create(
            socio=socio, tipo='qr', token=token or f'QR-{nombre.upper()}',
        )
        membresia = None
        if estado:
            membresia = Membresia.objects.create(
                socio=socio, plan=self.plan, sucursal=self.sucursal,
                fecha_inicio=fecha_inicio or HOY(),
                fecha_fin=fecha_fin if fecha_fin is not False else None,
                estado=estado,
            )
        return socio, membresia

    def socio_en_lista(self, socio):
        resp = self.client.get('/api/socios/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        return next((s for s in resp.data if s['id'] == socio.id), None)


class SociosListaMuestraTodosLosEstadosTests(MembresiaBase):
    """El listado de Socios debe incluir al socio sin importar el estado de su membresía.

    Un socio moroso que desaparece de la lista es un socio que nadie cobra.
    """

    def test_lista_incluye_socio_con_membresia_activa(self):
        socio, _ = self.crear_socio('Activo', estado='activa',
                                    fecha_fin=HOY() + timedelta(days=30))
        self.assertIsNotNone(self.socio_en_lista(socio))

    def test_lista_incluye_socio_con_membresia_vencida(self):
        socio, _ = self.crear_socio('Vencido', estado='vencida',
                                    fecha_inicio=HOY() - timedelta(days=60),
                                    fecha_fin=HOY() - timedelta(days=1))
        self.assertIsNotNone(self.socio_en_lista(socio))

    def test_lista_incluye_socio_con_membresia_suspendida(self):
        socio, _ = self.crear_socio('Suspendido', estado='suspendida',
                                    fecha_fin=HOY() + timedelta(days=30))
        self.assertIsNotNone(self.socio_en_lista(socio))

    def test_lista_incluye_socio_con_membresia_pendiente_pago(self):
        socio, _ = self.crear_socio('Pendiente', estado='pendiente_pago',
                                    fecha_fin=HOY() + timedelta(days=30))
        self.assertIsNotNone(self.socio_en_lista(socio))

    def test_lista_incluye_socio_sin_ninguna_membresia(self):
        socio, _ = self.crear_socio('SinPlan')
        fila = self.socio_en_lista(socio)
        self.assertIsNotNone(fila)
        self.assertIsNone(fila['membresia_activa'])

    def test_lista_incluye_socio_dado_de_baja(self):
        socio, _ = self.crear_socio('Baja', estado='vencida', activo=False,
                                    fecha_fin=HOY() - timedelta(days=5))
        fila = self.socio_en_lista(socio)
        self.assertIsNotNone(fila)
        self.assertFalse(fila['activo'])

    def test_los_seis_casos_aparecen_juntos(self):
        self.crear_socio('Uno', estado='activa', fecha_fin=HOY() + timedelta(days=30))
        self.crear_socio('Dos', estado='vencida', fecha_fin=HOY() - timedelta(days=1))
        self.crear_socio('Tres', estado='suspendida', fecha_fin=HOY() + timedelta(days=10))
        self.crear_socio('Cuatro', estado='pendiente_pago', fecha_fin=HOY() + timedelta(days=10))
        self.crear_socio('Cinco')
        self.crear_socio('Seis', estado='vencida', activo=False, fecha_fin=HOY() - timedelta(days=90))

        resp = self.client.get('/api/socios/')
        nombres = sorted(s['nombre'] for s in resp.data)
        self.assertEqual(nombres, ['Cinco', 'Cuatro', 'Dos', 'Seis', 'Tres', 'Uno'])


class MembresiaActivaCampoTests(MembresiaBase):
    """`membresia_activa` es el campo que alimenta las columnas PLAN y PRÓX. PAGO."""

    def test_activa_vigente_se_expone(self):
        socio, _ = self.crear_socio('Activo', estado='activa',
                                    fecha_fin=HOY() + timedelta(days=30))
        ma = self.socio_en_lista(socio)['membresia_activa']
        self.assertIsNotNone(ma)
        self.assertEqual(ma['plan'], 'Mensual')
        self.assertEqual(ma['estado'], 'activa')

    def test_vencida_no_se_expone_como_activa(self):
        socio, _ = self.crear_socio('Vencido', estado='vencida',
                                    fecha_inicio=HOY() - timedelta(days=60),
                                    fecha_fin=HOY() - timedelta(days=1))
        self.assertIsNone(self.socio_en_lista(socio)['membresia_activa'])

    def test_suspendida_no_se_expone_como_activa(self):
        socio, _ = self.crear_socio('Suspendido', estado='suspendida',
                                    fecha_fin=HOY() + timedelta(days=30))
        self.assertIsNone(self.socio_en_lista(socio)['membresia_activa'])

    def test_pendiente_pago_no_se_expone_como_activa(self):
        socio, _ = self.crear_socio('Pendiente', estado='pendiente_pago',
                                    fecha_fin=HOY() + timedelta(days=30))
        self.assertIsNone(self.socio_en_lista(socio)['membresia_activa'])

    def test_membresia_sin_fecha_fin_es_activa(self):
        """Plan de visita suelta / sin vencimiento: fecha_fin nula sigue siendo vigente."""
        socio, _ = self.crear_socio('Indefinido', estado='activa', fecha_fin=False)
        ma = self.socio_en_lista(socio)['membresia_activa']
        self.assertIsNotNone(ma)
        self.assertIsNone(ma['fecha_fin'])

    def test_membresia_que_vence_hoy_sigue_vigente(self):
        """Frontera: el último día de la membresía todavía cuenta."""
        socio, _ = self.crear_socio('VenceHoy', estado='activa', fecha_fin=HOY())
        self.assertIsNotNone(self.socio_en_lista(socio)['membresia_activa'])

    def test_BUG_activa_con_fecha_vencida_no_deberia_exponerse(self):
        """BUG: SocioSerializer.get_membresia_activa filtra solo por estado='activa'
        y nunca compara fecha_fin contra hoy (socios/serializers.py:25).

        Nada en el backend cambia el estado a 'vencida' cuando pasa la fecha, así que
        una membresía que expiró ayer se sigue publicando como activa. El kiosco
        (accesos/views.py:79-85) SÍ compara fechas y le niega el paso.
        Resultado: el socio se ve al corriente en la lista pero no puede entrar.

        Se espera que falle hasta que el serializer aplique el mismo filtro de fecha.
        """
        socio, _ = self.crear_socio('Fantasma', estado='activa',
                                    fecha_inicio=HOY() - timedelta(days=60),
                                    fecha_fin=HOY() - timedelta(days=1))
        self.assertIsNone(self.socio_en_lista(socio)['membresia_activa'])

    def test_BUG_activa_con_fecha_futura_no_deberia_exponerse(self):
        """BUG (misma causa): una membresía que arranca la próxima semana ya se
        publica como activa. El check-in la rechaza por fecha_inicio__lte=hoy."""
        socio, _ = self.crear_socio('Futuro', estado='activa',
                                    fecha_inicio=HOY() + timedelta(days=7),
                                    fecha_fin=HOY() + timedelta(days=37))
        self.assertIsNone(self.socio_en_lista(socio)['membresia_activa'])


class ConsistenciaSociosVsCheckInTests(MembresiaBase):
    """`membresia_activa` en Socios y el veredicto del kiosco deben coincidir siempre.

    Si divergen, recepción cobra (o no cobra) con información distinta a la que
    usa la puerta.
    """

    def _veredicto_lista(self, socio):
        return self.socio_en_lista(socio)['membresia_activa'] is not None

    def _veredicto_checkin(self, token):
        resp = self.client.post('/api/accesos/checkin/', {
            'token': token, 'sucursal_id': self.sucursal.id,
        })
        return resp.status_code == status.HTTP_200_OK

    def test_activa_vigente_coincide(self):
        socio, _ = self.crear_socio('Ok', estado='activa',
                                    fecha_fin=HOY() + timedelta(days=30))
        self.assertTrue(self._veredicto_lista(socio))
        self.assertTrue(self._veredicto_checkin('QR-OK'))

    def test_vencida_coincide(self):
        socio, _ = self.crear_socio('Vieja', estado='vencida',
                                    fecha_inicio=HOY() - timedelta(days=60),
                                    fecha_fin=HOY() - timedelta(days=1))
        self.assertFalse(self._veredicto_lista(socio))
        self.assertFalse(self._veredicto_checkin('QR-VIEJA'))

    def test_suspendida_coincide(self):
        socio, _ = self.crear_socio('Susp', estado='suspendida',
                                    fecha_fin=HOY() + timedelta(days=30))
        self.assertFalse(self._veredicto_lista(socio))
        self.assertFalse(self._veredicto_checkin('QR-SUSP'))

    def test_pendiente_pago_coincide(self):
        socio, _ = self.crear_socio('Debe', estado='pendiente_pago',
                                    fecha_fin=HOY() + timedelta(days=30))
        self.assertFalse(self._veredicto_lista(socio))
        self.assertFalse(self._veredicto_checkin('QR-DEBE'))

    def test_sin_membresia_coincide(self):
        socio, _ = self.crear_socio('Nadie')
        self.assertFalse(self._veredicto_lista(socio))
        self.assertFalse(self._veredicto_checkin('QR-NADIE'))

    def test_BUG_activa_expirada_diverge(self):
        """BUG: mismo caso del serializer. La lista dice que sí, la puerta dice que no."""
        socio, _ = self.crear_socio('Diverge', estado='activa',
                                    fecha_inicio=HOY() - timedelta(days=60),
                                    fecha_fin=HOY() - timedelta(days=1))
        self.assertEqual(self._veredicto_lista(socio), self._veredicto_checkin('QR-DIVERGE'))


class CheckInPorEstadoTests(MembresiaBase):
    """El kiosco por cada estado, incluyendo el motivo y la notificación generada."""

    def _checkin(self, token):
        return self.client.post('/api/accesos/checkin/', {
            'token': token, 'sucursal_id': self.sucursal.id,
        })

    def test_suspendida_es_denegada(self):
        socio, _ = self.crear_socio('Susp', estado='suspendida',
                                    fecha_fin=HOY() + timedelta(days=30))
        resp = self._checkin('QR-SUSP')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Acceso.objects.get(socio=socio).motivo_denegado, 'membresia_vencida')

    def test_pendiente_pago_es_denegada(self):
        socio, _ = self.crear_socio('Debe', estado='pendiente_pago',
                                    fecha_fin=HOY() + timedelta(days=30))
        resp = self._checkin('QR-DEBE')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Acceso.objects.get(socio=socio).motivo_denegado, 'membresia_vencida')

    def test_activa_que_aun_no_empieza_es_denegada(self):
        self.crear_socio('Futuro', estado='activa',
                         fecha_inicio=HOY() + timedelta(days=7),
                         fecha_fin=HOY() + timedelta(days=37))
        self.assertEqual(self._checkin('QR-FUTURO').status_code, status.HTTP_403_FORBIDDEN)

    def test_activa_que_expiro_ayer_es_denegada(self):
        self.crear_socio('Ayer', estado='activa',
                         fecha_inicio=HOY() - timedelta(days=31),
                         fecha_fin=HOY() - timedelta(days=1))
        self.assertEqual(self._checkin('QR-AYER').status_code, status.HTTP_403_FORBIDDEN)

    def test_activa_que_vence_hoy_es_permitida(self):
        self.crear_socio('Hoy', estado='activa',
                         fecha_inicio=HOY() - timedelta(days=30), fecha_fin=HOY())
        self.assertEqual(self._checkin('QR-HOY').status_code, status.HTTP_200_OK)

    def test_activa_sin_fecha_fin_es_permitida(self):
        self.crear_socio('Libre', estado='activa', fecha_fin=False)
        self.assertEqual(self._checkin('QR-LIBRE').status_code, status.HTTP_200_OK)

    def test_socio_dado_de_baja_con_membresia_activa_no_entra(self):
        """Dar de baja a un socio le cierra la puerta, tenga la membresía que tenga.

        Este test afirmaba lo contrario y su docstring lo decía sin rodeos: «el
        check-in no mira Socio.activo». Era un test de caracterización —dejaba por
        escrito el comportamiento que había, no el que se quería—, así que al cerrar
        el hueco se invierte en vez de borrarse: el caso sigue cubierto, ahora con el
        resultado correcto.
        """
        socio, _ = self.crear_socio('Baja', estado='activa', activo=False,
                                    fecha_fin=HOY() + timedelta(days=30))
        resp = self._checkin('QR-BAJA')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Acceso.objects.get(socio=socio).motivo_denegado, 'suspendido')

    def test_baja_pesa_mas_que_la_membresia_vencida(self):
        """El motivo importa: a un socio de baja Y vencido se le dice que está de
        baja, no que debe. Si dijera «membresía vencida», en el mostrador lo
        atenderían cobrándole, que es justo reactivar a quien se dio de baja."""
        socio, _ = self.crear_socio('BajaVencida', estado='vencida', activo=False,
                                    fecha_inicio=HOY() - timedelta(days=60),
                                    fecha_fin=HOY() - timedelta(days=1))
        self.assertEqual(self._checkin('QR-BAJAVENCIDA').status_code,
                         status.HTTP_403_FORBIDDEN)
        self.assertEqual(Acceso.objects.get(socio=socio).motivo_denegado, 'suspendido')

    def test_vencida_genera_notificacion_de_cobranza(self):
        from notificaciones.models import Notificacion
        self.crear_socio('Moroso', estado='vencida',
                         fecha_inicio=HOY() - timedelta(days=60),
                         fecha_fin=HOY() - timedelta(days=1))
        self._checkin('QR-MOROSO')
        noti = Notificacion.objects.filter(gym=self.gym, tipo='pago_vencido')
        self.assertEqual(noti.count(), 1)
        self.assertIn('Moroso', noti.first().mensaje)

    def test_sin_membresia_no_genera_notificacion(self):
        from notificaciones.models import Notificacion
        self.crear_socio('Nuevo')
        self._checkin('QR-NUEVO')
        self.assertFalse(Notificacion.objects.filter(tipo='pago_vencido').exists())

    def test_socio_con_dos_membresias_usa_la_vigente(self):
        """Historial: la vieja vencida no debe bloquear a la nueva activa."""
        socio, _ = self.crear_socio('Renovado', estado='vencida',
                                    fecha_inicio=HOY() - timedelta(days=60),
                                    fecha_fin=HOY() - timedelta(days=31))
        Membresia.objects.create(
            socio=socio, plan=self.plan, sucursal=self.sucursal,
            fecha_inicio=HOY(), fecha_fin=HOY() + timedelta(days=30), estado='activa',
        )
        self.assertEqual(self._checkin('QR-RENOVADO').status_code, status.HTTP_200_OK)


class MembresiaEndpointTests(MembresiaBase):
    """/api/socios/membresias/ — alimenta las pantallas Membresías y Pagos."""

    def test_lista_devuelve_todos_los_estados(self):
        for estado in ('activa', 'vencida', 'suspendida', 'pendiente_pago'):
            self.crear_socio(estado.capitalize(), estado=estado,
                             fecha_fin=HOY() + timedelta(days=30))
        resp = self.client.get('/api/socios/membresias/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        estados = sorted(m['estado'] for m in resp.data)
        self.assertEqual(estados, ['activa', 'pendiente_pago', 'suspendida', 'vencida'])

    def test_lista_incluye_nombres_desnormalizados(self):
        self.crear_socio('Ana', estado='activa', fecha_fin=HOY() + timedelta(days=30))
        m = self.client.get('/api/socios/membresias/').data[0]
        self.assertEqual(m['socio_nombre'], 'Ana Test')
        self.assertEqual(m['plan_nombre'], 'Mensual')
        self.assertEqual(m['plan_precio'], '500.00')

    def test_cambiar_estado_a_vencida(self):
        _, membresia = self.crear_socio('Ana', estado='activa',
                                        fecha_fin=HOY() + timedelta(days=30))
        resp = self.client.patch(f'/api/socios/membresias/{membresia.id}/', {'estado': 'vencida'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        membresia.refresh_from_db()
        self.assertEqual(membresia.estado, 'vencida')

    def test_estado_invalido_es_rechazado(self):
        _, membresia = self.crear_socio('Ana', estado='activa',
                                        fecha_fin=HOY() + timedelta(days=30))
        resp = self.client.patch(f'/api/socios/membresias/{membresia.id}/', {'estado': 'inventado'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_membresias_de_otro_gym_ocultas(self):
        otra_sucursal = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        otro_plan = Plan.objects.create(gym=self.otro_gym, nombre='Ajeno', tipo='mensual', precio=1)
        ajeno = Socio.objects.create(gym=self.otro_gym, nombre='Pedro', apellido='Ajeno')
        Membresia.objects.create(
            socio=ajeno, plan=otro_plan, sucursal=otra_sucursal,
            fecha_inicio=HOY(), estado='activa',
        )
        self.crear_socio('Mia', estado='activa', fecha_fin=HOY() + timedelta(days=30))
        resp = self.client.get('/api/socios/membresias/')
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['socio_nombre'], 'Mia Test')

    def test_no_puede_leer_membresia_de_otro_gym(self):
        otra_sucursal = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        otro_plan = Plan.objects.create(gym=self.otro_gym, nombre='Ajeno', tipo='mensual', precio=1)
        ajeno = Socio.objects.create(gym=self.otro_gym, nombre='Pedro', apellido='Ajeno')
        m = Membresia.objects.create(
            socio=ajeno, plan=otro_plan, sucursal=otra_sucursal,
            fecha_inicio=HOY(), estado='activa',
        )
        resp = self.client.get(f'/api/socios/membresias/{m.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_BUG_no_deberia_poder_crear_membresia_para_socio_de_otro_gym(self):
        """BUG: MembresiaViewSet (socios/views.py:46-51) filtra el queryset de lectura
        por gym pero no valida nada en la escritura: no hay perform_create ni
        validate() que confirme que socio/plan/sucursal pertenecen al gym del usuario.

        Un admin puede crear membresías sobre socios de otro negocio.
        Compárese con PagoViewSet.perform_create, que sí valida (socios/views.py:62-64).
        """
        otra_sucursal = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        otro_plan = Plan.objects.create(gym=self.otro_gym, nombre='Ajeno', tipo='mensual', precio=1)
        ajeno = Socio.objects.create(gym=self.otro_gym, nombre='Pedro', apellido='Ajeno')
        resp = self.client.post('/api/socios/membresias/', {
            'socio': ajeno.id, 'plan': otro_plan.id, 'sucursal': otra_sucursal.id,
            'fecha_inicio': HOY().isoformat(), 'estado': 'activa',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_recepcion_puede_gestionar_membresias(self):
        """Recepción cobra y renueva: necesita escritura sobre membresías."""
        from usuarios.models import Usuario
        recepcion = Usuario.objects.create_user(
            email='recep@round3.com', password='Passw0rd1', nombre='Recep',
            rol='recepcion', gym=self.gym,
        )
        socio, _ = self.crear_socio('Ana')
        self.authenticate(recepcion)
        resp = self.client.post('/api/socios/membresias/', {
            'socio': socio.id, 'plan': self.plan.id, 'sucursal': self.sucursal.id,
            'fecha_inicio': HOY().isoformat(), 'estado': 'activa',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)


class PagoReactivaMembresiaTests(MembresiaBase):
    """Registrar un pago debe reactivar y recorrer el período (socios/views.py:61-77)."""

    def test_pago_reactiva_membresia_vencida(self):
        socio, membresia = self.crear_socio('Moroso', estado='vencida',
                                            fecha_inicio=HOY() - timedelta(days=60),
                                            fecha_fin=HOY() - timedelta(days=1))
        resp = self.client.post('/api/socios/pagos/', {
            'membresia': membresia.id, 'monto': '500.00', 'metodo': 'efectivo',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        membresia.refresh_from_db()
        self.assertEqual(membresia.estado, 'activa')
        self.assertEqual(membresia.fecha_inicio, HOY())
        self.assertEqual(membresia.fecha_fin, HOY() + timedelta(days=30))

    def test_pago_reactiva_pendiente_de_pago(self):
        _, membresia = self.crear_socio('Debe', estado='pendiente_pago',
                                        fecha_fin=HOY() + timedelta(days=30))
        self.client.post('/api/socios/pagos/', {
            'membresia': membresia.id, 'monto': '500.00', 'metodo': 'tarjeta',
        })
        membresia.refresh_from_db()
        self.assertEqual(membresia.estado, 'activa')

    def test_socio_puede_entrar_despues_de_pagar(self):
        """Flujo completo: vencido → denegado → paga → permitido."""
        socio, membresia = self.crear_socio('Moroso', estado='vencida',
                                            fecha_inicio=HOY() - timedelta(days=60),
                                            fecha_fin=HOY() - timedelta(days=1))
        antes = self.client.post('/api/accesos/checkin/', {
            'token': 'QR-MOROSO', 'sucursal_id': self.sucursal.id,
        })
        self.assertEqual(antes.status_code, status.HTTP_403_FORBIDDEN)

        self.client.post('/api/socios/pagos/', {
            'membresia': membresia.id, 'monto': '500.00', 'metodo': 'efectivo',
        })

        despues = self.client.post('/api/accesos/checkin/', {
            'token': 'QR-MOROSO', 'sucursal_id': self.sucursal.id,
        })
        self.assertEqual(despues.status_code, status.HTTP_200_OK)
        self.assertEqual(despues.data['plan'], 'Mensual')

    def test_pago_repone_clases_en_plan_por_paquete(self):
        plan_clases = Plan.objects.create(
            gym=self.gym, nombre='10 Clases', tipo='clases', precio=800, num_clases=10,
        )
        socio, _ = self.crear_socio('Paquete')
        membresia = Membresia.objects.create(
            socio=socio, plan=plan_clases, sucursal=self.sucursal,
            fecha_inicio=HOY() - timedelta(days=20), clases_restantes=0, estado='vencida',
        )
        self.client.post('/api/socios/pagos/', {
            'membresia': membresia.id, 'monto': '800.00', 'metodo': 'efectivo',
        })
        membresia.refresh_from_db()
        self.assertEqual(membresia.clases_restantes, 10)
        self.assertEqual(membresia.estado, 'activa')

    def test_plan_sin_duracion_deja_fecha_fin_nula(self):
        plan_visita = Plan.objects.create(
            gym=self.gym, nombre='Visita', tipo='visita', precio=80,
        )
        socio, _ = self.crear_socio('Visitante')
        membresia = Membresia.objects.create(
            socio=socio, plan=plan_visita, sucursal=self.sucursal,
            fecha_inicio=HOY(), fecha_fin=HOY(), estado='pendiente_pago',
        )
        self.client.post('/api/socios/pagos/', {
            'membresia': membresia.id, 'monto': '80.00', 'metodo': 'efectivo',
        })
        membresia.refresh_from_db()
        self.assertIsNone(membresia.fecha_fin)

    def test_pago_sobre_membresia_de_otro_gym_es_rechazado(self):
        otra_sucursal = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        otro_plan = Plan.objects.create(gym=self.otro_gym, nombre='Ajeno', tipo='mensual', precio=1)
        ajeno = Socio.objects.create(gym=self.otro_gym, nombre='Pedro', apellido='Ajeno')
        m = Membresia.objects.create(
            socio=ajeno, plan=otro_plan, sucursal=otra_sucursal,
            fecha_inicio=HOY(), estado='vencida',
        )
        resp = self.client.post('/api/socios/pagos/', {
            'membresia': m.id, 'monto': '1.00', 'metodo': 'efectivo',
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        m.refresh_from_db()
        self.assertEqual(m.estado, 'vencida')

    def test_pago_registra_quien_cobro(self):
        _, membresia = self.crear_socio('Ana', estado='vencida',
                                        fecha_fin=HOY() - timedelta(days=1))
        resp = self.client.post('/api/socios/pagos/', {
            'membresia': membresia.id, 'monto': '500.00', 'metodo': 'efectivo',
        })
        pago = Pago.objects.get(id=resp.data['id'])
        self.assertEqual(pago.registrado_por, self.user)

    def test_registrado_por_no_es_falsificable(self):
        from usuarios.models import Usuario
        otro = Usuario.objects.create_user(
            email='otro@round3.com', password='Passw0rd1', nombre='Otro',
            rol='recepcion', gym=self.gym,
        )
        _, membresia = self.crear_socio('Ana', estado='vencida',
                                        fecha_fin=HOY() - timedelta(days=1))
        resp = self.client.post('/api/socios/pagos/', {
            'membresia': membresia.id, 'monto': '500.00', 'metodo': 'efectivo',
            'registrado_por': otro.id,
        })
        pago = Pago.objects.get(id=resp.data['id'])
        self.assertEqual(pago.registrado_por, self.user)
