from .settings import *  # noqa

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Hasher barato SOLO para tests. Con PBKDF2 (el de producción) cada create_user cuesta
# ~1M de iteraciones y la suite tardaba 412s; una suite de regresión que tarda 7 minutos
# no se corre en cada cambio, que es justamente para lo que existe.
# Producción no se toca: este módulo solo se carga vía DJANGO_SETTINGS_MODULE en tests.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
