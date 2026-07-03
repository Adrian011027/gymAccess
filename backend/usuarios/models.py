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
