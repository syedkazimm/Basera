from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import User


class BaseraUserCreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "full_name", "role")


class BaseraUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = BaseraUserChangeForm
    add_form = BaseraUserCreationForm

    list_display = ("email", "full_name", "role", "is_active", "date_joined")
    list_filter = ("role", "is_active", "is_superuser")
    search_fields = ("email", "full_name", "phone")
    ordering = ("email",)
    readonly_fields = ("last_login", "date_joined")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name", "phone", "default_address", "default_city")}),
        ("Role and access", {"fields": ("role", "is_active", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "role", "usable_password", "password1", "password2"),
            },
        ),
    )
