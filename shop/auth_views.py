from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import redirect, render

from .forms_auth import SignUpForm
from .views import _get_cart, _cart_count, DANIELA_WSP


def signup(request):
    if request.user.is_authenticated:
        return redirect("product_list")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "✅ Cuenta creada. ¡Bienvenida! 💖")
            return redirect("product_list")
        messages.error(request, "Revisa los datos del formulario.")
    else:
        form = SignUpForm()

    cart = _get_cart(request)
    return render(request, "registration/signup.html", {
        "form": form,
        "cart_count": _cart_count(cart),
        "daniela_wsp": DANIELA_WSP,
    })
