from decimal import Decimal
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.http import HttpRequest
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth.decorators import login_required

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
