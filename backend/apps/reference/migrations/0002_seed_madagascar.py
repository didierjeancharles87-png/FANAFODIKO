from django.db import migrations


def add_madagascar(apps, schema_editor):
    Country = apps.get_model("reference", "Country")
    Country.objects.update_or_create(
        code_alpha2="MG",
        defaults={
            "code_alpha3": "MDG",
            "name_fr": "Madagascar",
            "name_en": "Madagascar",
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("reference", "0001_initial")]
    operations = [migrations.RunPython(add_madagascar, migrations.RunPython.noop)]
