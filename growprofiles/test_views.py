"""US-06: create a grow profile and see it listed. US-07: edit it."""

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from catalog.models import Region
from orders.models import Order

from .models import GrowProfile

FAST_HASHERS = override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])

VALID = {
    "name": "Backyard",
    "space_type": "OUTDOOR",
    "sunlight": "FULL_SUN",
    "soil_type": "LOAM",
    "water_availability": "MEDIUM",
    "purpose": "SHADE_COOLING",
}


@FAST_HASHERS
class CreateGrowProfileTests(TestCase):
    url = "/profiles/new/"

    def setUp(self):
        self.region = Region.objects.create(name="Punjab Plains")
        self.user = User.objects.create_user("ana@example.com", "x", full_name="Ana Khan")
        self.client.force_login(self.user)

    def post(self, **changes):
        data = {**VALID, "region": self.region.pk, **changes}
        return self.client.post(self.url, data)

    def test_valid_profile_is_saved_under_the_logged_in_customer_and_listed(self):
        response = self.post()
        self.assertRedirects(response, reverse("grow_profiles"))
        profile = GrowProfile.objects.get()
        self.assertEqual((profile.user, profile.region, profile.name), (self.user, self.region, "Backyard"))
        self.assertEqual(profile.sunlight, "FULL_SUN")
        page = self.client.get(reverse("grow_profiles"))
        self.assertContains(page, "Backyard")
        self.assertContains(page, "Punjab Plains")

    def test_every_missing_field_shows_its_own_error_and_saves_nothing(self):
        response = self.client.post(self.url, {})
        for text in ("Please give this profile a name.", "Please choose a region.",
                     "Please choose indoor or outdoor.", "Please choose your soil.",
                     "Please choose how much water you can provide.",
                     "Please choose what you want the plants to do."):
            self.assertContains(response, text)
        self.assertContains(response, "Please fix the highlighted fields and try again.")
        self.assertEqual(GrowProfile.objects.count(), 0)

    def test_a_failed_save_keeps_what_the_user_typed(self):
        response = self.post(sunlight="")
        self.assertContains(response, 'value="Backyard"')
        self.assertContains(response, 'value="LOAM" checked')

    def test_values_outside_the_fixed_choices_are_rejected(self):
        self.post(sunlight="MOONLIGHT")
        self.assertEqual(GrowProfile.objects.count(), 0)

    def test_region_choices_come_from_the_region_table(self):
        Region.objects.create(name="Potohar Plateau")
        page = self.client.get(self.url)
        self.assertContains(page, "Punjab Plains")
        self.assertContains(page, "Potohar Plateau")

    def test_how_matching_works_draws_each_weight_as_a_bar(self):
        page = self.client.get(self.url)
        self.assertContains(page, "30 pts")
        for width in (91, 76, 61, 45, 30):  # 30, 25, 20, 15, 10 points, drawn out of 33
            self.assertContains(page, f'style="width: {width}%"')
        self.assertEqual(page.content.decode().count('class="bt-weights__bar"'), 5)
        self.assertContains(page, "Your grow profiles are private. Only you can see them.")

    def test_answers_are_cards_with_icons_and_purposes_are_pill_buttons(self):
        page = self.client.get(self.url).content.decode()
        self.assertEqual(page.count('class="bt-choice"'), 2 + 3 + 4 + 3)
        self.assertEqual(page.count('class="bt-pill-choice"'), 6)
        self.assertEqual(page.count('class="bt-icon"'), 2 + 3 + 4 + 3 + 6 + 1)

    def test_the_user_cannot_be_chosen_through_the_form(self):
        other = User.objects.create_user("bo@example.com", "x", full_name="Bo")
        self.post(user=other.pk)
        self.assertEqual(GrowProfile.objects.get().user, self.user)


@FAST_HASHERS
class ProfileListTests(TestCase):
    def setUp(self):
        self.region = Region.objects.create(name="Punjab Plains")
        self.ana = User.objects.create_user("ana@example.com", "x", full_name="Ana Khan")
        self.bo = User.objects.create_user("bo@example.com", "x", full_name="Bo Ali")

    def make(self, user, name):
        return GrowProfile.objects.create(user=user, region=self.region, name=name, space_type="OUTDOOR",
                                          sunlight="FULL_SUN", soil_type="LOAM", water_availability="LOW",
                                          purpose="FOOD")

    def test_empty_list_invites_the_customer_to_create_one(self):
        self.client.force_login(self.ana)
        page = self.client.get(reverse("grow_profiles"))
        self.assertContains(page, "You haven’t created a grow profile yet")
        self.assertContains(page, reverse("grow_profile_new"))

    def test_a_customer_only_sees_their_own_profiles(self):
        self.make(self.ana, "Ana's balcony")
        self.make(self.bo, "Bo's roof")
        self.client.force_login(self.ana)
        page = self.client.get(reverse("grow_profiles"))
        self.assertContains(page, "Ana&#x27;s balcony")
        self.assertNotContains(page, "Bo&#x27;s roof")

    def test_logged_out_visitors_are_sent_to_log_in(self):
        for url in ("/profiles/", "/profiles/new/"):
            self.assertRedirects(self.client.get(url), f"/?next={url}")

    def test_sellers_cannot_use_grow_profiles(self):
        seller = User.objects.create_user("s@example.com", "x", full_name="Sam", role=User.Role.SELLER)
        self.client.force_login(seller)
        self.assertRedirects(self.client.get("/profiles/"), reverse("home"))


@FAST_HASHERS
class EditGrowProfileTests(TestCase):
    """US-07: change a saved profile."""

    def setUp(self):
        self.region = Region.objects.create(name="Punjab Plains")
        self.other_region = Region.objects.create(name="Potohar Plateau")
        self.ana = User.objects.create_user("ana@example.com", "x", full_name="Ana Khan")
        self.bo = User.objects.create_user("bo@example.com", "x", full_name="Bo Ali")
        self.profile = GrowProfile.objects.create(user=self.ana, region=self.region, **VALID)
        self.url = reverse("grow_profile_edit", args=[self.profile.pk])
        self.client.force_login(self.ana)

    def data(self, **changes):
        return {**VALID, "region": self.other_region.pk, **changes}

    def test_the_form_opens_filled_in_with_the_saved_answers(self):
        page = self.client.get(self.url)
        self.assertContains(page, "Edit grow profile")
        self.assertContains(page, 'value="Backyard"')
        self.assertContains(page, f'<option value="{self.region.pk}" selected>Punjab Plains</option>', html=True)
        for code in ("OUTDOOR", "FULL_SUN", "LOAM", "MEDIUM", "SHADE_COOLING"):
            self.assertContains(page, f'value="{code}" checked')
        self.assertContains(page, "Save changes")
        self.assertNotContains(page, "Save grow profile")

    def test_saving_changes_the_same_profile(self):
        response = self.client.post(self.url, self.data(name="Roof", sunlight="SHADE"), follow=True)
        self.assertRedirects(response, reverse("grow_profiles"))
        self.assertContains(response, "Saved your changes to")
        profile = GrowProfile.objects.get()
        self.assertEqual((profile.pk, profile.name, profile.region, profile.sunlight),
                         (self.profile.pk, "Roof", self.other_region, "SHADE"))

    def test_a_failed_save_changes_nothing_and_keeps_what_was_typed(self):
        response = self.client.post(self.url, self.data(name="Roof", soil_type="MOON"))
        self.assertContains(response, "Please choose your soil.")
        self.assertContains(response, 'value="Roof"')
        self.assertContains(response, "Update the answers for Backyard.")
        self.profile.refresh_from_db()
        self.assertEqual((self.profile.name, self.profile.region), ("Backyard", self.region))

    def test_another_customers_profile_answers_404_and_is_untouched(self):
        self.client.force_login(self.bo)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertEqual(self.client.post(self.url, self.data(name="Stolen")).status_code, 404)
        self.profile.refresh_from_db()
        self.assertEqual((self.profile.name, self.profile.user), ("Backyard", self.ana))

    def test_the_owner_cannot_be_changed_through_the_form(self):
        self.client.post(self.url, self.data(user=self.bo.pk))
        self.assertEqual(GrowProfile.objects.get().user, self.ana)

    def test_logged_out_visitors_and_sellers_cannot_edit(self):
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), f"/?next={self.url}")
        seller = User.objects.create_user("s@example.com", "x", full_name="Sam", role=User.Role.SELLER)
        self.client.force_login(seller)
        self.assertRedirects(self.client.post(self.url, self.data(name="Taken")), reverse("home"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.name, "Backyard")

    def test_earlier_orders_stay_as_they_were(self):
        order = Order.objects.create(user=self.ana, grow_profile=self.profile, delivery_name="Ana",
                                     delivery_address="1 Road", city="Lahore", phone="03001234567",
                                     total_amount=500)
        before = Order.objects.filter(pk=order.pk).values().get()
        self.client.post(self.url, self.data(name="Roof"))
        self.assertEqual(Order.objects.filter(pk=order.pk).values().get(), before)

    def test_the_list_and_the_match_results_link_to_the_edit_page(self):
        for page in (reverse("grow_profiles"), reverse("match_profile", args=[self.profile.pk])):
            self.assertContains(self.client.get(page), f'href="{self.url}"')

