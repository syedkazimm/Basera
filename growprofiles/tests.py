"""Tests for grow profiles: who owns them, what protects their data.

The app has no views yet (the page is still a header placeholder), so these
cover the model rules the ERD makes promises about.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django.test import TestCase
from django.utils import timezone

from accounts.tests import FAST_HASHERS
from catalog.models import Region

from .models import GrowProfile

User = get_user_model()


def make_profile(user, region, name="Balcony patch", **overrides):
    data = dict(
        user=user,
        region=region,
        name=name,
        space_type="Balcony",
        sunlight="Full sun",
        soil_type="Loam",
        water_availability="Low",
        purpose="Pollinators",
    )
    data.update(overrides)
    return GrowProfile.objects.create(**data)


@FAST_HASHERS
class GrowProfileTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user("ana@example.com", "x", full_name="Ana Khan")
        self.region = Region.objects.create(name="Punjab Plains", climate_zone="Semi-arid subtropical")

    def test_profile_belongs_to_one_user_and_reads_sensibly(self):
        profile = make_profile(self.customer, self.region, name="Front yard")
        self.assertEqual(profile.user, self.customer)
        self.assertIn("Front yard", str(profile))
        self.assertIn(self.customer.email, str(profile))

    def test_deleting_the_user_takes_their_profiles_with_it(self):
        make_profile(self.customer, self.region)
        self.customer.delete()
        self.assertFalse(GrowProfile.objects.exists())

    def test_a_region_in_use_cannot_be_deleted(self):
        make_profile(self.customer, self.region)
        with self.assertRaises(ProtectedError):
            self.region.delete()
        self.assertTrue(Region.objects.filter(pk=self.region.pk).exists())

    def test_profiles_are_listed_most_recently_changed_first(self):
        older = make_profile(self.customer, self.region, name="Older")
        newer = make_profile(self.customer, self.region, name="Newer")
        # updated_at is auto_now, so set it explicitly to make the order certain.
        now = timezone.now()
        GrowProfile.objects.filter(pk=older.pk).update(updated_at=now - timedelta(days=1))
        GrowProfile.objects.filter(pk=newer.pk).update(updated_at=now)
        self.assertEqual(list(GrowProfile.objects.values_list("name", flat=True)), ["Newer", "Older"])
