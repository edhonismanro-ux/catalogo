from django.contrib import admin
from .models import Product, Order, OrderItem, Address


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "stock", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    list_editable = ("price", "stock", "is_active")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "qty", "unit_price", "subtotal")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("code", "full_name", "whatsapp", "total", "status", "payment_status", "created_at", "has_receipt")
    list_filter = ("status", "payment_status", "created_at")
    search_fields = ("code", "full_name", "whatsapp")
    readonly_fields = ("code", "total", "created_at", "receipt_uploaded_at")
    inlines = [OrderItemInline]

    actions = ["mark_paid", "mark_pending_review", "mark_confirmed", "mark_on_the_way", "mark_delivered", "mark_cancelled"]

    def has_receipt(self, obj):
        return "✅" if obj.receipt_image else "—"
    has_receipt.short_description = "Comprobante"

    @admin.action(description="Marcar como PAGADO")
    def mark_paid(self, request, queryset):
        queryset.update(payment_status="paid")

    @admin.action(description="Marcar como COMPROBANTE EN REVISIÓN")
    def mark_pending_review(self, request, queryset):
        queryset.update(payment_status="pending_review")

    @admin.action(description="Estado: Confirmado")
    def mark_confirmed(self, request, queryset):
        queryset.update(status="confirmed")

    @admin.action(description="Estado: En camino")
    def mark_on_the_way(self, request, queryset):
        queryset.update(status="on_the_way")

    @admin.action(description="Estado: Entregado")
    def mark_delivered(self, request, queryset):
        queryset.update(status="delivered")

    @admin.action(description="Estado: Cancelado")
    def mark_cancelled(self, request, queryset):
        queryset.update(status="cancelled")


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "full_name", "whatsapp", "is_default", "created_at")
    list_filter = ("is_default", "created_at")
    search_fields = ("label", "full_name", "whatsapp", "address", "reference")
