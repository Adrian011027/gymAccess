"""Horario de atención del gym con descansos (cierres parciales dentro del turno).

Se guarda en un JSONField, que acepta cualquier estructura: si el serializer no
valida, un descanso invertido o fuera del turno queda persistido y la pantalla
muestra después un horario imposible sin rastro de dónde salió.
"""

from rest_framework import status

from gyms.tests import BaseAPITestCase


def dia(inicio='06:00', fin='22:00', descansos=None):
    return {'abierto': True, 'inicio': inicio, 'fin': fin, 'descansos': descansos or []}


class HorarioGymTests(BaseAPITestCase):
    def patch_horario(self, horario):
        return self.client.patch(
            f'/api/gyms/{self.gym.id}/', {'horario': horario}, format='json',
        )

    def test_guarda_horario_con_descanso(self):
        resp = self.patch_horario({'lun': dia(descansos=[{'inicio': '13:00', 'fin': '15:00'}])})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.gym.refresh_from_db()
        self.assertEqual(
            self.gym.horario['lun']['descansos'], [{'inicio': '13:00', 'fin': '15:00'}],
        )

    def test_dia_cerrado_no_exige_horas(self):
        resp = self.patch_horario({'dom': {'abierto': False}})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.gym.refresh_from_db()
        self.assertEqual(self.gym.horario['dom'], {'abierto': False})

    def test_rechaza_dia_invalido(self):
        self.assertEqual(
            self.patch_horario({'lunes': dia()}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_rechaza_apertura_posterior_al_cierre(self):
        self.assertEqual(
            self.patch_horario({'lun': dia('22:00', '06:00')}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_rechaza_descanso_invertido(self):
        resp = self.patch_horario({'lun': dia(descansos=[{'inicio': '15:00', 'fin': '13:00'}])})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rechaza_descanso_fuera_del_turno(self):
        """Un cierre a las 23:00 en un turno que acaba a las 22:00 no significa nada."""
        resp = self.patch_horario({'lun': dia(descansos=[{'inicio': '23:00', 'fin': '23:30'}])})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rechaza_descansos_encimados(self):
        resp = self.patch_horario({'lun': dia(descansos=[
            {'inicio': '13:00', 'fin': '15:00'},
            {'inicio': '14:00', 'fin': '16:00'},
        ])})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_ordena_los_descansos(self):
        """Se guardan ordenados para que la comparación de días y el texto de la
        pantalla no dependan de en qué orden los capturó recepción."""
        resp = self.patch_horario({'lun': dia(descansos=[
            {'inicio': '17:00', 'fin': '18:00'},
            {'inicio': '13:00', 'fin': '15:00'},
        ])})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.gym.refresh_from_db()
        self.assertEqual(
            [d['inicio'] for d in self.gym.horario['lun']['descansos']], ['13:00', '17:00'],
        )

    def test_rechaza_hora_con_formato_invalido(self):
        self.assertEqual(
            self.patch_horario({'lun': dia('25:99', '22:00')}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
