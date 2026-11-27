from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import MAX_IMAGE_BYTES, ListingForm
from .models import SOIL_CHOICES, PlantSpecies


# Short hints and icons shown on the choice cards (wireframe "Add a plant").
CARD_DETAILS = {
    "light_need": {
        "Full sun": ("6+ hours of direct sun", "sun"),
        "Partial shade": ("3–6 hours of sun", "cloud"),
        "Shade": ("Under 3 hours of sun", "moon"),
    },
    "water_need": {
        "Low": ("Once a week or less", "drop"),
        "Medium": ("A few times a week", "drop"),
        "High": ("Daily or irrigated", "drop"),
    },
    "setting": {
        "INDOOR": ("Inside a room or balcony", "home"),
        "OUTDOOR": ("Garden, yard or rooftop", "sun"),
        "BOTH": ("Happy in either", "both"),
    },
    "soils": {name: (hint, "layers") for name, hint in SOIL_CHOICES},
}


def _options(bound_field):
    """The choices of a form field, with whether each is currently chosen."""
    value = bound_field.value()
    if value is None:
        chosen = set()
    elif isinstance(value, (list, tuple)):
        chosen = {str(getattr(v, "pk", v)) for v in value}
    else:
        chosen = {str(value)}
    details = CARD_DETAILS.get(bound_field.name, {})
    options = []
    for index, (key, label) in enumerate(bound_field.field.choices):
        key = str(getattr(key, "value", key))
        if not key:
            continue
        hint, icon = details.get(key, ("", ""))
        options.append({
            "id": f"id_{bound_field.name}_{index}",
            "value": key, "label": label, "hint": hint, "icon": icon,
            "checked": key in chosen,
        })
    return options


def _seller_required(request):
    if not request.user.is_seller:
        raise PermissionDenied("Only sellers can add plants.")


@login_required
def add_listing(request):
    """US-13: a seller lists a native plant. It is in the catalogue straight away."""
    _seller_required(request)

    if request.method == "POST":
        form = ListingForm(request.POST, request.FILES)
        if form.is_valid():
            form.instance.seller = request.user
            with transaction.atomic():
                listing = form.save()
            messages.success(request, f"{listing.common_name} is published. Buyers can find it in the catalogue now.")
            return redirect("plant_detail", pk=listing.pk)
    else:
        form = ListingForm()

    rejected_file = request.FILES.get("image") if form.errors.get("image") else None
    return render(request, "catalog/add_listing.html", {
        "form": form,
        "groups": {name: _options(form[name]) for name in (
            "regions", "light_need", "water_need", "soils", "setting", "ecological_roles")},
        "max_image_bytes": MAX_IMAGE_BYTES,
        "rejected_file": rejected_file,
    })


@login_required
def plant_detail(request, pk):
    """A listing as buyers see it. Inactive listings are only visible to their seller."""
    visible = Q(is_active=True) | Q(seller=request.user)
    listing = get_object_or_404(
        PlantSpecies.objects.filter(visible).select_related("seller").prefetch_related("regions"),
        pk=pk,
    )
    return render(request, "catalog/plant_detail.html", {"listing": listing})
