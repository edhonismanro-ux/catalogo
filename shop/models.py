from django.conf import settings
from django.db import models
from django.utils import timezone
import uuid


class Product(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


def _new_order_code() -> str:
    # Código corto tipo: DANI-4F8A2C
    return "DANI-" + uuid.uuid4().hex[:6].upper()


class Address(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField("Etiqueta", max_length=60, default="Casa")  # Casa / Trabajo / etc.
    full_name = models.CharField("Nombre completo", max_length=120)
    whatsapp = models.CharField("WhatsApp", max_length=30)
    address = models.CharField("Dirección", max_length=180)
    reference = models.CharField("Referencia", max_length=180, blank=True, null=True)
    notes = models.TextField("Notas", blank=True, null=True)
    is_default = models.BooleanField("Predeterminada", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.label} - {self.full_name}"


class Order(models.Model):
    STATUS_CHOICES = [
        ("new", "Nuevo"),
        ("confirmed", "Confirmado"),
        ("preparing", "Preparando"),
        ("on_the_way", "En camino"),
        ("delivered", "Entregado"),
        ("cancelled", "Cancelado"),
    ]

    PAYMENT_CHOICES = [
        ("unpaid", "Sin pago"),
        ("pending_review", "Comprobante en revisión"),
        ("paid", "Pagado"),
    ]

    code = models.CharField(max_length=20, unique=True, default=_new_order_code, editable=False)

    # ✅ Login opcional: si el cliente está logueado, guardas su user
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders"
    )

    full_name = models.CharField("Nombre completo", max_length=120, default="")
    whatsapp = models.CharField("WhatsApp", max_length=30, default="")

    # ✅ delivery por coordinación
    address = models.CharField("Dirección", max_length=180, blank=True, null=True)
    reference = models.CharField("Referencia", max_length=180, blank=True, null=True)
    notes = models.TextField("Notas", blank=True, null=True)

    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")

    payment_status = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default="unpaid")
    paid_at = models.DateTimeField("Pagado el", blank=True, null=True)

    receipt_image = models.ImageField("Comprobante", upload_to="receipts/", blank=True, null=True)
    receipt_uploaded_at = models.DateTimeField(blank=True, null=True)

    # ✅ Culqi (para QR con monto automático + webhook)
    culqi_order_id = models.CharField(max_length=60, blank=True, null=True, unique=True)
    culqi_last_state = models.CharField(max_length=30, blank=True, default="")
    culqi_last_event_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.full_name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.PositiveIntegerField(default=1)

    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.product.name} x{self.qty}"
