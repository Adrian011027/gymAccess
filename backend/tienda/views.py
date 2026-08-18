from django.db.models import Count, DecimalField, F, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from gyms.models import Sucursal
from usuarios.permissions import AdminOSoloLectura
from usuarios.scoping import SucursalScopedMixin
from .models import Producto, StockSucursal, Venta, VentaItem
from .serializers import (
    AjusteStockSerializer, ProductoSerializer, StockSucursalSerializer,
    VentaCreateSerializer, VentaSerializer,
)


class ProductoViewSet(SucursalScopedMixin, viewsets.ModelViewSet):
    """Catálogo. Recepción necesita leerlo para cobrar, pero no toca precios ni stock.

    El catálogo NO se acota por sucursal: el producto y su precio son del negocio. Lo
    que cambia por local son las existencias, que viven en StockSucursal.
    """

    serializer_class = ProductoSerializer
    permission_classes = [permissions.IsAuthenticated, AdminOSoloLectura]

    def get_queryset(self):
        return Producto.objects.filter(
            gym_id=self.request.user.gym_id, activo=True,
        ).prefetch_related('stocks__sucursal')

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        # Qué sucursal manda al leer `stock`: la del usuario, o la que pida el dueño.
        ctx['sucursal_id'] = self.sucursal_id or self.sucursal_solicitada()
        return ctx

    def perform_create(self, serializer):
        gym_id = self.request.user.gym_id
        stock_inicial = serializer.validated_data.pop('stock_inicial', 0)
        producto = serializer.save(gym_id=gym_id)

        # Un producto nuevo existe en todas las sucursales, aunque sea con cero piezas:
        # así aparece en el catálogo de cada caja y se le puede cargar inventario.
        contexto = self.sucursal_id or self.sucursal_solicitada()
        for sucursal in Sucursal.objects.filter(gym_id=gym_id, activa=True):
            StockSucursal.objects.create(
                producto=producto,
                sucursal=sucursal,
                cantidad=stock_inicial if sucursal.id == contexto else 0,
            )

    def perform_destroy(self, instance):
        # Baja lógica: VentaItem apunta al producto con PROTECT y el histórico lo necesita.
        instance.activo = False
        instance.save(update_fields=['activo'])

    @action(detail=True, methods=['post'], url_path='stock')
    def ajustar_stock(self, request, pk=None):
        """Fija las existencias de una sucursal. Solo admin (AdminOSoloLectura ya lo exige)."""
        producto = self.get_object()
        entrada = AjusteStockSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data

        sucursal_id = datos.get('sucursal') or self.sucursal_id
        if sucursal_id is None:
            raise ValidationError({'sucursal': 'Indica la sucursal cuyo stock ajustas.'})
        if not Sucursal.objects.filter(
            id=sucursal_id, gym_id=request.user.gym_id,
        ).exists():
            raise ValidationError({'sucursal': 'Sucursal no encontrada.'})
        self.validar_escritura_id(sucursal_id)

        fila, _ = StockSucursal.objects.get_or_create(
            producto=producto, sucursal_id=sucursal_id,
        )
        if datos.get('cantidad') is not None:
            fila.cantidad = datos['cantidad']
        if datos.get('stock_minimo') is not None:
            fila.stock_minimo = datos['stock_minimo']
        fila.save()
        return Response(StockSucursalSerializer(fila).data)


class VentaViewSet(SucursalScopedMixin,
                   mixins.CreateModelMixin,
                   mixins.ListModelMixin,
                   mixins.RetrieveModelMixin,
                   viewsets.GenericViewSet):
    """Sin update ni delete a propósito: una venta cobrada es un hecho contable.
    Corregir se hará con una devolución cuando exista, no editando el histórico."""

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.scope_sucursal(
            Venta.objects.filter(gym_id=self.request.user.gym_id)
        ).select_related('sucursal', 'vendido_por').prefetch_related('items__producto')

    def get_serializer_class(self):
        return VentaCreateSerializer if self.action == 'create' else VentaSerializer

    @action(detail=False, methods=['get'])
    def resumen(self, request):
        """Números de tienda para Reportes: van como línea aparte de las membresías."""
        qs = self.get_queryset()
        hoy = timezone.localdate()
        inicio_mes = hoy.replace(day=1)

        cero = Coalesce(Sum('total'), 0, output_field=DecimalField(max_digits=12, decimal_places=2))
        # El resumen se acota igual que la lista: recepción ve el corte de su caja,
        # no el del negocio entero.
        items = VentaItem.objects.filter(venta__in=qs)

        costo = items.aggregate(
            c=Coalesce(
                Sum(F('cantidad') * F('producto__costo'), output_field=DecimalField(max_digits=12, decimal_places=2)),
                0,
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )['c']
        vendido = qs.aggregate(t=cero)['t']

        return Response({
            'total_ventas': vendido,
            'costo_mercancia': costo,
            'margen': vendido - costo,
            'ventas_hoy': qs.filter(fecha__date=hoy).aggregate(t=cero)['t'],
            'ventas_mes': qs.filter(fecha__date__gte=inicio_mes).aggregate(t=cero)['t'],
            'num_ventas': qs.count(),
            'por_metodo': list(qs.values('metodo').annotate(n=Count('id'), total=Sum('total'))),
            'top_productos': list(
                items.values('producto__nombre')
                .annotate(unidades=Sum('cantidad'), total=Sum('subtotal'))
                .order_by('-unidades')[:5]
            ),
        })
