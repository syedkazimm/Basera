"""
Catalog: the ERD's Region, PlantSpecies (Listing) and SpeciesRegion entities
(docs/database/erd_transcription.md).
"""

from django.conf import settings
from django.db import models


class Region(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    climate_zone = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


# Soils and ecological roles a seller can pick (several of each). They are
# stored as comma-separated text in suitable_soils / ecological_role.
SOIL_CHOICES = [
    ("Sandy", "Drains fast"),
    ("Loam", "Balanced, rich"),
    ("Clay", "Holds water"),
    ("Rocky", "Stony, well drained"),
]
ECOLOGICAL_ROLE_CHOICES = [
    "Shade & cooling",
    "Food",
    "Pollinators",
    "Erosion control",
    "Ornamental",
    "Medicinal",
]


class PlantSpecies(models.Model):
    """A species offered for sale by a seller (ERD: "PlantSpecies (Listing)")."""

    class Setting(models.TextChoices):
        INDOOR = "INDOOR", "Indoor"
        OUTDOOR = "OUTDOOR", "Outdoor"
        BOTH = "BOTH", "Both"

    class LightNeed(models.TextChoices):
        FULL_SUN = "Full sun", "Full sun"
        PARTIAL_SHADE = "Partial shade", "Partial shade"
        SHADE = "Shade", "Shade"

    class WaterNeed(models.TextChoices):
        LOW = "Low", "Low"
        MEDIUM = "Medium", "Medium"
        HIGH = "High", "High"

    # PROTECT: a seller who still has listings cannot be hard-deleted (their
    # listings may be referenced by past orders); deactivate the user instead.
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="listings",
    )
    common_name = models.CharField(max_length=150)
    scientific_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    light_need = models.CharField(max_length=50, choices=LightNeed.choices)
    water_need = models.CharField(max_length=50, choices=WaterNeed.choices)
    suitable_soils = models.CharField(max_length=255)
    setting = models.CharField(max_length=10, choices=Setting.choices)
    ecological_role = models.CharField(max_length=255, blank=True)
    is_invasive = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # PositiveIntegerField adds CHECK ("stock_qty" >= 0) in the database, so
    # stock can never go below zero (proposal NFR "Data Integrity").
    stock_qty = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to="species/", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    regions = models.ManyToManyField(
        Region,
        through="SpeciesRegion",
        related_name="species",
        blank=True,
    )

    class Meta:
        verbose_name = "plant species"
        verbose_name_plural = "plant species"
        ordering = ["common_name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(setting__in=["INDOOR", "OUTDOOR", "BOTH"]),
                name="catalog_plantspecies_setting_valid",
            ),
            models.CheckConstraint(
                # US-13: a listing's price must be more than Rs 0.
                condition=models.Q(price__gt=0),
                name="catalog_plantspecies_price_gt_0",
            ),
        ]

    def __str__(self):
        return f"{self.common_name} ({self.scientific_name})"

    @staticmethod
    def _split(text):
        return [part.strip() for part in text.split(",") if part.strip()]

    @property
    def soil_list(self):
        return self._split(self.suitable_soils)

    @property
    def ecological_role_list(self):
        return self._split(self.ecological_role)


class SpeciesRegion(models.Model):
    """Junction table: which regions a species is native to."""

    # CASCADE on both sides: a link row has no meaning once either end is gone.
    species = models.ForeignKey(PlantSpecies, on_delete=models.CASCADE, related_name="species_regions")
    region = models.ForeignKey(Region, on_delete=models.CASCADE, related_name="species_regions")

    class Meta:
        verbose_name = "species region"
        constraints = [
            models.UniqueConstraint(fields=["species", "region"], name="catalog_speciesregion_unique_pair"),
        ]

    def __str__(self):
        return f"{self.species.common_name} in {self.region.name}"
