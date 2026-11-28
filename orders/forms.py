"""US-21: the checkout form — where the order should go and how it is paid.

Basera ships inside Pakistan with Cash on Delivery as the only payment
method (proposal, Scope), so the form asks for the delivery details and
checks the phone number is a real Pakistani mobile number before the order
is created.
"""

import re

from django import forms

from .models import Order


# Pakistani mobile numbers: 03XX followed by 7 digits, optionally written
# with a leading +92 instead of the 0, and with the digits grouped by a
# space or a dash ("0300 1234567", "+92-321-1234567"). Landlines (02x, 04x…)
# and foreign numbers are rejected: delivery is by courier to a mobile.
PAKISTANI_MOBILE = re.compile(r"^(?:\+92|0)3[0-9]{2}[- ]?[0-9]{7}$")


def normalise_mobile(value):
    """Keep one canonical spelling in the order record: 03XXXXXXXXX."""
    digits = value.strip().replace(" ", "").replace("-", "")
    if digits.startswith("+92"):
        digits = "0" + digits[3:]
    return digits


class CheckoutForm(forms.Form):
    """Delivery details for a Cash-on-Delivery order."""

    delivery_name = forms.CharField(
        max_length=Order._meta.get_field("delivery_name").max_length,
        label="Full name",
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    delivery_address = forms.CharField(
        max_length=Order._meta.get_field("delivery_address").max_length,
        label="Delivery address",
        widget=forms.TextInput(attrs={"autocomplete": "street-address"}),
    )
    city = forms.CharField(
        max_length=Order._meta.get_field("city").max_length,
        label="City",
        widget=forms.TextInput(attrs={"autocomplete": "address-level2"}),
    )
    phone = forms.CharField(
        max_length=20,
        label="Mobile number",
        help_text="Pakistani mobile, e.g. 0300 1234567 or +92 300 1234567.",
        widget=forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
    )

    def clean_delivery_name(self):
        return self.cleaned_data["delivery_name"].strip()

    def clean_delivery_address(self):
        return self.cleaned_data["delivery_address"].strip()

    def clean_city(self):
        return self.cleaned_data["city"].strip()

    def clean_phone(self):
        value = self.cleaned_data["phone"].strip()
        compact = value.replace(" ", "").replace("-", "")
        if not PAKISTANI_MOBILE.match(compact):
            raise forms.ValidationError(
                "Enter a Pakistani mobile number, like 0300 1234567 or +92 300 1234567."
            )
        return normalise_mobile(value)
