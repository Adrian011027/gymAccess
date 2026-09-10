"""Registro de visitas de mostrador: /api/accesos/visita/

El visitante que llega de la calle, paga el día y entra no existía en el sistema.
Recepción cobraba a mano y abría la puerta, así que ese dinero no salía en el corte
del día y esa persona no salía en la afluencia — las dos cosas que el negocio mira al
cerrar.

Lo que estas pruebas fijan es que la visita quede en las TRES tablas que la hacen
contable: el cobro, la bitácora de accesos y el padrón (marcada, para no ensuciarlo).
"""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import status

from accesos.models import Acceso
from gyms.models import Sucursal
from gyms.tests import BaseAPITestCase
from socios.models import Membresia, Pago, Plan, PrecioPlanSucursal, Socio
from usuarios.models import Usuario

URL = '/api/accesos/visita/'


class VisitaBase(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.plan_visita = Plan.objects.create(
            gym=self.gym, nombre='Visita', tipo='visita', precio=Decimal('80'),
            duracion_dias=1,
        )
        self.plan_mensual = Plan.objects.create(
            gym=self.gym, nombre='Mensual', tipo='mensual', precio=Decimal('500'),
            duracion_dias=30,
        )

    def registrar(self, **extra):
        cuerpo = {
            'nombre': 'Luis', 'apellido': 'Ramirez', 'telefono': '3322332046',
            'plan': self.plan_visita.id, 'sucursal': self.sucursal.id,
            'metodo': 'efectivo',
        }
        cuerpo.update(extra)
        return self.client.post(URL, cuerpo)


class VisitaQuedaRegistradaTests(VisitaBase):
    def test_crea_socio_marcado_como_visita(self):
        resp = self.registrar()

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        socio = Socio.objects.get(id=resp.data['socio_id'])
        self.assertTrue(socio.es_visita)
        self.assertEqual(socio.nombre, 'Luis')
        self.assertEqual(socio.telefono, '3322332046')
        self.assertEqual(socio.sucursal_id, self.sucursal.id)

    def test_cobra_y_el_pago_queda_colgado_de_la_membresia(self):
        """Es lo que hace que la visita entre al corte de caja: el corte suma pagos de
        membresía, así que un cobro suelto no aparecería en el cierre del día."""
        resp = self.registrar()

        pago = Pago.objects.get(membresia__socio_id=resp.data['socio_id'])
        self.assertEqual(pago.monto, Decimal('80'))
        self.assertEqual(pago.metodo, 'efectivo')
        self.assertEqual(pago.registrado_por, self.user)

    def test_registra_el_acceso_en_la_bitacora(self):
        resp = self.registrar()

        acceso = Acceso.objects.get(socio_id=resp.data['socio_id'])
        self.assertEqual(acceso.resultado, 'permitido')
        self.assertEqual(acceso.metodo_usado, 'manual')
        self.assertEqual(acceso.sucursal_id, self.sucursal.id)

    def test_la_membresia_vale_solo_por_hoy(self):
        """Sin fecha_fin sería un pase indefinido cobrado como un día."""
        resp = self.registrar()

        m = Membresia.objects.get(socio_id=resp.data['socio_id'])
        hoy = timezone.localdate()
        self.assertEqual(m.fecha_inicio, hoy)
        self.assertEqual(m.fecha_fin, hoy)
        self.assertEqual(m.estado, 'activa')

    def test_manana_esa_membresia_ya_no_esta_vigente(self):
        resp = self.registrar()
        m = Membresia.objects.get(socio_id=resp.data['socio_id'])
        m.fecha_fin = timezone.localdate() - timedelta(days=1)
        m.save(update_fields=['fecha_fin'])

        self.assertFalse(Membresia.objects.vigentes().filter(id=m.id).exists())

    def test_toma_el_precio_del_plan_si_no_se_manda_monto(self):
        resp = self.registrar()
        self.assertEqual(Decimal(str(resp.data['monto'])), Decimal('80'))

    def test_acepta_un_monto_distinto_para_cortesias_y_promociones(self):
        resp = self.registrar(monto='50.00')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(
            Pago.objects.get(membresia__socio_id=resp.data['socio_id']).monto,
            Decimal('50'),
        )

    def test_la_visita_recibe_su_numero_de_socio_consecutivo(self):
        """Comparte el mismo contador que el alta normal: dos cuentas separadas
        chocarían contra el UniqueConstraint por gym."""
        primera = self.registrar().data['numero_socio']
        segunda = self.registrar(nombre='Otro').data['numero_socio']

        self.assertEqual(segunda, primera + 1)


class VisitaNoAceptaCualquierPlanTests(VisitaBase):
    def test_rechaza_un_plan_que_no_sea_de_visita(self):
        """Con la mensualidad daría acceso de un mes cobrando el precio de un día."""
        resp = self.registrar(plan=self.plan_mensual.id)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('plan', resp.data)
        self.assertFalse(Socio.objects.filter(es_visita=True).exists())

    def test_rechaza_el_plan_de_visita_de_otro_gym(self):
        ajeno = Plan.objects.create(
            gym=self.otro_gym, nombre='Visita', tipo='visita', precio=10, duracion_dias=1,
        )
        resp = self.registrar(plan=ajeno.id)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rechaza_una_sucursal_de_otro_gym(self):
        ajena = Sucursal.objects.create(gym=self.otro_gym, nombre='Ajena')
        resp = self.registrar(sucursal=ajena.id)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_el_nombre_es_obligatorio(self):
        resp = self.registrar(nombre='')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_metodo_de_pago_invalido_se_rechaza(self):
        resp = self.registrar(metodo='vales')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class VisitaAisladaPorSucursalTests(VisitaBase):
    def setUp(self):
        super().setUp()
        self.norte = Sucursal.objects.create(gym=self.gym, nombre='Norte')
        self.recepcion = Usuario.objects.create_user(
            email='recepcion@round3.com', password='Passw0rd1', nombre='Karla',
            rol='recepcion', gym=self.gym, sucursal=self.sucursal,
        )

    def test_recepcion_no_puede_registrar_la_visita_en_otra_sucursal(self):
        """Si no, el cobro cae en el corte del local de al lado."""
        self.authenticate(self.recepcion)
        resp = self.registrar(sucursal=self.norte.id)

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Socio.objects.filter(es_visita=True).exists())

    def test_recepcion_registra_en_la_suya(self):
        self.authenticate(self.recepcion)
        resp = self.registrar(sucursal=self.sucursal.id)

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

    def test_el_dueno_puede_registrar_en_cualquiera_de_sus_sucursales(self):
        resp = self.registrar(sucursal=self.norte.id)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)


class VisitaEntraAlCorteYALaAfluenciaTests(VisitaBase):
    """El recorrido completo: lo que el mostrador cobra tiene que aparecer al cerrar."""

    def test_el_cobro_de_la_visita_sale_en_el_corte_del_dia(self):
        self.registrar()

        corte = self.client.get('/api/socios/pagos/corte/').data

        self.assertEqual(Decimal(str(corte['membresias']['total'])), Decimal('80'))
        self.assertEqual(Decimal(str(corte['efectivo_esperado'])), Decimal('80'))
        self.assertEqual(
            [m['tipo'] for m in corte['movimientos']], ['membresia'],
        )

    def test_la_visita_cuenta_en_la_afluencia_del_dia(self):
        self.registrar()

        stats = self.client.get('/api/accesos/stats/?rango=hoy').data

        self.assertEqual(stats['accesos_hoy'], 1)


class VisitaSinSesionTests(VisitaBase):
    def test_sin_token_no_se_registran_visitas(self):
        self.client.credentials()
        resp = self.registrar()
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class VisitaNoEnsuciaElPadronTests(VisitaBase):
    """Para esto existe la marca `es_visita`.

    La visita se guarda como `Socio` porque su cobro tiene que colgar de una membresía
    para entrar al corte del día. El precio de esa decisión es que, sin filtro, cada
    persona que paga un día suelto aparecería en el padrón y en el conteo de socios
    que factura el SaaS.
    """

    def setUp(self):
        super().setUp()
        self.socio = Socio.objects.create(
            gym=self.gym, sucursal=self.sucursal, nombre='Ana', apellido='Torres',
            numero_socio=1000,
        )

    def test_el_listado_de_socios_no_trae_visitas(self):
        self.registrar()

        resp = self.client.get('/api/socios/')

        ids = [s['id'] for s in resp.data]
        self.assertEqual(ids, [self.socio.id])

    def test_el_socio_inscrito_sigue_saliendo(self):
        """El filtro esconde visitas, no socios: la comprobación que evita que un
        `padron()` mal puesto vacíe el listado entero sin que nadie lo note."""
        resp = self.client.get('/api/socios/')

        self.assertEqual([s['id'] for s in resp.data], [self.socio.id])

    def test_la_visita_si_aparece_al_buscarla_por_nombre(self):
        """El visitante que vuelve a inscribirse se busca por su nombre. Si no
        apareciera, recepción lo daría de alta otra vez y perdería el historial de
        accesos y pagos que la marca existe para conservar."""
        visita_id = self.registrar().data['socio_id']

        resp = self.client.get('/api/socios/?buscar=Luis')

        self.assertEqual([s['id'] for s in resp.data], [visita_id])

    def test_se_puede_abrir_la_ficha_de_la_visita_para_quitarle_la_marca(self):
        visita_id = self.registrar().data['socio_id']

        resp = self.client.patch(f'/api/socios/{visita_id}/', {'es_visita': False})

        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertFalse(Socio.objects.get(id=visita_id).es_visita)

    def test_una_vez_inscrita_vuelve_al_padron_con_su_historial(self):
        visita_id = self.registrar().data['socio_id']
        Socio.objects.filter(id=visita_id).update(es_visita=False)

        resp = self.client.get('/api/socios/')

        self.assertIn(visita_id, [s['id'] for s in resp.data])
        self.assertTrue(Acceso.objects.filter(socio_id=visita_id).exists())
        self.assertTrue(Pago.objects.filter(membresia__socio_id=visita_id).exists())

    def test_el_conteo_de_socios_del_saas_no_cuenta_visitas(self):
        """Es el número con el que se le argumenta al gym que suba de paquete."""
        self.registrar()
        superadmin = Usuario.objects.create_user(
            email='dueno@saas.com', password='Passw0rd1', nombre='Dueño',
            rol='superadmin',
        )
        self.authenticate(superadmin)

        tenant = next(
            g for g in self.client.get('/api/saas/tenants/').data if g['id'] == self.gym.id
        )
        resumen = self.client.get('/api/saas/resumen/').data

        self.assertEqual(tenant['socios'], 1)
        self.assertEqual(tenant['socios_vigentes'], 0)
        self.assertEqual(resumen['socios'], 1)
        self.assertEqual(resumen['socios_vigentes'], 0)


class VisitaCobraElPrecioDeSuSucursalTests(VisitaBase):
    """El precio de la visita puede variar por local, igual que el de las mensualidades.

    `PrecioPlanSucursal` ya existía y el alta de membresías lo respeta. Cobrando aquí
    el precio base, la sucursal con descuento metía la diferencia de más en su corte
    todos los días y el precio anunciado en su puerta dejaba de ser el que cobra.
    """

    def setUp(self):
        super().setUp()
        self.barata = Sucursal.objects.create(gym=self.gym, nombre='San Sebastián')
        PrecioPlanSucursal.objects.create(
            plan=self.plan_visita, sucursal=self.barata, precio=Decimal('50'),
        )

    def test_usa_la_excepcion_de_esa_sucursal(self):
        resp = self.registrar(sucursal=self.barata.id)

        self.assertEqual(Decimal(str(resp.data['monto'])), Decimal('50'))
        self.assertEqual(
            Pago.objects.get(membresia__socio_id=resp.data['socio_id']).monto,
            Decimal('50'),
        )

    def test_la_sucursal_sin_excepcion_sigue_cobrando_el_precio_base(self):
        resp = self.registrar()

        self.assertEqual(Decimal(str(resp.data['monto'])), Decimal('80'))

    def test_un_monto_explicito_sigue_mandando_sobre_el_precio_de_sucursal(self):
        """La cortesía del mostrador no la pisa el catálogo."""
        resp = self.registrar(sucursal=self.barata.id, monto='0')

        self.assertEqual(Decimal(str(resp.data['monto'])), Decimal('0'))


class VisitaNoSeCobraDosVecesTests(VisitaBase):
    """La visita ya pagó: no puede volver como deuda al día siguiente.

    Su membresía nace venciendo hoy, así que los dos filtros de cobro pendiente la
    recogían: el de /pagos ("fecha_fin ya pasó" = atrasado) al día siguiente, y el del
    Dashboard ("vence hoy") el mismo día en que se cobró. Recepción veía $70 por
    cobrar de alguien que ya pagó, entró y se fue.
    """

    def setUp(self):
        super().setUp()
        self.socio = Socio.objects.create(
            gym=self.gym, sucursal=self.sucursal, nombre='Ana', apellido='Torres',
            numero_socio=1000,
        )
        self.suya = Membresia.objects.create(
            socio=self.socio, plan=self.plan_mensual, sucursal=self.sucursal,
            fecha_inicio=timezone.localdate() - timedelta(days=30),
            fecha_fin=timezone.localdate() - timedelta(days=1),
            estado='activa',
        )

    def test_la_membresia_de_la_visita_no_sale_en_el_listado(self):
        self.registrar()

        resp = self.client.get('/api/socios/membresias/')

        self.assertEqual([m['id'] for m in resp.data], [self.suya.id])

    def test_el_socio_vencido_de_verdad_sigue_saliendo(self):
        """El filtro esconde visitas, no cobros: sin esto, "Por cobrar" se vaciaría
        entero y nadie notaría que dejó de reclamar las renovaciones."""
        self.registrar()

        resp = self.client.get('/api/socios/membresias/')

        self.assertIn(self.suya.id, [m['id'] for m in resp.data])

    def test_el_cobro_de_la_visita_sigue_en_el_corte(self):
        """Esconderla de "Por cobrar" no puede esconderla del cierre del día."""
        self.registrar()

        corte = self.client.get('/api/socios/pagos/corte/').data

        self.assertEqual(Decimal(str(corte['membresias']['total'])), Decimal('80'))

    def test_una_vez_inscrita_su_membresia_vuelve_al_listado(self):
        visita_id = self.registrar().data['socio_id']
        Socio.objects.filter(id=visita_id).update(es_visita=False)

        resp = self.client.get('/api/socios/membresias/')

        self.assertIn(visita_id, [m['socio'] for m in resp.data])
