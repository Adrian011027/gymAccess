from django.contrib import admin

from .models import Producto, StockSucursal, Venta, VentaItem


class VentaItemInline(admin.TabularInline):
    model = VentaItem
    extra = 0
    readonly_fields = ['producto', 'cantidad', 'precio_unitario', 'subtotal']


class StockSucursalInline(admin.TabularInline):
    model = StockSucursal
    extra = 0


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'categoria', 'precio', 'stock_total', 'gym', 'activo']
    list_filter = ['gym', 'categoria', 'activo']
    search_fields = ['nombre']
    inlines = [StockSucursalInline]


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ['id', 'fecha', 'total', 'metodo', 'sucursal', 'vendido_por']
    list_filter = ['gym', 'metodo']
    inlines = [VentaItemInline]
