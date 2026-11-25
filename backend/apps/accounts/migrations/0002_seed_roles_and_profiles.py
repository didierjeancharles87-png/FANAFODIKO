from django.conf import settings
from django.db import migrations


ROLE_GROUPS = ("patient", "professional_pending", "professional_verified")


def create_roles_and_profiles(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    AccountProfile = apps.get_model("accounts", "AccountProfile")

    for role in ROLE_GROUPS:
        Group.objects.get_or_create(name=role)
    for user in User.objects.iterator():
        AccountProfile.objects.get_or_create(user_id=user.pk)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("reference", "0002_seed_madagascar"),
    ]
    operations = [migrations.RunPython(create_roles_and_profiles, migrations.RunPython.noop)]
