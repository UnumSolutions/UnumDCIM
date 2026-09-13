from django.db import migrations, models


def normalize_region(apps, schema_editor):
    Room = apps.get_model("placement", "Room")
    Room.objects.using(schema_editor.connection.alias).filter(
        region="North America"
    ).update(region="AMER")


class Migration(migrations.Migration):
    dependencies = [
        ("placement", "0002_room_city_room_country_room_region_room_room_type_and_more"),
    ]

    operations = [
        # AMER also covers other geography, so rollback retains normalized values.
        migrations.RunPython(normalize_region, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="room",
            name="region",
            field=models.CharField(
                blank=True,
                choices=[("AMER", "AMER"), ("EMEA", "EMEA"), ("APAC", "APAC")],
                default="",
                max_length=100,
            ),
        ),
    ]
