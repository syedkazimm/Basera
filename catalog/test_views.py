"""US-13 Create a species listing: the Add a plant page and the plant details page."""

import io
import os
import shutil
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from .models import PlantSpecies, Region

User = get_user_model()
TEMP_MEDIA = tempfile.mkdtemp(prefix="basera-test-media-")


def make_image(fmt="JPEG", name="neem.jpg", size=(40, 40), noise=False):
    if noise:
        img = Image.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3))
    else:
        img = Image.new("RGB", size, (90, 140, 80))
    buffer = io.BytesIO()
    img.save(buffer, fmt)
    content_type = {"JPEG": "image/jpeg", "PNG": "image/png", "GIF": "image/gif"}[fmt]
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)


@override_settings(
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
    MEDIA_ROOT=TEMP_MEDIA,
)
class AddListingTests(TestCase):
    url = reverse("listing_add")

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.seller = User.objects.create_user(
            "seller@basera.test", "x", full_name="Green Roots Nursery", role=User.Role.SELLER)
        self.customer = User.objects.create_user(
            "buyer@basera.test", "x", full_name="Bea Buyer", role=User.Role.CUSTOMER)
        # Regions come from the 0003_seed_regions migration.
        self.punjab = Region.objects.get(name="Punjab Plains")
        self.potohar = Region.objects.get(name="Potohar Plateau")

    def valid_data(self, **changes):
        data = {
            "common_name": "Neem",
            "scientific_name": "Azadirachta indica",
            "description": "A hardy evergreen tree that gives dense shade.",
            "regions": [self.punjab.pk, self.potohar.pk],
            "light_need": "Full sun",
            "water_need": "Medium",
            "soils": ["Loam"],
            "setting": "OUTDOOR",
            "ecological_roles": ["Shade & cooling", "Pollinators"],
            "price": "450",
            "stock_qty": "24",
        }
        data.update(changes)
        return {k: v for k, v in data.items() if v is not None}

    # ---------- Who can open the page ----------

    def test_logged_out_user_is_sent_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('login')}?next={self.url}")

    def test_customer_gets_403(self):
        self.client.force_login(self.customer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        response = self.client.post(self.url, self.valid_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(PlantSpecies.objects.exists())

    def test_seller_sees_the_form_with_all_regions(self):
        self.client.force_login(self.seller)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "catalog/add_listing.html")
        for name in ("Punjab Plains", "Potohar Plateau", "Sindh Indus Plains", "Northern Highlands", "Balochistan Uplands"):
            self.assertContains(response, name)
        self.assertContains(response, "Publish listing")

    # ---------- Creating a listing ----------

    def test_valid_listing_is_created_under_the_seller(self):
        self.client.force_login(self.seller)
        response = self.client.post(self.url, self.valid_data())
        listing = PlantSpecies.objects.get()
        self.assertRedirects(response, reverse("plant_detail", args=[listing.pk]))
        self.assertEqual(listing.seller, self.seller)
        self.assertEqual(listing.common_name, "Neem")
        self.assertEqual(listing.price, Decimal("450"))
        self.assertEqual(listing.stock_qty, 24)
        self.assertEqual(listing.suitable_soils, "Loam")
        self.assertEqual(listing.ecological_role_list, ["Shade & cooling", "Pollinators"])
        self.assertEqual(set(listing.regions.all()), {self.punjab, self.potohar})
        self.assertTrue(listing.is_active)

    def test_new_listing_is_visible_to_buyers_with_a_placeholder(self):
        self.client.force_login(self.seller)
        self.client.post(self.url, self.valid_data())
        listing = PlantSpecies.objects.get()

        self.client.force_login(self.customer)
        response = self.client.get(reverse("plant_detail", args=[listing.pk]))
        self.assertContains(response, "Neem")
        self.assertContains(response, "Azadirachta indica")
        self.assertContains(response, "Rs 450")
        self.assertContains(response, "In stock · 24 available")
        self.assertContains(response, "Green Roots Nursery")
        self.assertContains(response, 'aria-label="No photo yet"')

    def test_stock_zero_is_allowed(self):
        self.client.force_login(self.seller)
        self.client.post(self.url, self.valid_data(stock_qty="0"))
        listing = PlantSpecies.objects.get()
        self.assertEqual(listing.stock_qty, 0)
        response = self.client.get(reverse("plant_detail", args=[listing.pk]))
        self.assertContains(response, "Out of stock")

    def test_cannot_set_seller_from_the_form(self):
        self.client.force_login(self.seller)
        self.client.post(self.url, self.valid_data(seller=self.customer.pk))
        self.assertEqual(PlantSpecies.objects.get().seller, self.seller)

    # ---------- Required fields ----------

    def test_required_fields_show_errors_and_save_nothing(self):
        self.client.force_login(self.seller)
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PlantSpecies.objects.exists())
        for message in (
            "Please fix the highlighted fields and try again.",
            "Please enter the common name.",
            "Please enter the scientific name.",
            "Please add a description.",
            "Please choose at least one region.",
            "Please choose a light level.",
            "Please choose a water level.",
            "Please choose at least one soil.",
            "Please choose indoor, outdoor or both.",
            "Please choose at least one ecological role.",
            "Please enter a price.",
        ):
            self.assertContains(response, message)

    def test_each_suitability_attribute_is_required(self):
        self.client.force_login(self.seller)
        for field in ("regions", "light_need", "water_need", "soils", "setting", "ecological_roles"):
            with self.subTest(field=field):
                response = self.client.post(self.url, self.valid_data(**{field: None}))
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["form"].errors)
        self.assertFalse(PlantSpecies.objects.exists())

    def test_unknown_choice_values_are_rejected(self):
        self.client.force_login(self.seller)
        response = self.client.post(self.url, self.valid_data(light_need="Moonlight", soils=["Lava"]))
        self.assertIn("light_need", response.context["form"].errors)
        self.assertIn("soils", response.context["form"].errors)
        self.assertFalse(PlantSpecies.objects.exists())

    def test_typed_values_are_kept_after_an_error(self):
        self.client.force_login(self.seller)
        response = self.client.post(self.url, self.valid_data(price="0"))
        self.assertContains(response, 'value="Neem"')
        self.assertContains(response, 'value="Shade &amp; cooling" checked')
        self.assertContains(response, 'value="OUTDOOR" checked')

    # ---------- Price and stock ----------

    def test_price_must_be_more_than_zero(self):
        self.client.force_login(self.seller)
        for price in ("0", "-5", "0.00"):
            with self.subTest(price=price):
                response = self.client.post(self.url, self.valid_data(price=price))
                self.assertContains(response, "Price must be more than Rs 0.")
        self.assertFalse(PlantSpecies.objects.exists())

    def test_stock_cannot_be_negative(self):
        self.client.force_login(self.seller)
        response = self.client.post(self.url, self.valid_data(stock_qty="-1"))
        self.assertContains(response, "Stock must be 0 or more.")
        self.assertFalse(PlantSpecies.objects.exists())

    # ---------- Photo ----------

    def test_jpg_photo_is_saved_and_shown(self):
        self.client.force_login(self.seller)
        self.client.post(self.url, self.valid_data(image=make_image("JPEG", "neem.jpg")))
        listing = PlantSpecies.objects.get()
        self.assertTrue(listing.image.name.startswith("species/neem"))
        response = self.client.get(reverse("plant_detail", args=[listing.pk]))
        self.assertContains(response, f'src="{listing.image.url}"')
        self.assertNotContains(response, "No photo yet")

    def test_png_photo_is_saved(self):
        self.client.force_login(self.seller)
        self.client.post(self.url, self.valid_data(image=make_image("PNG", "neem.png")))
        self.assertTrue(PlantSpecies.objects.get().image.name.endswith(".png"))

    def test_other_files_are_rejected(self):
        self.client.force_login(self.seller)
        files = {
            "gif": make_image("GIF", "neem.gif"),
            "text renamed to jpg": SimpleUploadedFile("neem.jpg", b"not an image", content_type="image/jpeg"),
            "png renamed to gif": make_image("PNG", "neem.gif"),
            "over 2 MB": make_image("PNG", "big.png", size=(1000, 1000), noise=True),
        }
        self.assertGreater(files["over 2 MB"].size, 2 * 1024 * 1024)
        for label, upload in files.items():
            with self.subTest(label):
                upload.seek(0)
                response = self.client.post(self.url, self.valid_data(image=upload))
                self.assertContains(response, "Please use a JPG or PNG under 2 MB.")
                self.assertContains(response, "was not added")
        self.assertFalse(PlantSpecies.objects.exists())


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class PlantDetailTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user("seller@basera.test", "x", full_name="Sam Seller", role=User.Role.SELLER)
        self.buyer = User.objects.create_user("buyer@basera.test", "x", full_name="Bea Buyer", role=User.Role.CUSTOMER)
        self.listing = PlantSpecies.objects.create(
            seller=self.seller, common_name="Kikar", scientific_name="Vachellia nilotica",
            description="Thorny tree.", light_need="Full sun", water_need="Low",
            suitable_soils="Sandy", setting="OUTDOOR", ecological_role="Erosion control",
            price=Decimal("300"), stock_qty=3, is_active=False,
        )

    def test_inactive_listing_is_hidden_from_buyers(self):
        self.client.force_login(self.buyer)
        response = self.client.get(reverse("plant_detail", args=[self.listing.pk]))
        self.assertEqual(response.status_code, 404)

    def test_seller_can_still_see_their_inactive_listing(self):
        self.client.force_login(self.seller)
        response = self.client.get(reverse("plant_detail", args=[self.listing.pk]))
        self.assertContains(response, "Not for sale")
