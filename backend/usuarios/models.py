from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UsuarioManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError('Email requerido')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault('rol', 'superadmin')
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin):
    ROL_CHOICES = [
        ('superadmin', 'Super Admin'),
        ('admin', 'Admin Gym'),
        ('recepcion', 'Recepción'),
        ('coach', 'Coach'),
    ]

    email = models.EmailField(unique=True)
    nombre = models.CharField(max_length=150)
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default='recepcion')
    gym = models.ForeignKey(
        'gyms.Gym', on_delete=models.CASCADE,
        null=True, blank=True, related_name='usuarios'
    )
    # Nulo = ve todo el gym (el dueño). Asignada = solo opera esa sucursal.
    # Nulo es el default para no romper a los usuarios que ya existen, pero la UI
    # obliga a elegir sucursal al dar de alta a recepción.
    #
    # Es la sucursal ACTIVA de la sesión, no el total de sucursales donde puede
    # trabajar (eso es `sucursales_permitidas`). Todo el scoping (usuarios/scoping.py
    # y los ViewSets que lo usan) sigue leyendo este campo tal cual: cambiar de
    # sucursal activa = reasignar este FK, no tocar el scoping.
    sucursal = models.ForeignKey(
        'gyms.Sucursal', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='usuarios'
    )
    # Conjunto de sucursales entre las que puede elegir al hacer login (recepción
    # que rota de local según el día). Vacío = sin restricción explícita (típico
    # del admin, que de todos modos no usa este flujo).
    sucursales_permitidas = models.ManyToManyField(
        'gyms.Sucursal', blank=True, related_name='usuarios_permitidos'
    )
    # Horario semanal informativo: {"lunes": <sucursal_id|None>, ..., "domingo": ...}.
    # No se valida contra accesos ni bloquea nada, es solo para que el admin lo consulte.
    horario_semanal = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    objects = UsuarioManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nombre']

    class Meta:
        db_table = 'usuarios'

    def __str__(self):
        return f'{self.nombre} ({self.email})'
