"""Aviso de privacidad de un gym a partir de la plantilla común.

El texto es el mismo para todos los gyms; lo que cambia es quién responde por los
datos (razón social, domicilio y contacto), que la LFPDPPP exige que el aviso diga.
Por eso se genera con los datos de cada gym en lugar de que cada dueño lo redacte.

Lo que se publica es el texto YA LLENO, guardado como `DocumentoLegal`. No se llena
al vuelo al mostrarlo: cada consentimiento apunta a una versión concreta, y si el
gym cambiara de domicilio el socio "habría aceptado" un texto que nunca vio. Un
cambio de datos es una versión nueva.

La plantilla vive dentro de `backend/` y no en `legal/` de la raíz porque la imagen
de Docker solo copia `backend/`: desde ahí no llegaría al servidor.
"""

import re
from pathlib import Path

from django.utils import timezone

PLANTILLA = Path(__file__).resolve().parent / 'plantillas' / 'aviso_privacidad.md'

# Lo que el aviso no puede omitir. `nombre` no está porque el gym siempre lo tiene.
CAMPOS_DEL_GYM = (
    ('razon_social', 'Razón social'),
    ('direccion', 'Dirección'),
    ('telefono', 'Teléfono'),
    ('email_contacto', 'Correo de contacto'),
)


def _una_linea(valor):
    # La dirección se captura en un textarea. Un salto de línea en blanco en medio de
    # `**...**` parte el párrafo y el Markdown deja los asteriscos sueltos a la vista.
    return ' '.join(str(valor or '').split())


def datos_faltantes(gym):
    return [
        {'campo': campo, 'etiqueta': etiqueta}
        for campo, etiqueta in CAMPOS_DEL_GYM
        if not _una_linea(getattr(gym, campo, ''))
    ]


def version_sugerida(gym):
    """La siguiente versión libre: 1.0 para el primer aviso, luego 2.0, 3.0…"""
    from .models import DocumentoLegal
    usadas = set(
        DocumentoLegal.objects
        .filter(gym=gym, tipo=DocumentoLegal.AVISO_PRIVACIDAD)
        .values_list('version', flat=True)
    )
    n = len(usadas) + 1
    while f'{n}.0' in usadas:
        n += 1
    return f'{n}.0'


def generar_aviso(gym, version, fecha=None):
    fecha = fecha or timezone.localdate()
    valores = {
        'nombre': _una_linea(gym.nombre),
        'razon_social': _una_linea(gym.razon_social),
        'direccion': _una_linea(gym.direccion),
        'telefono': _una_linea(gym.telefono),
        'email_contacto': _una_linea(gym.email_contacto),
        'version': version,
        'fecha': fecha.strftime('%d/%m/%Y'),
    }
    texto = PLANTILLA.read_text(encoding='utf-8')
    # Una variable que la plantilla use y aquí no exista revienta con KeyError a
    # propósito: publicar "{{algo}}" literal ante un socio sería peor que un error.
    return re.sub(r'\{\{\s*(\w+)\s*\}\}', lambda m: valores[m.group(1)], texto)
