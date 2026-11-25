# Généré manuellement pour figer les informations réglementaires à la réservation.
# Cette migration n'a pas été appliquée à PostgreSQL.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="authorization_status",
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="authorization_reference",
            field=models.CharField(blank=True, max_length=160),
        ),
    ]
