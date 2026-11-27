"""Forms for sellers' plant listings (US-13 Create a species listing)."""

import os
from decimal import Decimal

from django import forms

from .models import ECOLOGICAL_ROLE_CHOICES, SOIL_CHOICES, PlantSpecies, Region

MAX_IMAGE_BYTES = 2 * 1024 * 1024  # photos must be under 2 MB
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
IMAGE_ERROR = "Please use a JPG or PNG under 2 MB."


def _required(message):
    return {"required": message}


class ListingForm(forms.ModelForm):
    """Add a plant. Everything is required except the photo.

    Soils and ecological roles are chosen from fixed lists (several of each)
    and stored as comma-separated text on the listing.
    """

    regions = forms.ModelMultipleChoiceField(
        queryset=Region.objects.order_by("pk"),
        widget=forms.CheckboxSelectMultiple,
        error_messages=_required("Please choose at least one region."),
    )
    soils = forms.MultipleChoiceField(
        choices=[(name, name) for name, _ in SOIL_CHOICES],
        widget=forms.CheckboxSelectMultiple,
        error_messages=_required("Please choose at least one soil."),
    )
    ecological_roles = forms.MultipleChoiceField(
        choices=[(name, name) for name in ECOLOGICAL_ROLE_CHOICES],
        widget=forms.CheckboxSelectMultiple,
        error_messages=_required("Please choose at least one ecological role."),
    )

    class Meta:
        model = PlantSpecies
        fields = [
            "common_name", "scientific_name", "description", "image",
            "light_need", "water_need", "setting", "price", "stock_qty",
        ]
        widgets = {
            "light_need": forms.RadioSelect,
            "water_need": forms.RadioSelect,
            "setting": forms.RadioSelect,
        }
        error_messages = {
            "common_name": _required("Please enter the common name."),
            "scientific_name": _required("Please enter the scientific name."),
            "description": _required("Please add a description."),
            "light_need": _required("Please choose a light level."),
            "water_need": _required("Please choose a water level."),
            "setting": _required("Please choose indoor, outdoor or both."),
            # Every rejected file (not an image, empty, broken) gets the same message.
            "image": {key: IMAGE_ERROR for key in ("invalid", "invalid_image", "missing", "empty")},
            "price": {
                "required": "Please enter a price.",
                "invalid": "Please enter a price in rupees, like 450.",
            },
            "stock_qty": {
                "required": "Please enter how many you have in stock.",
                "invalid": "Please enter a whole number.",
                "min_value": "Stock must be 0 or more.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The model allows a blank description, but a listing needs one.
        self.fields["description"].required = True
        # Drop Django's "---------" empty choice from the radio groups.
        for name in ("light_need", "water_need", "setting"):
            self.fields[name].choices = [c for c in self.fields[name].choices if c[0]]
        if not self.instance.pk:
            # Start a new listing with an empty Stock box (not the model's 0),
            # so the seller types a number.
            self.fields["stock_qty"].initial = None
            self.initial.pop("stock_qty", None)
        else:
            self.initial.setdefault("regions", list(self.instance.regions.all()))
            self.initial.setdefault("soils", self.instance.soil_list)
            self.initial.setdefault("ecological_roles", self.instance.ecological_role_list)

    def clean_common_name(self):
        return self.cleaned_data["common_name"].strip()

    def clean_scientific_name(self):
        return self.cleaned_data["scientific_name"].strip()

    def clean_price(self):
        price = self.cleaned_data["price"]
        if price is not None and price <= Decimal("0"):
            raise forms.ValidationError("Price must be more than Rs 0.", code="min_value")
        return price

    def clean_image(self):
        image = self.cleaned_data.get("image")
        # Nothing new uploaded (or the existing photo kept): nothing to check.
        if not image or not hasattr(image, "image"):
            return image
        extension = os.path.splitext(image.name)[1].lower()
        fmt = getattr(image.image, "format", None)
        if (image.size >= MAX_IMAGE_BYTES or extension not in ALLOWED_IMAGE_EXTENSIONS
                or fmt not in ALLOWED_IMAGE_FORMATS):
            raise forms.ValidationError(IMAGE_ERROR, code="invalid_image")
        return image

    def save(self, commit=True):
        listing = super().save(commit=False)
        listing.suitable_soils = ", ".join(self.cleaned_data["soils"])
        listing.ecological_role = ", ".join(self.cleaned_data["ecological_roles"])
        if commit:
            listing.save()
            listing.regions.set(self.cleaned_data["regions"])
        return listing
