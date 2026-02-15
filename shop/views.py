from decimal import Decimal
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt

from django.http import HttpRequest
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.conf import settings
import time
import json
import base64
import requests
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from .models import Product, Order, OrderItem, Address
from .forms import CheckoutForm, ReceiptUploadForm, AddressForm

DANIELA_WSP = "51944739301"


# -------------------
# Helpers carrito
# -------------------
def _get_cart(request):
    return request.session.get("cart", {})

def _save_cart(request, cart):
    request.session["cart"] = cart
    request.session.modified = True

def _cart_count(cart):
    return sum(int(q) for q in cart.values())


# -------------------
# ✅ Acceso seguro a pedidos
# -------------------
def _grant_order_access(request, code: str):
    """
    Para usuarios sin login: si validan código + whatsapp,
    guardamos el code en sesión para permitir ver detalle.
    """
    codes = request.session.get("order_access", [])
    code = (code or "").upper().strip()
    if code and code not in codes:
        codes.append(code)
        request.session["order_access"] = codes
        request.session.modified = True

def _can_view_order(request, order: Order) -> bool:
    # Si el pedido tiene user asignado: solo el dueño lo ve estando logueado
    if getattr(order, "user_id", None):
        return request.user.is_authenticated and (order.user_id == request.user.id)

    # Si no tiene user (pedido “invitado”): permitir si el code está en sesión
    codes = request.session.get("order_access", [])
    return order.code in codes


# -------------------
# Catálogo
# -------------------
def product_list(request):
    qs = Product.objects.filter(is_active=True)

    q = request.GET.get("q", "").strip()
    order = request.GET.get("order", "new")
    minp = request.GET.get("min", "").strip()
    maxp = request.GET.get("max", "").strip()

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))

    try:
        if minp:
            qs = qs.filter(price__gte=minp)
    except Exception:
        pass

    try:
        if maxp:
            qs = qs.filter(price__lte=maxp)
    except Exception:
        pass

    if order == "price_asc":
        qs = qs.order_by("price")
    elif order == "price_desc":
        qs = qs.order_by("-price")
    else:
        qs = qs.order_by("-created_at")

    cart = _get_cart(request)
    return render(request, "shop/product_list.html", {
        "products": qs,
        "cart_count": _cart_count(cart),
        "q": q,
        "order": order,
        "minp": minp,
        "maxp": maxp,
        "daniela_wsp": DANIELA_WSP,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    cart = _get_cart(request)
    return render(request, "shop/product_detail.html", {
        "product": product,
        "cart_count": _cart_count(cart),
        "daniela_wsp": DANIELA_WSP,
    })


# -------------------
# Carrito
# -------------------
def cart_add(request: HttpRequest, pk: int):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    cart = _get_cart(request)
    pid = str(product.id)

    qty = int(cart.get(pid, 0)) + 1
    if qty > product.stock:
        qty = product.stock

    if qty <= 0:
        cart.pop(pid, None)
        messages.warning(request, "Producto sin stock.")
    else:
        cart[pid] = qty
        messages.success(request, f"✅ Agregado: {product.name}")

    _save_cart(request, cart)
    return redirect(request.META.get("HTTP_REFERER", "product_list"))


def cart_decrease(request, pk):
    cart = _get_cart(request)
    pid = str(pk)
    if pid in cart:
        qty = int(cart[pid]) - 1
        if qty <= 0:
            cart.pop(pid, None)
        else:
            cart[pid] = qty
        _save_cart(request, cart)
    return redirect("cart_detail")


def cart_remove(request, pk):
    cart = _get_cart(request)
    cart.pop(str(pk), None)
    _save_cart(request, cart)
    return redirect("cart_detail")


def cart_clear(request):
    _save_cart(request, {})
    return redirect("cart_detail")


def cart_detail(request):
    cart = _get_cart(request)
    ids = [int(i) for i in cart.keys()] if cart else []
    products = Product.objects.filter(id__in=ids, is_active=True)

    items = []
    total = Decimal("0.00")
    by_id = {p.id: p for p in products}

    for pid_str, qty in cart.items():
        pid = int(pid_str)
        product = by_id.get(pid)
        if not product:
            continue
        qty = int(qty)
        subtotal = product.price * qty
        total += subtotal
        items.append({"product": product, "qty": qty, "subtotal": subtotal})

    return render(request, "shop/cart.html", {
        "items": items,
        "total": total,
        "cart_count": _cart_count(cart),
        "daniela_wsp": DANIELA_WSP,
    })


# -------------------
# ✅ Checkout (crea pedido y lo vincula si hay login)
# -------------------
def checkout(request):
    cart = _get_cart(request)
    if not cart:
        messages.info(request, "Tu carrito está vacío.")
        return redirect("product_list")

    ids = [int(i) for i in cart.keys()]
    products = Product.objects.filter(id__in=ids, is_active=True)
    by_id = {p.id: p for p in products}

    items = []
    total = Decimal("0.00")

    for pid_str, qty in cart.items():
        pid = int(pid_str)
        product = by_id.get(pid)
        if not product:
            continue
        qty = int(qty)
        if qty > product.stock:
            qty = product.stock
        subtotal = product.price * qty
        total += subtotal
        items.append({"product": product, "qty": qty, "subtotal": subtotal})

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)

            # ✅ si está logueado, el pedido queda “de su cuenta”
            if request.user.is_authenticated:
                order.user = request.user

            order.total = total
            order.status = "new"
            order.payment_status = getattr(order, "payment_status", "unpaid")  # por si existe
            order.save()

            for it in items:
                p = it["product"]
                q = int(it["qty"])
                OrderItem.objects.create(
                    order=order,
                    product=p,
                    qty=q,
                    unit_price=p.price,
                    subtotal=p.price * q,
                )

            _save_cart(request, {})

            # ✅ si es invitado, darle acceso por sesión al detalle (sin pedir code)
            _grant_order_access(request, order.code)

            messages.success(request, f"✅ Pedido {order.code} creado.")
            return redirect("order_detail_code", code=order.code)

        messages.error(request, "Revisa los datos del formulario.")
    else:
        form = CheckoutForm()

    return render(request, "shop/checkout.html", {
        "form": form,
        "items": items,
        "total": total,
        "cart_count": _cart_count(cart),
        "daniela_wsp": DANIELA_WSP,
        "show_qr": True,
    })


# -------------------
# ✅ Detalle pedido por código (protegido)
# -------------------
def order_detail(request, code: str):
    order = get_object_or_404(Order, code=code.upper().strip())

    if not _can_view_order(request, order):
        messages.error(request, "Este pedido no te pertenece o no está autorizado.")
        return redirect("track_order")

    items = order.items.select_related("product").all()
    upload_form = ReceiptUploadForm(instance=order)

    return render(request, "shop/order_detail.html", {
    "order": order,
    "items": items,
    "upload_form": upload_form,
    "cart_count": _cart_count(_get_cart(request)),
    "daniela_wsp": DANIELA_WSP,
    "show_qr": True,
    "CULQI_PUBLIC_KEY": settings.CULQI_PUBLIC_KEY,
    "CULQI_RSA_ID": settings.CULQI_RSA_ID,
    "CULQI_RSA_PUBLIC_KEY": settings.CULQI_RSA_PUBLIC_KEY,
})

# alias para tu URL actual
def order_detail_code(request, code):
    return order_detail(request, code)


def upload_receipt(request, code: str):
    order = get_object_or_404(Order, code=code.upper().strip())

    if not _can_view_order(request, order):
        messages.error(request, "No autorizado.")
        return redirect("track_order")

    if request.method != "POST":
        return redirect("order_detail_code", code=order.code)

    form = ReceiptUploadForm(request.POST, request.FILES, instance=order)
    if form.is_valid():
        form.save()
        order.payment_status = "pending_review"
        order.receipt_uploaded_at = timezone.now()
        order.save(update_fields=["payment_status", "receipt_uploaded_at"])
        messages.success(request, "✅ Comprobante subido. Queda en revisión.")
    else:
        messages.error(request, "No se pudo subir el comprobante. Intenta con otra imagen.")

    return redirect("order_detail_code", code=order.code)


# -------------------
# ✅ Mis pedidos (panel por login)
# -------------------
@login_required
def my_orders(request):
    orders = (
        Order.objects
        .filter(user=request.user)
        .order_by("-created_at")
        .prefetch_related("items", "items__product")
    )
    return render(request, "shop/my_orders.html", {
        "orders": orders,
        "cart_count": _cart_count(_get_cart(request)),
        "daniela_wsp": DANIELA_WSP,
    })


# -------------------
# ✅ Mis pedidos sin login: tracking por código + WhatsApp
# -------------------
def track_order(request):
    # ✅ si está logueado, NO pedir código: llévalo a su panel
    if request.user.is_authenticated:
        return redirect("my_orders")

    cart = _get_cart(request)

    if request.method == "POST":
        code = request.POST.get("code", "").strip().upper()
        wsp = request.POST.get("whatsapp", "").strip()
        order = Order.objects.filter(code=code, whatsapp=wsp).first()

        if order:
            _grant_order_access(request, order.code)
            return redirect("order_detail_code", code=order.code)

        messages.error(request, "No encontramos ese pedido. Verifica código y WhatsApp.")

    return render(request, "shop/track_order.html", {
        "cart_count": _cart_count(cart),
        "daniela_wsp": DANIELA_WSP,
    })


# -------------------
# Extras
# -------------------
def home(request):
    cart = _get_cart(request)
    featured = Product.objects.filter(is_active=True).order_by("-created_at")[:6]
    return render(request, "shop/home.html", {
        "featured": featured,
        "cart_count": _cart_count(cart),
        "daniela_wsp": DANIELA_WSP,
    })

def about(request):
    cart = _get_cart(request)
    return render(request, "shop/about.html", {"cart_count": _cart_count(cart), "daniela_wsp": DANIELA_WSP})

def contact(request):
    cart = _get_cart(request)
    return render(request, "shop/contact.html", {"cart_count": _cart_count(cart), "daniela_wsp": DANIELA_WSP})

@require_POST
def culqi_create_order(request, code: str):
    """
    Crea una ORDEN en Culqi para pagar con QR (billeteras).
    Devuelve order_id y amount (en céntimos).
    """
    order = get_object_or_404(Order, code=code.upper().strip())

    # Seguridad: respeta tu regla de acceso
    if not _can_view_order(request, order):
        return JsonResponse({"ok": False, "msg": "No autorizado"}, status=403)

    # Culqi usa amount en céntimos
    amount = int(Decimal(order.total) * 100)

    # Datos cliente
    full_name = (getattr(order, "full_name", "") or "").strip() or "Cliente"
    parts = full_name.split(" ", 1)
    first_name = parts[0][:50]
    last_name = (parts[1] if len(parts) > 1 else "")[:50]

    phone = (getattr(order, "whatsapp", "") or "").strip()
    # Culqi suele esperar +51XXXXXXXXX
    if phone and not phone.startswith("+"):
        if phone.startswith("51"):
            phone = "+" + phone
        else:
            phone = "+51" + phone

    payload = {
        "amount": amount,
        "currency_code": "PEN",
        "description": f"Pedido {order.code}",
        "order_number": order.code,
        "client_details": {
            "first_name": first_name or "Cliente",
            "last_name": last_name,
            "email": "cliente@correo.com",   # si tienes order.email, reemplázalo aquí
            "phone_number": phone or "+51999999999",
        },
        # Expira en 1 hora
        "expiration_date": int(time.time()) + 3600,
    }

    r = requests.post(
        "https://api.culqi.com/v2/orders",
        json=payload,
        headers={
            "Authorization": f"Bearer {settings.CULQI_SECRET_KEY}",
            "Content-Type": "application/json",
        },
        timeout=20,
    )

    data = r.json() if r.content else {}
    if r.status_code >= 400:
        return JsonResponse({"ok": False, "culqi": data}, status=400)

    return JsonResponse({"ok": True, "order_id": data.get("id"), "amount": amount})

def _basic_auth_ok(request) -> bool:
    """
    Si defines CULQI_WEBHOOK_USER y CULQI_WEBHOOK_PASS en env,
    el webhook exigirá Basic Auth.
    (Útil si activas 'Activar autenticación' en CulqiPanel.) :contentReference[oaicite:2]{index=2}
    """
    user = os.environ.get("CULQI_WEBHOOK_USER", "").strip()
    pwd = os.environ.get("CULQI_WEBHOOK_PASS", "").strip()
    if not user or not pwd:
        return True  # no exigir auth

    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth.startswith("Basic "):
        return False

    try:
        raw = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
        u, p = raw.split(":", 1)
        return u == user and p == pwd
    except Exception:
        return False


@require_POST
def culqi_create_order(request, code: str):
    """
    Crea una ORDEN en Culqi y guarda culqi_order_id en tu Order.
    """
    order = get_object_or_404(Order, code=code.upper().strip())

    # Respeta tu regla de acceso (dueño o sesión invitado)
    if not _can_view_order(request, order):
        return JsonResponse({"ok": False, "msg": "No autorizado"}, status=403)

    amount = int(Decimal(order.total) * 100)  # céntimos

    full_name = (order.full_name or "Cliente").strip()
    parts = full_name.split(" ", 1)
    first_name = (parts[0] if parts else "Cliente")[:50]
    last_name = (parts[1] if len(parts) > 1 else "")[:50]

    phone = (order.whatsapp or "").strip()
    if phone and not phone.startswith("+"):
        if phone.startswith("51"):
            phone = "+" + phone
        else:
            phone = "+51" + phone

    payload = {
        "amount": amount,
        "currency_code": "PEN",
        "description": f"Pedido {order.code}",
        "order_number": order.code,
        "client_details": {
            "first_name": first_name or "Cliente",
            "last_name": last_name,
            "email": "cliente@correo.com",  # si luego agregas email al Order, lo pones aquí
            "phone_number": phone or "+51999999999",
        },
        "expiration_date": int(time.time()) + 3600,  # 1 hora
    }

    r = requests.post(
        "https://api.culqi.com/v2/orders",
        json=payload,
        headers={
            "Authorization": f"Bearer {settings.CULQI_SECRET_KEY}",
            "Content-Type": "application/json",
        },
        timeout=20,
    )

    data = r.json() if r.content else {}
    if r.status_code >= 400:
        return JsonResponse({"ok": False, "culqi": data}, status=400)

    culqi_order_id = data.get("id")
    if culqi_order_id:
        # Guardar el id Culqi para luego matchear webhook
        if order.culqi_order_id != culqi_order_id:
            order.culqi_order_id = culqi_order_id
            order.save(update_fields=["culqi_order_id"])

    return JsonResponse({"ok": True, "order_id": culqi_order_id, "amount": amount})


@csrf_exempt
def culqi_webhook(request):
    """
    Webhook: evento order.status.changed para marcar Order como pagado. :contentReference[oaicite:3]{index=3}
    """
    if request.method != "POST":
        return HttpResponse(status=405)

    # (Opcional) Basic Auth si activas autenticación en CulqiPanel
    if not _basic_auth_ok(request):
        return HttpResponse("Unauthorized", status=401)

    try:
        raw_body = request.body.decode("utf-8")
        evt = json.loads(raw_body) if raw_body else {}
    except Exception:
        return HttpResponse("Bad JSON", status=400)

    # Estructura típica: object=event, type=order.status.changed, data=... :contentReference[oaicite:4]{index=4}
    event_type = evt.get("type") or ""
    if event_type != "order.status.changed":
        # responder 200 para que Culqi no reintente por eventos que no nos importan
        return HttpResponse("ignored", status=200)

    data = evt.get("data")

    # A veces 'data' viene como string JSON (muchos plugins lo tratan así),
    # y a veces como dict. Soportamos ambos.
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            data = {}

    if not isinstance(data, dict):
        data = {}

    # estado de la orden (paid / expired / canceled / etc)
    state = (data.get("state") or "").strip().lower()

    # Identificadores posibles
    culqi_order_id = (data.get("id") or "").strip()  # id de la orden Culqi
    order_number = (data.get("order_number") or data.get("orderNumber") or "").strip()  # tu code si Culqi lo envía

    order = None

    # 1) Primero: buscar por culqi_order_id (lo guardamos al crear orden)
    if culqi_order_id:
        order = Order.objects.filter(culqi_order_id=culqi_order_id).first()

    # 2) Si no encontró: buscar por code = order_number (si viene)
    if not order and order_number:
        order = Order.objects.filter(code=order_number.upper()).first()

    if not order:
        # No rompemos (Culqi reintenta si no respondes 200)
        return HttpResponse("order_not_found", status=200)

    # Guardamos último estado recibido
    order.culqi_last_state = state
    order.culqi_last_event_at = timezone.now()

    # ✅ Si Culqi confirma pagado, marcamos pagado local
    if state == "paid":
        if order.payment_status != "paid":
            order.payment_status = "paid"
            order.paid_at = timezone.now()
            # opcional: si quieres que el status cambie también:
            # order.status = "confirmed"
            order.save(update_fields=["payment_status", "paid_at", "culqi_last_state", "culqi_last_event_at"])
        else:
            order.save(update_fields=["culqi_last_state", "culqi_last_event_at"])
    else:
        order.save(update_fields=["culqi_last_state", "culqi_last_event_at"])

    return HttpResponse("ok", status=200)