"""
Cart and orders: the ERD's CartItem, Order and OrderItem entities
(docs/database/erd_transcription.md).
"""

from django.conf import settings
from django.db import models


class CartItem(models.Model):
    # CASCADE: the cart belongs to the user.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    # CASCADE: if a listing is deleted it simply disappears from carts.
    species = models.ForeignKey(
        "catalog.PlantSpecies",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["added_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "species"], name="orders_cartitem_unique_user_species"),
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="orders_cartitem_quantity_gte_1"),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.species.common_name} ({self.user})"


class Order(models.Model):
    # The ERD does not list the status values; these are the project's
    # working set (see erd_transcription.md, "Decisions").
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        SHIPPED = "SHIPPED", "Shipped"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    # Cash on Delivery is the only payment method in scope (proposal, Scope).
    class PaymentMethod(models.TextChoices):
        COD = "COD", "Cash on Delivery"

    # PROTECT: orders are business records; a user with orders cannot be
    # hard-deleted (deactivate with is_active instead).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    # SET_NULL: the ERD marks this FK nullable; deleting a grow profile keeps the order.
    grow_profile = models.ForeignKey(
        "growprofiles.GrowProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    delivery_name = models.CharField(max_length=150)
    delivery_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    placed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-placed_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(total_amount__gte=0), name="orders_order_total_amount_gte_0"),
        ]

    def __str__(self):
        return f"Order #{self.pk} ({self.user})"


class OrderItem(models.Model):
    # CASCADE: items are part of their order.
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    # PROTECT: a listing that appears in any order cannot be hard-deleted
    # (set PlantSpecies.is_active = False instead), so order history stays intact.
    species = models.ForeignKey(
        "catalog.PlantSpecies",
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["order", "species"], name="orders_orderitem_unique_order_species"),
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="orders_orderitem_quantity_gte_1"),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name="orders_orderitem_unit_price_gte_0"),
        ]

    @property
    def total(self):
        """What this line cost when the order was placed (US-21 summary page)."""
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.species.common_name} (order #{self.order_id})"
