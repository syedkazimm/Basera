"""Tests for checkout and the order summary (US-21).

Checkout turns the cart into a Cash-on-Delivery order: the delivery form is
prefilled from the user's profile, the phone must be a Pakistani mobile, and
placing the order snapshots prices, decrements stock and empties the cart in
one transaction. The summary page belongs to the order's owner only.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from accounts.tests import FAST_HASHERS
from catalog.models import PlantSpecies

from .models import CartItem, Order, OrderItem

User = get_user_model()

GOOD_PHONE = "0300 1234567"


def make_species(seller, name, **overrides):
    data = dict(
        seller=seller, common_name=name, scientific_name=f"{name} scientificus",
        description="A test plant.", light_need="Full sun", water_need="Low",
        suitable_soils="Loam", setting=PlantSpecies.Setting.OUTDOOR,
        ecological_role="Feeds bees.", price=Decimal("450.00"), stock_qty=10,
    )
    data.update(overrides)
    return PlantSpecies.objects.create(**data)


@FAST_HASHERS
class CheckoutFormTests(TestCase):
    """The phone check: Pakistani mobiles only, one canonical spelling kept."""

    def test_plain_mobile_is_valid_and_normalised(self):
        from .forms import CheckoutForm
        form = CheckoutForm(data={
            "delivery_name": "Ana Khan", "delivery_address": "12-A Canal Road",
            "city": "Lahore", "phone": "0300 1234567",
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["phone"], "03001234567")

    def test_plus_92_format_is_valid_and_normalised(self):
        from .forms import CheckoutForm
        for raw in ("+92 300 1234567", "+92-321-1234567", "03211234567", "0345-1234567"):
            with self.subTest(raw=raw):
                form = CheckoutForm(data={
                    "delivery_name": "Ana Khan", "delivery_address": "12-A Canal Road",
                    "city": "Lahore", "phone": raw,
                })
                self.assertTrue(form.is_valid(), form.errors)
                self.assertTrue(form.cleaned_data["phone"].startswith("03"))

    def test_landlines_and_foreign_numbers_are_rejected(self):
        from .forms import CheckoutForm
        for raw in ("042 3577 0000", "030123456", "+1 555 236 8888", "03001234567890", "not-a-phone", ""):
            with self.subTest(raw=raw):
                form = CheckoutForm(data={
                    "delivery_name": "Ana Khan", "delivery_address": "12-A Canal Road",
                    "city": "Lahore", "phone": raw,
                })
                self.assertFalse(form.is_valid())
                self.assertIn("phone", form.errors)

    def test_whitespace_only_fields_are_rejected(self):
        from .forms import CheckoutForm
        form = CheckoutForm(data={
            "delivery_name": "   ", "delivery_address": "12-A Canal Road",
            "city": "Lahore", "phone": GOOD_PHONE,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("delivery_name", form.errors)

    def test_non_ascii_digits_are_rejected(self):
        from .forms import CheckoutForm
        form = CheckoutForm(data={
            "delivery_name": "Ana Khan", "delivery_address": "12-A Canal Road",
            "city": "Lahore", "phone": "٠٣٠٠١٢٣٤٥٦٧",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)


@FAST_HASHERS
class CheckoutViewTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            "seller@basera.test", "x", full_name="Sam Seller", role=User.Role.SELLER
        )
        self.customer = User.objects.create_user(
            "ana@example.com", "x", full_name="Ana Khan", phone="+92 300 1234567"
        )
        self.neem = make_species(self.seller, "Neem")
        self.species2 = make_species(self.seller, "Tulsi", price=Decimal("200.00"), stock_qty=3)
        CartItem.objects.create(user=self.customer, species=self.neem, quantity=2)
        CartItem.objects.create(user=self.customer, species=self.species2, quantity=1)
        self.client.force_login(self.customer)
        self.data = {
            "delivery_name": "Ana Khan", "delivery_address": "12-A Canal Road",
            "city": "Lahore", "phone": GOOD_PHONE,
        }

    # --- guards ---------------------------------------------------------

    def test_guest_is_sent_to_log_in(self):
        self.client.logout()
        response = self.client.get(reverse("checkout"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_sellers_and_admins_cannot_check_out(self):
        seller = User.objects.create_user(
            "sam@basera.test", "x", full_name="Sam Seller", role=User.Role.SELLER
        )
        CartItem.objects.create(user=seller, species=self.neem, quantity=1)
        self.client.force_login(seller)
        response = self.client.get(reverse("checkout"), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())

    def test_empty_cart_sends_you_back_to_the_cart(self):
        CartItem.objects.all().delete()
        response = self.client.get(reverse("checkout"), follow=True)
        self.assertRedirects(response, reverse("cart"))
        self.assertFalse(Order.objects.exists())

    def test_cart_of_only_unavailable_lines_cannot_check_out(self):
        self.neem.is_invasive = True
        self.neem.save()
        self.species2.stock_qty = 0
        self.species2.save()
        response = self.client.get(reverse("checkout"), follow=True)
        self.assertRedirects(response, reverse("cart"))

    # --- the form page --------------------------------------------------

    def test_form_is_prefilled_from_the_profile(self):
        response = self.client.get(reverse("checkout"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Ana Khan"')
        self.assertContains(response, 'value="+92 300 1234567"')
        self.assertContains(response, "Cash on Delivery")

    def test_get_checkout_is_a_page_not_a_fragment(self):
        response = self.client.get(reverse("checkout"))
        self.assertTemplateUsed(response, "orders/checkout.html")

    # --- placing the order ----------------------------------------------

    def test_valid_post_creates_the_order_and_items(self):
        response = self.client.post(reverse("checkout"), self.data)
        self.assertRedirects(response, reverse("order_summary", args=[Order.objects.get().pk]))
        order = Order.objects.get()
        self.assertEqual(order.user, self.customer)
        self.assertEqual(order.delivery_name, "Ana Khan")
        self.assertEqual(order.delivery_address, "12-A Canal Road")
        self.assertEqual(order.city, "Lahore")
        self.assertEqual(order.phone, "03001234567")
        self.assertEqual(order.payment_method, Order.PaymentMethod.COD)
        self.assertEqual(order.status, Order.Status.PENDING)
        # 2 x 450 + 1 x 200
        self.assertEqual(order.total_amount, Decimal("1100.00"))
        self.assertEqual(order.items.count(), 2)
        tulsi = order.items.get(species=self.species2)
        self.assertEqual(tulsi.quantity, 1)
        # The price is snapshotted, so later repricing can't rewrite history.
        self.assertEqual(tulsi.unit_price, Decimal("200.00"))

    def test_placing_the_order_empties_the_cart_and_decrements_stock(self):
        self.client.post(reverse("checkout"), self.data)
        self.assertFalse(CartItem.objects.filter(user=self.customer).exists())
        self.neem.refresh_from_db()
        self.species2.refresh_from_db()
        self.assertEqual(self.neem.stock_qty, 8)
        self.assertEqual(self.species2.stock_qty, 2)

    def test_stock_is_checked_again_at_place_time(self):
        # The cart holds 2 Neem but the listing dropped to 1 after the page loaded.
        self.neem.stock_qty = 1
        self.neem.save(update_fields=["stock_qty"])
        response = self.client.post(reverse("checkout"), self.data, follow=True)
        self.assertRedirects(response, reverse("cart"))
        self.assertFalse(Order.objects.exists())
        self.assertTrue(any("left in stock" in m.message for m in get_messages(response.wsgi_request)))

    def test_invalid_post_keeps_the_cart_and_the_form(self):
        response = self.client.post(reverse("checkout"), {**self.data, "phone": "042 3577 0000"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a Pakistani mobile number")
        self.assertEqual(CartItem.objects.filter(user=self.customer).count(), 2)
        self.assertFalse(Order.objects.exists())

    def test_unavailable_line_at_place_time_blocks_the_whole_order(self):
        self.species2.is_active = False
        self.species2.save(update_fields=["is_active"])
        response = self.client.post(reverse("checkout"), self.data, follow=True)
        self.assertRedirects(response, reverse("cart"))
        self.assertFalse(Order.objects.exists())
        self.assertEqual(CartItem.objects.filter(user=self.customer).count(), 2)
        self.neem.refresh_from_db()
        self.assertEqual(self.neem.stock_qty, 10)

    def test_price_is_read_when_the_order_is_placed_not_when_the_page_loaded(self):
        self.client.get(reverse("checkout"))
        self.neem.price = Decimal("500.00")
        self.neem.save(update_fields=["price"])
        self.client.post(reverse("checkout"), self.data)
        order = Order.objects.get()
        self.assertEqual(order.items.get(species=self.neem).unit_price, Decimal("500.00"))
        self.assertEqual(order.total_amount, Decimal("1200.00"))

    def test_another_customers_cart_is_left_alone(self):
        other = User.objects.create_user("bilal@example.com", "x", full_name="Bilal Ahmed")
        CartItem.objects.create(user=other, species=self.neem, quantity=1)
        self.client.post(reverse("checkout"), self.data)
        self.assertTrue(CartItem.objects.filter(user=other).exists())

    def test_post_only(self):
        response = self.client.post(reverse("order_summary", args=[1]))
        self.assertIn(response.status_code, (302, 404))


@FAST_HASHERS
class OrderSummaryTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            "seller@basera.test", "x", full_name="Sam Seller", role=User.Role.SELLER
        )
        self.customer = User.objects.create_user("ana@example.com", "x", full_name="Ana Khan")
        self.other = User.objects.create_user("bilal@example.com", "x", full_name="Bilal Ahmed")
        self.neem = make_species(self.seller, "Neem")
        self.order = Order.objects.create(
            user=self.customer, delivery_name="Ana Khan", delivery_address="12-A Canal Road",
            city="Lahore", phone="03001234567", total_amount=Decimal("900.00"),
        )
        OrderItem.objects.create(order=self.order, species=self.neem, quantity=2, unit_price=Decimal("450.00"))

    def test_owner_sees_the_summary(self):
        self.client.force_login(self.customer)
        response = self.client.get(reverse("order_summary", args=[self.order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "orders/order_summary.html")
        self.assertContains(response, "Neem")
        self.assertContains(response, "12-A Canal Road")
        self.assertContains(response, "Cash on Delivery")
        self.assertContains(response, "Rs 900")

    def test_someone_elses_order_is_a_404(self):
        self.client.force_login(self.other)
        response = self.client.get(reverse("order_summary", args=[self.order.pk]))
        self.assertEqual(response.status_code, 404)

    def test_guest_is_sent_to_log_in(self):
        response = self.client.get(reverse("order_summary", args=[self.order.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_cart_page_has_a_real_checkout_button(self):
        CartItem.objects.create(user=self.customer, species=self.neem, quantity=1)
        self.client.force_login(self.customer)
        response = self.client.get(reverse("cart"))
        self.assertContains(response, reverse("checkout"))
        self.assertNotContains(response, "Checkout coming soon")

    def test_checkout_button_is_disabled_when_a_line_is_unavailable(self):
        CartItem.objects.create(user=self.customer, species=self.neem, quantity=1)
        self.neem.stock_qty = 0
        self.neem.save(update_fields=["stock_qty"])
        self.client.force_login(self.customer)
        response = self.client.get(reverse("cart"))
        self.assertNotContains(response, 'href="/checkout/"')
        self.assertContains(response, "aria-disabled")
