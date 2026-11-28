"""
Accounts: the ERD's "User" entity (docs/database/erd_transcription.md).

ERD columns -> Django fields
    id            -> id (BigAutoField, primary key)
    email         -> email (unique, case-insensitive; the login identifier)
    password_hash -> password (Django's salted hash, set only via set_password)
    full_name     -> full_name
    phone         -> phone
    role          -> role (CUSTOMER / SELLER / ADMIN)
    is_active     -> is_active
    date_joined   -> date_joined

Columns added for US-05 (not in the ERD): default_address, default_city.

Extra columns that Django's auth framework needs (not in the ERD):
    last_login   (from AbstractBaseUser, set by Django on every login)
    is_superuser (from PermissionsMixin, plus the groups / user_permissions
                  many-to-many tables that power admin permissions)
"""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class UserManager(BaseUserManager):
    """Creates users with a lower-cased email and a hashed password."""

    use_in_migrations = True

    @classmethod
    def normalize_email(cls, email):
        # Store the whole address in lower case so "Ana@Mail.com" and
        # "ana@mail.com" are the same account (the DB constraint on
        # Lower("email") enforces this as well).
        return (email or "").strip().lower()

    def get_by_natural_key(self, username):
        # Emails are stored normalised (see save()), so normalising the login
        # input gives an exact match however the email is typed.
        return self.get(email=self.normalize_email(username))

    def _create_user(self, email, password, **extra_fields):
        # Normalise first so whitespace-only input counts as missing.
        email = self.normalize_email(email)
        if not email:
            raise ValueError("Users must have an email address.")
        full_name = (extra_fields.get("full_name") or "").strip()
        if not full_name:
            raise ValueError("Users must have a full name.")
        extra_fields["full_name"] = full_name
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # hashes; a None password becomes unusable
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("role", User.Role.CUSTOMER)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        if extra_fields.get("role") != User.Role.ADMIN:
            raise ValueError("Superuser must have role=ADMIN.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        SELLER = "SELLER", "Seller"
        ADMIN = "ADMIN", "Admin"

    email = models.EmailField("email address", max_length=254, unique=True)
    # `password` (ERD: password_hash) is inherited from AbstractBaseUser.
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    # Filled in on My Profile (US-05) and used to prefill the delivery form at checkout.
    # db_default keeps a default in the database itself, so code from before these
    # columns existed (an older branch, or the old site during a deploy) can still add users.
    default_address = models.TextField(blank=True, default="", db_default="")
    default_city = models.CharField(max_length=60, blank=True, default="", db_default="")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CUSTOMER)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_email_ci_unique",
                violation_error_message="A user with that email already exists.",
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=["CUSTOMER", "SELLER", "ADMIN"]),
                name="accounts_user_role_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(full_name=""),
                name="accounts_user_full_name_not_empty",
                violation_error_message="Please enter your full name.",
            ),
            # A superuser must also have the ADMIN role.
            models.CheckConstraint(
                condition=models.Q(is_superuser=False) | models.Q(role="ADMIN"),
                name="accounts_user_superuser_is_admin",
                violation_error_message="A superuser must have the Admin role.",
            ),
        ]

    def __str__(self):
        return self.email

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

    def save(self, *args, **kwargs):
        # Keep email lower-case however the row is saved (forms, admin, shell).
        self.email = self.__class__.objects.normalize_email(self.email)
        super().save(*args, **kwargs)

    # The ERD has no is_staff column; admin-site access is derived from role.
    # Side effects: is_staff cannot be passed to create_user()/User(...) or
    # used in queryset filters; use role="ADMIN" instead. Being ADMIN only
    # lets a user log into the admin site; non-superusers still need model
    # permissions granted (groups / user_permissions) to see anything there.
    @property
    def is_staff(self):
        return self.is_active and (self.role == self.Role.ADMIN or self.is_superuser)

    @property
    def is_customer(self):
        return self.role == self.Role.CUSTOMER

    @property
    def is_seller(self):
        return self.role == self.Role.SELLER

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name.split(" ")[0] if self.full_name else self.email
