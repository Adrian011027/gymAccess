"""Cómo se arma el enlace del QR que se le manda al socio.

Vive aparte porque lo usan tres sitios (el serializer de socios, el de métodos de
acceso y la propia página del QR) y la regla tiene que ser una sola: si cada uno
llamara a `build_absolute_uri` por su cuenta, bastaría con que uno se quedara sin
actualizar para que el socio recibiera un enlace roto y nadie supiera por qué.
"""

from django.conf import settings
from django.urls import reverse


def url_qr(request, token, nombre='qr-pagina'):
    """URL absoluta del QR de un socio, apta para mandar por chat.

    Por defecto sale del host de la petición, que es lo correcto detrás de un nginx
    bien configurado. `QR_BASE_URL` la fuerza a un dominio fijo, y existe por un
    desajuste que no se ve hasta que el socio recibe el mensaje: **el enlace lo genera
    la petición de recepción, pero lo abre el teléfono del socio**. Si recepción entra
    por `localhost` —o por la IP privada del gym—, `build_absolute_uri` devuelve esa
    misma dirección, que en el teléfono del socio no lleva a ninguna parte.

    Devuelve None si no hay ni base configurada ni petición de la que sacar el host.
    """
    ruta = reverse(nombre, kwargs={'token': token})
    if settings.QR_BASE_URL:
        return f'{settings.QR_BASE_URL}{ruta}'
    if request is None:
        return None
    return request.build_absolute_uri(ruta)
