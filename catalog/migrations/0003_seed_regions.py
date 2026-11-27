"""Adds the native regions a seller can choose on the Add a plant page (US-13).

Regions already in the database are left as they are.
"""

from django.db import migrations

REGIONS = [
    ("Punjab Plains", "Hot summers, mild winters; fertile alluvial plains."),
    ("Potohar Plateau", "Semi-arid uplands between the Indus and Jhelum."),
    ("Sindh Indus Plains", "Hot and dry lower Indus floodplain."),
    ("Northern Highlands", "Cool to cold mountain valleys of the north."),
    ("Balochistan Uplands", "Dry, rocky plateau with cold winters."),
]


def add_regions(apps, schema_editor):
    Region = apps.get_model("catalog", "Region")
    for name, description in REGIONS:
        Region.objects.get_or_create(name=name, defaults={"description": description})


def remove_regions(apps, schema_editor):
    Region = apps.get_model("catalog", "Region")
    # Only remove regions no listing uses.
    Region.objects.filter(name__in=[n for n, _ in REGIONS], species_regions__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0002_listing_choices_price_gt_0"),
    ]

    operations = [
        migrations.RunPython(add_regions, remove_regions),
    ]
