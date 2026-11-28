"""The cart (US-19) and checkout (US-21): add a plant, change how many, take
it out again, then turn the cart into a real Cash-on-Delivery order.

One CartItem row per species — the model enforces UNIQUE(user, species) — so
adding a plant that is already in the cart raises its quantity instead of
creating a second line. Stock is the ceiling everywhere: a line never holds
more plants than the listing has, and invasive or out-of-stock listings never
enter the cart at all.

Every change is a POST. Without JavaScript it stores a Django message and
redirects back; the HTMX version answers with a fragment that swaps the cart
body in place, and reports what happened through an HX-Trigger event that the
page turns into a toast, so nothing reloads either way.
"""

import json
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.ui import page_band
from catalog.models import PlantSpecies
from catalog.queries import visible_species

from .forms import CheckoutForm
from .models import CartItem, Order, OrderItem


def _is_htmx(request):
    """True for the in-place requests the cart buttons send."""
    return request.headers.get("HX-Request") == "true"


def _notify(request, level, text):
    """Queue one line of feedback for whichever way this request is answered."""
    if _is_htmx(request):
        notices = getattr(request, "_cart_notices", [])
        notices.append({"message": text, "level": level})
        request._cart_notices = notices
    else:
        getattr(messages, level)(request, text)


def _back(request, fallback):
    """Return to the page the form came from, if it is on this site."""
    target = request.POST.get("next") or ""
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return fallback


def _refuse_non_customers(request):
    """Only customers shop here: sellers and admins own or run the shop."""
    if request.user.is_customer:
        return None
    _notify(request, "error", "Only customer accounts can shop on Basera.")
    if _is_htmx(request):
        return _finish(request, None, fragment="orders/_cart_toast.html")
    return redirect("home")


def requires_customer(view):
    """login_required + customer-only, in a shape HTMX understands.

    A plain redirect would make HTMX swap the login page into the cart, so an
    expired session answers with HX-Redirect instead and the browser navigates.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if _is_htmx(request):
                response = HttpResponse(status=204)
                response["HX-Redirect"] = f"{reverse('login')}?next={request.get_full_path()}"
                return response
            return redirect_to_login(request.get_full_path())
        refused = _refuse_non_customers(request)
        if refused is not None:
            return refused
        return view(request, *args, **kwargs)

    return wrapper


def _cart_lines(user):
    """The cart as the templates want it: one dict per line, plus the totals."""
    items = (
        CartItem.objects.filter(user=user)
        .select_related("species", "species__seller")
        .order_by("added_at")
    )
    lines, subtotal = [], Decimal("0.00")
    for item in items:
        species = item.species
        line_total = species.price * item.quantity
        subtotal += line_total
        lines.append(
            {
                "species": species,
                "quantity": item.quantity,
                "line_total": line_total,
                # A listing can sell out or be withdrawn while it sits in a cart.
                "unavailable": species.stock_qty < 1 or species.is_invasive or not species.is_active,
                "at_limit": item.quantity >= species.stock_qty,
            }
        )
    return lines, subtotal, sum(line["quantity"] for line in lines)


def _finish(request, back, *, fragment="orders/_cart_response.html"):
    """Answer the request: a fragment in place for HTMX, a redirect otherwise."""
    if not _is_htmx(request):
        return redirect(back)

    if fragment == "orders/_cart_response.html":
        lines, subtotal, plant_count = _cart_lines(request.user)
        context = {
            "lines": lines,
            "subtotal": subtotal,
            "plant_count": plant_count,
            "any_unavailable": any(line["unavailable"] for line in lines),
        }
    else:
        context = {}
    response = render(request, fragment, context)

    notices = getattr(request, "_cart_notices", None)
    if notices:
        # htmx turns this into an event the page listens for (see botanical.js).
        response["HX-Trigger"] = json.dumps({"cart:notice": notices[0]})
    return response


def _requested_quantity(request):
    """The quantity posted with an Add-to-cart form, 1 when missing or odd."""
    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        return 1
    return max(1, quantity)


@requires_customer
def cart_view(request):
    """The cart page: every line, what it costs, and what is left in stock."""
    lines, subtotal, plant_count = _cart_lines(request.user)
    context = {
        "lines": lines,
        "subtotal": subtotal,
        "plant_count": plant_count,
        "any_unavailable": any(line["unavailable"] for line in lines),
        **page_band(
            request,
            "Your cart",
            "Plants waiting for your patch.",
            ("Catalogue", reverse("catalogue")),
            ("Cart", None),
        ),
    }
    return render(request, "orders/cart.html", context)


@requires_customer
def checkout(request):
    """US-21: turn the cart into a Cash-on-Delivery order.

    GET shows the delivery form prefilled from the user's profile. POST checks
    every line again (stock can have moved since the cart was last open) and
    creates the order in one transaction: item prices are snapshotted, the
    listings' stock is decremented with F() expressions so two buyers racing
    for the last plant cannot both win, and the cart is emptied.
    """
    lines, subtotal, plant_count = _cart_lines(request.user)

    sellable = [line for line in lines if not line["unavailable"]]
    if not sellable:
        # An empty cart — or one whose every line has sold out or been
        # withdrawn — has nothing to check out.
        _notify(request, "error", "Your cart has nothing available to check out.")
        return _finish(request, reverse("cart"))

    initial = {
        "delivery_name": request.user.full_name,
        "phone": request.user.phone,
    }
    form = CheckoutForm(initial=initial)

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                order = _place_order(request.user, form, sellable)
            except ValidationError as error:
                # Something sold out between loading the page and placing the
                # order; send the buyer back to the cart to see the new state.
                _notify(request, "error", "; ".join(error.messages))
                return _finish(request, reverse("cart"))
            return redirect("order_summary", pk=order.pk)

    context = {
        "form": form,
        "lines": lines,
        "subtotal": subtotal,
        "plant_count": plant_count,
        "has_unavailable": len(sellable) < len(lines),
        **page_band(
            request,
            "Checkout",
            "Where should your plants go?",
            ("Catalogue", reverse("catalogue")),
            ("Cart", reverse("cart")),
            ("Checkout", None),
        ),
    }
    return render(request, "orders/checkout.html", context)


def _place_order(user, form, lines):
    """Create the Order and its items atomically, or raise ValidationError.

    `lines` are the cart lines that looked sellable when the page was built;
    they are re-validated here against the database because the cart page may
    have been open while a seller changed a listing.
    """
    with transaction.atomic():
        # Lock the listing rows so a stock check and its decrement cannot race
        # another buyer's checkout.
        for line in lines:
            species = PlantSpecies.objects.select_for_update().get(pk=line["species"].pk)
            if species.stock_qty < line["quantity"] or species.is_invasive or not species.is_active:
                raise ValidationError(
                    f"{line['species'].common_name} is no longer available in that quantity."
                )

        order = Order.objects.create(
            user=user,
            grow_profile=None,
            status=Order.Status.PENDING,
            delivery_name=form.cleaned_data["delivery_name"],
            delivery_address=form.cleaned_data["delivery_address"],
            city=form.cleaned_data["city"],
            phone=form.cleaned_data["phone"],
            payment_method=Order.PaymentMethod.COD,
            total_amount=sum(line["line_total"] for line in lines),
        )
        for line in lines:
            OrderItem.objects.create(
                order=order,
                species=line["species"],
                quantity=line["quantity"],
                unit_price=line["species"].price,
            )
            # F() so the decrement happens in the database, not on a stale
            # Python copy of stock_qty.
            PlantSpecies.objects.filter(pk=line["species"].pk).update(
                stock_qty=F("stock_qty") - line["quantity"]
            )

        CartItem.objects.filter(user=user).delete()
        return order


@requires_customer
def order_summary(request, pk):
    """US-21: the confirmation page for one order — owner eyes only."""
    order = get_object_or_404(
        Order.objects.filter(user=request.user).prefetch_related(
            Prefetch("items", queryset=OrderItem.objects.select_related("species", "species__seller"))
        ),
        pk=pk,
    )
    context = {
        "order": order,
        "items": order.items.all(),
        "plant_count": sum(item.quantity for item in order.items.all()),
        **page_band(
            request,
            f"Order #{order.pk}",
            "Thank you — your plants are on their way.",
            ("Catalogue", reverse("catalogue")),
            ("Cart", reverse("cart")),
            (f"Order #{order.pk}", None),
        ),
    }
    return render(request, "orders/order_summary.html", context)


@requires_customer
@require_POST
def add_to_cart(request, pk):
    """Add one plant (or raise its quantity) and go back where we came from."""
    species = get_object_or_404(visible_species(), pk=pk)
    back = _back(request, reverse("species_detail", args=[species.pk]))

    if species.is_invasive:
        _notify(request, "error", f"{species.common_name} is invasive, so Basera doesn't sell it.")
        return _finish(request, back, fragment="orders/_cart_toast.html")
    if species.stock_qty < 1:
        _notify(request, "error", f"{species.common_name} is out of stock right now.")
        return _finish(request, back, fragment="orders/_cart_toast.html")

    quantity = _requested_quantity(request)

    with transaction.atomic():
        clamped = quantity > species.stock_qty
        item, created = CartItem.objects.get_or_create(
            user=request.user,
            species=species,
            defaults={"quantity": min(quantity, species.stock_qty)},
        )
        if created:
            if clamped:
                _notify(
                    request,
                    "success",
                    f"{species.common_name}: {species.stock_qty} in your cart — that's all that's left in stock.",
                )
            else:
                _notify(request, "success", f"{species.common_name} is in your cart.")
        else:
            previous = item.quantity
            wanted = min(previous + quantity, species.stock_qty)
            if wanted <= previous:
                # Either the cart already holds every plant in stock, or the
                # listing was reduced after it went in: never quietly lower it.
                if previous > species.stock_qty:
                    _notify(
                        request,
                        "info",
                        f"Only {species.stock_qty} of the {species.common_name} are left in stock.",
                    )
                else:
                    _notify(
                        request,
                        "info",
                        f"All {species.stock_qty} of the {species.common_name} in stock are already in your cart.",
                    )
                return _finish(request, back, fragment="orders/_cart_toast.html")
            item.quantity = wanted
            item.save(update_fields=["quantity"])
            if previous + quantity > species.stock_qty:
                _notify(
                    request,
                    "success",
                    f"{species.common_name}: {wanted} in your cart — that's all that's left in stock.",
                )
            else:
                _notify(request, "success", f"{species.common_name}: {wanted} in your cart.")

    return _finish(request, back, fragment="orders/_cart_toast.html")


@requires_customer
@require_POST
def update_cart(request, pk):
    """Set a line's quantity, or move it by ±1 from the cart page stepper."""
    species = get_object_or_404(visible_species(), pk=pk)
    item = get_object_or_404(CartItem, user=request.user, species=species)
    back = _back(request, reverse("cart"))

    if species.stock_qty < 1:
        _notify(request, "error", f"{species.common_name} is out of stock, so it can't be increased.")
        return _finish(request, back)

    if "quantity" in request.POST:
        try:
            target = int(request.POST["quantity"])
        except (TypeError, ValueError):
            _notify(request, "error", "That quantity doesn't look right. Try again.")
            return _finish(request, back)
    else:
        try:
            delta = int(request.POST.get("delta", 0))
        except (TypeError, ValueError):
            delta = 0
        target = item.quantity + delta

    target = max(1, min(target, species.stock_qty))

    if target == item.quantity:
        if target == species.stock_qty:
            _notify(request, "info", f"There are only {species.stock_qty} of the {species.common_name} in stock.")
        return _finish(request, back)

    item.quantity = target
    item.save(update_fields=["quantity"])
    # The stepper already shows the new number, so only speak up elsewhere.
    if not _is_htmx(request):
        _notify(request, "success", f"{species.common_name}: {target} in your cart.")
    return _finish(request, back)


@requires_customer
@require_POST
def remove_from_cart(request, pk):
    """Take a plant out of the cart."""
    item = CartItem.objects.filter(user=request.user, species_id=pk).select_related("species").first()
    back = _back(request, reverse("cart"))

    if item is None:
        _notify(request, "info", "That plant wasn't in your cart.")
        return _finish(request, back)

    name = item.species.common_name
    item.delete()
    _notify(request, "success", f"{name} removed from your cart.")
    return _finish(request, back)
