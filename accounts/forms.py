import re

from django import forms
from django.contrib.auth import authenticate, password_validation
from django.core.exceptions import ValidationError

from .models import User


class SignUpForm(forms.Form):
    """Sign-up page (Figma "Create account").

    Only Customer or Seller can be chosen here. Admin accounts are never
    self-selected: they are created with `manage.py createsuperuser`, or an
    existing admin changes a user's role in the admin site ("Manage User
    Accounts" in the proposal's use case diagram).
    """

    SIGNUP_ROLES = [
        (User.Role.CUSTOMER, "Customer"),
        (User.Role.SELLER, "Seller"),
    ]

    full_name = forms.CharField(
        max_length=150,
        error_messages={"required": "Please enter your name."},
    )
    email = forms.EmailField(
        max_length=254,
        error_messages={
            "required": "Please enter your email.",
            "invalid": "Please enter a valid email, like you@example.com.",
        },
    )
    password = forms.CharField(
        strip=False,
        error_messages={"required": "Please choose a password."},
    )
    role = forms.ChoiceField(
        choices=SIGNUP_ROLES,
        initial=User.Role.CUSTOMER,
        error_messages={
            "required": "Please choose an account type.",
            "invalid_choice": "Please choose Customer or Seller.",
        },
    )

    def clean_full_name(self):
        name = " ".join(self.cleaned_data["full_name"].split())
        if not name:
            raise ValidationError("Please enter your name.")
        return name

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"])
        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email already exists.", code="duplicate")
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        if password:
            # Runs the project's validators (8+ characters, not too common,
            # not all numbers, not too similar to the name or email).
            probe = User(email=cleaned.get("email", ""), full_name=cleaned.get("full_name", ""))
            try:
                password_validation.validate_password(password, user=probe)
            except ValidationError as error:
                self.add_error("password", error)
        return cleaned

    def save(self):
        data = self.cleaned_data
        return User.objects.create_user(
            email=data["email"],
            password=data["password"],
            full_name=data["full_name"],
            role=data["role"],
        )


class LoginForm(forms.Form):
    email = forms.EmailField(
        max_length=254,
        error_messages={
            "required": "Please enter your email.",
            "invalid": "Please enter a valid email, like you@example.com.",
        },
    )
    password = forms.CharField(strip=False, error_messages={"required": "Please enter your password."})

    error_messages = {
        # Same message whether the email or the password is wrong, so the form
        # doesn't reveal which emails have accounts.
        "invalid_login": "That email and password don't match. Please try again.",
    }

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        email, password = cleaned.get("email"), cleaned.get("password")
        if email and password:
            # authenticate() also refuses deactivated accounts (is_active=False).
            self.user = authenticate(self.request, username=email, password=password)
            if self.user is None:
                raise ValidationError(self.error_messages["invalid_login"], code="invalid_login")
        return cleaned


# +92 or 0, then 3, then nine digits (a Pakistani mobile number).
PHONE_PATTERN = re.compile(r"^(\+92|0)3[0-9]{9}$")
PHONE_MESSAGE = "Enter a Pakistani number, for example 0300 1234567 or +92 300 1234567."


class ProfileForm(forms.ModelForm):
    """US-05: the details a user may change on My Profile.

    Email and role are deliberately not fields, so a forged request can't change
    them. Everything except the name may be left empty.
    """

    full_name = forms.CharField(max_length=150, error_messages={"required": "Please enter your full name."})
    # Longer than the column so that "0300 123 4567" can be typed; spaces are removed below.
    phone = forms.CharField(max_length=30, required=False, error_messages={"max_length": PHONE_MESSAGE})
    # 255 matches Order.delivery_address, which this prefills.
    default_address = forms.CharField(
        max_length=255,
        required=False,
        error_messages={"max_length": "Please keep the address to 255 characters or fewer."},
    )
    default_city = forms.CharField(
        max_length=60,
        required=False,
        error_messages={"max_length": "Please keep the city to 60 characters or fewer."},
    )

    class Meta:
        model = User
        fields = ["full_name", "phone", "default_address", "default_city"]

    def clean_full_name(self):
        name = " ".join(self.cleaned_data["full_name"].split())
        if not name:
            raise ValidationError("Please enter your full name.")
        return name

    def clean_phone(self):
        """Store the number without spaces or dashes, e.g. 03001234567."""
        phone = re.sub(r"[\s-]", "", self.cleaned_data["phone"])
        if phone and not PHONE_PATTERN.match(phone):
            raise ValidationError(PHONE_MESSAGE)
        return phone

    def clean_default_address(self):
        return " ".join(self.cleaned_data["default_address"].split())

    def clean_default_city(self):
        return " ".join(self.cleaned_data["default_city"].split())

    def save(self):
        # Only these columns are written, whatever else is on the instance.
        self.instance.save(update_fields=self._meta.fields)
        return self.instance
