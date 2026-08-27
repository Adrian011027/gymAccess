import os
import sys
from pathlib import Path
from datetime import timedelta

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(nombre, por_defecto):
    return os.environ.get(nombre, str(por_defecto)).lower() in ('1', 'true', 'yes', 'on')


DEBUG = _env_bool('DJANGO_DEBUG', True)

# En desarrollo se mantiene el valor de siempre; en el servidor hay que exportar
# DJANGO_SECRET_KEY, DJANGO_DEBUG=0 y DJANGO_ALLOWED_HOSTS con el dominio real.
#
# Con DEBUG=False no hay valor por defecto **a propósito**: antes, si la variable no
# se exportaba, el servidor arrancaba igual y firmaba los tokens con la llave de
# desarrollo, que está publicada en el repositorio y en el historial de git. Un
# arranque que falla se nota; uno que firma con una llave pública, no.
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-3-8#is1+(bm1kgw(axuj5d$g^#(_d&otj9w+au7n)zxv72csjm',
)
if not DEBUG and not os.environ.get('DJANGO_SECRET_KEY'):
    raise ImproperlyConfigured(
        'Falta DJANGO_SECRET_KEY. Genera una con:\n'
        '  python -c "from django.core.management.utils import get_random_secret_key; '
        'print(get_random_secret_key())"'
    )

ALLOWED_HOSTS = [h.strip() for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # third party
    'rest_framework',
    'rest_framework_simplejwt',
    # Hace revocable un refresh token. Ver el bloque SIMPLE_JWT.
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    # apps
    'usuarios',
    'gyms',
    'socios',
    'accesos',
    'notificaciones',
    'tienda',
    'legal',
    'saas',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'gymaccess.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'gymaccess.wsgi.application'

# --- Base de datos ------------------------------------------------------------
# Postgres si están las variables (el contenedor de docker-compose las inyecta);
# SQLite en su ausencia, para que un `manage.py test` o un clon recién bajado sigan
# funcionando sin levantar nada.
#
# Con DEBUG=False se EXIGE Postgres: SQLite es un archivo, y quien alcance el
# sistema de archivos del servidor —o un backup mal guardado— se lleva el padrón
# completo de socios y los hashes de contraseñas de todos los inquilinos. Además no
# aguanta varios kioscos escribiendo a la vez ('database is locked').
_db_name = os.environ.get('POSTGRES_DB')
if _db_name:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': _db_name,
            'USER': os.environ.get('POSTGRES_USER', 'gymaccess'),
            'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
            'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
            'PORT': os.environ.get('POSTGRES_PORT', '5432'),
            # Reusar conexiones evita pagar el handshake en cada request; 60 s es el
            # valor conservador que no deja conexiones colgadas si el worker muere.
            'CONN_MAX_AGE': 60,
        }
    }
elif DEBUG:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    raise ImproperlyConfigured(
        'Falta la configuración de Postgres (POSTGRES_DB, POSTGRES_USER, '
        'POSTGRES_PASSWORD, POSTGRES_HOST). SQLite no se usa en producción.'
    )

AUTH_USER_MODEL = 'usuarios.Usuario'

REST_FRAMEWORK = {
    # No es el JWTAuthentication de la librería: el nuestro además rechaza a los
    # usuarios de un gimnasio suspendido. Va en la autenticación y no en los
    # permisos porque varias vistas declaran `IsAuthenticated` explícito y eso
    # reemplaza al default en vez de sumarse. Ver usuarios/authentication.py.
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'usuarios.authentication.JWTUsuarioOperativo',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    # Rate limiting anti-DoS/fuerza bruta: límites por IP (anon) y por usuario
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/min',      # IPs sin autenticar
        'user': '300/min',     # usuarios autenticados (uso normal del dashboard)
        'login': '10/min',     # intentos de login por IP (anti fuerza bruta)
        'checkin': '60/min',   # kiosco de check-in
        # Verifica contraseñas de admin: se mantiene bajo a propósito para que no sirva
        # como banco de pruebas de fuerza bruta.
        'autorizacion': '5/min',
    },
}

SIMPLE_JWT = {
    # 8 h era demasiado para un token que no se puede revocar. Con la blacklist
    # activa, un access corto más un refresh largo dan la misma comodidad y acotan
    # la ventana de un token robado a una hora.
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.environ.get('JWT_ACCESS_MIN', 60))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    # La app `token_blacklist` (INSTALLED_APPS) es lo que hace posible invalidar un
    # refresh: antes no había forma de revocar nada, ni al dar de baja a un empleado
    # ni al cerrar una sesión de soporte.
    #
    # La ROTACIÓN queda APAGADA a propósito. Con rotación, cada refresh invalida al
    # anterior, y el frontend tiene un bug conocido —reintenta `POST /auth/refresh/`
    # ~15 veces en un segundo cuando el token vence, hasta dispararse su propio 429
    # (anotado en ESTADO_SESION_2026-08-21)—. Con rotación activa, el primer reintento
    # funcionaría y los otros catorce cerrarían la sesión del usuario. Se enciende
    # cuando ese bucle esté arreglado.
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
}

# Abierto en desarrollo; en producción se listan los orígenes reales en
# DJANGO_CORS_ORIGINS (separados por coma) y deja de aceptar cualquiera.
#
# Falla cerrado: el default inseguro estaba al revés —sin la variable, cualquier
# página web podía llamar a la API desde el navegador de un usuario con sesión
# abierta, y olvidar exportarla no daba ninguna señal—.
_cors_origins = [o.strip() for o in os.environ.get('DJANGO_CORS_ORIGINS', '').split(',') if o.strip()]
if _cors_origins:
    CORS_ALLOWED_ORIGINS = _cors_origins
    CORS_ALLOW_ALL_ORIGINS = False
elif DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    raise ImproperlyConfigured(
        'Falta DJANGO_CORS_ORIGINS con los orígenes del frontend, separados por coma '
        '(ej. https://gym.tudominio.com).'
    )

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 10}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# La suite crea y verifica cientos de contraseñas; con PBKDF2 real (~600k iteraciones)
# un solo módulo de 37 tests tardaba 205 s, que es lo que hace que nadie la corra.
# El hasher rápido solo aplica cuando el comando es `test`.
if 'test' in sys.argv:
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Solo se hace caso a X-Forwarded-For si hay un proxy de confianza delante que la
# reescriba (nginx, Cloudflare). Sin esto, el cliente elige qué IP queda en la
# evidencia de consentimiento y en la bitácora de soporte. Ver legal/views.py:ip_de.
USAR_X_FORWARDED_FOR = _env_bool('DJANGO_TRAS_PROXY', False)

# --- Endurecimiento para producción -------------------------------------------
# Detrás de nginx/Cloudflare Django ve http en REMOTE_ADDR y sin esta cabecera
# creería que la conexión no es segura, entrando en un bucle de redirección.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = _env_bool('DJANGO_SSL_REDIRECT', True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    CSRF_TRUSTED_ORIGINS = _cors_origins

LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
# Donde `collectstatic` deja los archivos para que los sirva nginx. Con `runserver`
# nunca hizo falta —Django los sirve solo en desarrollo— y por eso no estaba.
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
