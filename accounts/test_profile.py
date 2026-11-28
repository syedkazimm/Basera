"""US-05: view and edit my profile."""

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class ProfileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="ana@example.com", password="Fern-and-moss-42", full_name="Ana Malik",
            phone="03001234567", default_address="House 12, Gulberg III", default_city="Lahore",
        )
        cls.seller = User.objects.create_user(
            email="seller@example.com", password="Fern-and-moss-42", full_name="Sam Seller",
            role=User.Role.SELLER,
        )
        cls.url = reverse("profile")

    def setUp(self):
        self.client.force_login(self.user)

    def post(self, **changes):
        data = {"full_name": "Ana Malik", "phone": "", "default_address": "", "default_city": ""}
        return self.client.post(self.url, {**data, **changes})

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('login')}?next={self.url}")

    def test_shows_current_details(self):
        response = self.client.get(self.url)
        for text in ["Ana Malik", "ana@example.com", "03001234567", "House 12, Gulberg III", "Lahore", "Customer"]:
            self.assertContains(response, text)

    def test_email_and_role_are_read_only(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'value="ana@example.com" readonly')
        self.assertNotContains(response, 'name="email"')
        self.assertNotContains(response, 'name="role"')

    def test_valid_changes_save_and_show_immediately(self):
        response = self.client.post(self.url, {
            "full_name": "  Ana   Khan ", "phone": "+92 321 765-4321",
            "default_address": " Flat 3,  Model Town ", "default_city": " Multan ",
        }, follow=True)
        self.assertRedirects(response, self.url)
        self.assertContains(response, "Your profile has been updated.")
        self.assertContains(response, 'value="Ana Khan"')
        self.user.refresh_from_db()
        self.assertEqual(
            (self.user.full_name, self.user.phone, self.user.default_address, self.user.default_city),
            ("Ana Khan", "+923217654321", "Flat 3, Model Town", "Multan"),
        )

    def test_optional_details_can_be_cleared(self):
        self.assertRedirects(self.post(), self.url)
        self.user.refresh_from_db()
        self.assertEqual((self.user.phone, self.user.default_address, self.user.default_city), ("", "", ""))

    def test_forged_email_and_role_are_ignored(self):
        self.post(email="other@example.com", role="ADMIN", is_superuser="on", is_active="")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "ana@example.com")
        self.assertEqual(self.user.role, User.Role.CUSTOMER)
        self.assertFalse(self.user.is_superuser)
        self.assertTrue(self.user.is_active)

    def test_saving_keeps_the_user_logged_in_with_the_same_password(self):
        self.post(full_name="Ana Khan")
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Fern-and-moss-42"))

    def test_blank_name_is_rejected_and_nothing_is_saved(self):
        response = self.post(full_name="   ", default_city="Multan")
        self.assertContains(response, "Please enter your full name.")
        self.assertContains(response, "Please fix the highlighted fields and try again.")
        self.assertContains(response, 'value="Multan"')  # typed values are kept
        self.user.refresh_from_db()
        self.assertEqual((self.user.full_name, self.user.default_city), ("Ana Malik", "Lahore"))
        self.assertEqual(response.wsgi_request.user.full_name, "Ana Malik")

    def test_phone_must_be_a_pakistani_number(self):
        for bad in ["0300 12345", "0421234567", "+1 202 555 0100", "030012345678", "03abc234567", "923001234567"]:
            with self.subTest(phone=bad):
                response = self.post(phone=bad)
                self.assertContains(response, "Enter a Pakistani number")
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, "03001234567")

    def test_both_phone_formats_are_accepted(self):
        for typed, stored in [("0300 123 4567", "03001234567"), ("+923001234567", "+923001234567")]:
            with self.subTest(phone=typed):
                self.assertRedirects(self.post(phone=typed), self.url)
                self.user.refresh_from_db()
                self.assertEqual(self.user.phone, stored)

    def test_too_long_address_and_city_are_rejected(self):
        response = self.post(default_address="a" * 256, default_city="c" * 61)
        self.assertContains(response, "255 characters or fewer")
        self.assertContains(response, "60 characters or fewer")

    def test_database_supplies_defaults_for_code_that_omits_the_new_columns(self):
        """An older branch, or the old site mid-deploy, inserts users without these columns."""
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts_user (password, is_superuser, email, full_name, phone, role,"
                " is_active, date_joined) VALUES ('!', false, 'old@example.com', 'Old Code', '',"
                " 'CUSTOMER', true, now())")
        old = User.objects.get(email="old@example.com")
        self.assertEqual((old.default_address, old.default_city), ("", ""))

    def test_editing_never_touches_another_account(self):
        self.post(full_name="Changed Name", id=self.seller.pk, user=self.seller.pk)
        self.seller.refresh_from_db()
        self.assertEqual(self.seller.full_name, "Sam Seller")

    def test_customer_links_and_header_icon(self):
        response = self.client.get(self.url)
        for name in ["change_password", "grow_profiles", "my_orders"]:
            self.assertContains(response, f'href="{reverse(name)}"')
        self.assertContains(response, f'class="bt-icon-link" href="{self.url}"')
        self.assertContains(response, "0 saved")

    def test_seller_can_open_profile_without_customer_links(self):
        self.client.force_login(self.seller)
        response = self.client.get(self.url)
        self.assertContains(response, "Seller")
        self.assertNotContains(response, "My orders")
        self.assertNotContains(response, "saved</dd>")
        self.assertContains(self.client.get(reverse("home")), f'href="{self.url}"')

    def test_post_without_csrf_token_is_refused(self):
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url, {"full_name": "Forged"}).status_code, 403)
