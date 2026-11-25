from django.test import TestCase
from rest_framework.test import APIClient

from .models import Country


class CountryReferenceTests(TestCase):
    def test_country_list_is_public_and_hides_inactive_countries(self):
        Country.objects.get_or_create(code_alpha2="MG", defaults={"code_alpha3": "MDG", "name_fr": "Madagascar", "name_en": "Madagascar"})
        Country.objects.create(code_alpha2="ZZ", code_alpha3="ZZZ", name_fr="Inactif", name_en="Inactive", is_active=False)

        response = APIClient().get("/api/v1/reference/countries/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["code_alpha2"] for item in response.json()], ["MG"])
