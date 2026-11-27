from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import F
from django.test import TestCase, override_settings

from .models import PlantSpecies, Region, SpeciesRegion

User = get_user_model()

# The real PBKDF2 hasher takes seconds per hash; tests that are not about
# hashing use Django's fast test hasher (PasswordHashingTests uses the real one).
FAST_HASHERS = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])


@FAST_HASHERS
class CatalogConstraintTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            "seller@basera.test", "x", full_name="Sam Seller", role=User.Role.SELLER
        )
        self.species = PlantSpecies.objects.create(
            seller=self.seller, common_name="Neem", scientific_name="Azadirachta indica",
            light_need="Full sun", water_need="Low", suitable_soils="Loam",
            setting=PlantSpecies.Setting.OUTDOOR, price=Decimal("250.00"), stock_qty=5,
        )
        self.region = Region.objects.create(name="Punjab")

    def test_stock_never_below_zero(self):
        # Proposal NFR (Data Integrity): stock shall never fall below zero.
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlantSpecies.objects.filter(pk=self.species.pk).update(stock_qty=F("stock_qty") - 6)
        self.species.refresh_from_db()
        self.assertEqual(self.species.stock_qty, 5)
        # Decrementing to exactly zero is allowed.
        PlantSpecies.objects.filter(pk=self.species.pk).update(stock_qty=F("stock_qty") - 5)
        self.species.refresh_from_db()
        self.assertEqual(self.species.stock_qty, 0)

    def test_price_more_than_zero(self):
        # US-13: price must be greater than 0 (enforced by the database too).
        for price in (Decimal("-0.01"), Decimal("0.00")):
            with self.assertRaises(IntegrityError), transaction.atomic():
                PlantSpecies.objects.filter(pk=self.species.pk).update(price=price)
        PlantSpecies.objects.filter(pk=self.species.pk).update(price=Decimal("0.01"))

    def test_setting_must_be_valid(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlantSpecies.objects.filter(pk=self.species.pk).update(setting="ROOF")
        for value in ("INDOOR", "OUTDOOR", "BOTH"):
            PlantSpecies.objects.filter(pk=self.species.pk).update(setting=value)

    def test_region_name_unique(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Region.objects.create(name="Punjab")

    def test_species_region_pair_unique(self):
        SpeciesRegion.objects.create(species=self.species, region=self.region)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SpeciesRegion.objects.create(species=self.species, region=self.region)
        self.assertEqual(list(self.region.species.all()), [self.species])
