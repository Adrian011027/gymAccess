"""Módulo de Clases y Equipamiento: CRUD, cupos, aislamiento por gym y permisos."""

from datetime import date

from rest_framework import status

from gyms.models import Clase, Equipamiento
from gyms.tests import BaseAPITestCase
from usuarios.models import Usuario

CLASE_VALIDA = {
    'nombre': 'Boxeo Fundamentos', 'tipo': 'resistencia', 'profesor': 'Coach A',
    'hora_inicio': '18:00', 'hora_fin': '19:00', 'dias': 'lun,mie,vie',
}


class ClaseBase(BaseAPITestCase):
    def crear_clase(self, gym=None, **kwargs):
        datos = {
            'nombre': 'Boxeo', 'tipo': 'resistencia', 'profesor': 'Coach A',
            'hora_inicio': '18:00', 'hora_fin': '19:00', 'dias': 'lun,mie',
        }
        datos.update(kwargs)
        return Clase.objects.create(gym=gym or self.gym, **datos)


class ClaseCRUDTests(ClaseBase):
    def test_crear_clase(self):
        resp = self.client.post('/api/gyms/clases/', CLASE_VALIDA)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['gym'], self.gym.id)
        self.assertEqual(resp.data['cupo_max'], 20)
        self.assertEqual(resp.data['inscritos'], 0)
        self.assertEqual(resp.data['nivel'], 'todos')

    def test_listar_clases(self):
        self.crear_clase(nombre='Sparring')
        resp = self.client.get('/api/gyms/clases/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual([c['nombre'] for c in resp.data], ['Sparring'])

    def test_editar_clase(self):
        clase = self.crear_clase()
        resp = self.client.patch(f'/api/gyms/clases/{clase.id}/', {
            'profesor': 'Coach B', 'cupo_max': 30,
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        clase.refresh_from_db()
        self.assertEqual(clase.profesor, 'Coach B')
        self.assertEqual(clase.cupo_max, 30)

    def test_borrar_clase(self):
        clase = self.crear_clase()
        resp = self.client.delete(f'/api/gyms/clases/{clase.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Clase.objects.filter(pk=clase.pk).exists())

    def test_clase_desactivada_no_aparece(self):
        self.crear_clase(nombre='Vigente')
        self.crear_clase(nombre='Cancelada', activa=False)
        resp = self.client.get('/api/gyms/clases/')
        nombres = [c['nombre'] for c in resp.data]
        self.assertIn('Vigente', nombres)
        self.assertNotIn('Cancelada', nombres)

    def test_desactivar_es_baja_logica(self):
        """Poner activa=False la saca del listado sin perder el registro."""
        clase = self.crear_clase()
        self.client.patch(f'/api/gyms/clases/{clase.id}/', {'activa': False})
        self.assertEqual(len(self.client.get('/api/gyms/clases/').data), 0)
        self.assertTrue(Clase.objects.filter(pk=clase.pk).exists())

    def test_tipo_invalido_es_rechazado(self):
        resp = self.client.post('/api/gyms/clases/', {**CLASE_VALIDA, 'tipo': 'yoga'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nivel_invalido_es_rechazado(self):
        resp = self.client.post('/api/gyms/clases/', {**CLASE_VALIDA, 'nivel': 'experto'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_faltan_campos_obligatorios(self):
        resp = self.client.post('/api/gyms/clases/', {'nombre': 'Incompleta'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        for campo in ('tipo', 'profesor', 'hora_inicio', 'hora_fin', 'dias'):
            self.assertIn(campo, resp.data)

    def test_hora_mal_formada_es_rechazada(self):
        resp = self.client.post('/api/gyms/clases/', {**CLASE_VALIDA, 'hora_inicio': '25:99'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inscritos_puede_llegar_al_cupo(self):
        clase = self.crear_clase(cupo_max=10)
        resp = self.client.patch(f'/api/gyms/clases/{clase.id}/', {'inscritos': 10})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        clase.refresh_from_db()
        self.assertEqual(clase.inscritos, 10)

    def test_inscritos_negativo_es_rechazado(self):
        clase = self.crear_clase()
        resp = self.client.patch(f'/api/gyms/clases/{clase.id}/', {'inscritos': -1})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sobrecupo_no_esta_validado(self):
        """Comportamiento actual: nada impide inscritos > cupo_max.

        Si el negocio necesita bloquear el sobrecupo, la regla va en el serializer.
        """
        clase = self.crear_clase(cupo_max=5)
        resp = self.client.patch(f'/api/gyms/clases/{clase.id}/', {'inscritos': 99})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class ClaseMultitenantTests(ClaseBase):
    def test_clases_de_otro_gym_ocultas(self):
        self.crear_clase(nombre='Mia')
        self.crear_clase(nombre='Ajena', gym=self.otro_gym)
        nombres = [c['nombre'] for c in self.client.get('/api/gyms/clases/').data]
        self.assertIn('Mia', nombres)
        self.assertNotIn('Ajena', nombres)

    def test_no_puede_leer_clase_de_otro_gym(self):
        ajena = self.crear_clase(gym=self.otro_gym)
        resp = self.client.get(f'/api/gyms/clases/{ajena.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_no_puede_editar_clase_de_otro_gym(self):
        ajena = self.crear_clase(gym=self.otro_gym, profesor='Suyo')
        resp = self.client.patch(f'/api/gyms/clases/{ajena.id}/', {'profesor': 'Robado'})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        ajena.refresh_from_db()
        self.assertEqual(ajena.profesor, 'Suyo')

    def test_no_puede_borrar_clase_de_otro_gym(self):
        ajena = self.crear_clase(gym=self.otro_gym)
        resp = self.client.delete(f'/api/gyms/clases/{ajena.id}/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Clase.objects.filter(pk=ajena.pk).exists())

    def test_gym_del_payload_es_ignorado(self):
        """perform_create fuerza el gym del usuario aunque el cliente mande otro."""
        resp = self.client.post('/api/gyms/clases/', {**CLASE_VALIDA, 'gym': self.otro_gym.id})
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(Clase.objects.get(id=resp.data['id']).gym_id, self.gym.id)


class ClasePermisosTests(ClaseBase):
    """Clases usa solo IsAuthenticated: recepción también administra el horario."""

    def setUp(self):
        super().setUp()
        self.recepcion = Usuario.objects.create_user(
            email='recep@round3.com', password='Passw0rd1', nombre='Recep',
            rol='recepcion', gym=self.gym,
        )

    def test_recepcion_puede_leer_clases(self):
        self.crear_clase()
        self.authenticate(self.recepcion)
        self.assertEqual(self.client.get('/api/gyms/clases/').status_code, status.HTTP_200_OK)

    def test_recepcion_puede_crear_clase(self):
        self.authenticate(self.recepcion)
        resp = self.client.post('/api/gyms/clases/', CLASE_VALIDA)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

    def test_recepcion_puede_borrar_clase(self):
        clase = self.crear_clase()
        self.authenticate(self.recepcion)
        resp = self.client.delete(f'/api/gyms/clases/{clase.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_anonimo_no_ve_clases(self):
        from rest_framework.test import APIClient
        self.assertEqual(
            APIClient().get('/api/gyms/clases/').status_code, status.HTTP_401_UNAUTHORIZED
        )


class EquipamientoDetalleTests(BaseAPITestCase):
    """Complementa gyms.tests.EquipamientoTests con validación y baja lógica."""

    def test_categoria_invalida_es_rechazada(self):
        resp = self.client.post('/api/gyms/equipamiento/', {
            'nombre': 'Bicicleta', 'categoria': 'spinning', 'cantidad': 1,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cantidad_negativa_es_rechazada(self):
        resp = self.client.post('/api/gyms/equipamiento/', {
            'nombre': 'Costal', 'categoria': 'impacto', 'cantidad': -5,
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_equipo_desactivado_no_aparece(self):
        Equipamiento.objects.create(gym=self.gym, nombre='Vigente', categoria='cardio')
        Equipamiento.objects.create(gym=self.gym, nombre='De baja', categoria='cardio', activo=False)
        nombres = [e['nombre'] for e in self.client.get('/api/gyms/equipamiento/').data]
        self.assertIn('Vigente', nombres)
        self.assertNotIn('De baja', nombres)

    def test_registrar_ultima_revision(self):
        eq = Equipamiento.objects.create(gym=self.gym, nombre='Ring', categoria='infraestructura')
        hoy = date.today().isoformat()
        resp = self.client.patch(f'/api/gyms/equipamiento/{eq.id}/', {'ultima_revision': hoy})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        eq.refresh_from_db()
        self.assertEqual(eq.ultima_revision.isoformat(), hoy)

    def test_no_puede_editar_equipo_de_otro_gym(self):
        ajeno = Equipamiento.objects.create(gym=self.otro_gym, nombre='Ajeno', categoria='cardio')
        resp = self.client.patch(f'/api/gyms/equipamiento/{ajeno.id}/', {'cantidad': 99})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_gym_del_payload_es_ignorado(self):
        resp = self.client.post('/api/gyms/equipamiento/', {
            'nombre': 'Costal', 'categoria': 'impacto', 'cantidad': 1, 'gym': self.otro_gym.id,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(Equipamiento.objects.get(id=resp.data['id']).gym_id, self.gym.id)


class SucursalTests(BaseAPITestCase):
    """Las sucursales alimentan el selector del kiosco de check-in."""

    def test_crear_sucursal(self):
        resp = self.client.post('/api/gyms/sucursales/', {
            'gym': self.gym.id, 'nombre': 'Norte', 'direccion': 'Av. Siempre Viva 1',
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

    def test_sucursal_inactiva_no_aparece(self):
        from gyms.models import Sucursal
        Sucursal.objects.create(gym=self.gym, nombre='Cerrada', activa=False)
        nombres = [s['nombre'] for s in self.client.get('/api/gyms/sucursales/').data]
        self.assertIn('Centro', nombres)
        self.assertNotIn('Cerrada', nombres)

    def test_recepcion_no_puede_crear_sucursal(self):
        recepcion = Usuario.objects.create_user(
            email='recep@round3.com', password='Passw0rd1', nombre='Recep',
            rol='recepcion', gym=self.gym,
        )
        self.authenticate(recepcion)
        resp = self.client.post('/api/gyms/sucursales/', {
            'gym': self.gym.id, 'nombre': 'Pirata',
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
