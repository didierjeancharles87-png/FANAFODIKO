from django.core.validators import RegexValidator
from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Country(TimestampedModel):
    code_alpha2 = models.CharField(max_length=2, unique=True, validators=[RegexValidator(r"^[A-Z]{2}$")])
    code_alpha3 = models.CharField(max_length=3, unique=True, validators=[RegexValidator(r"^[A-Z]{3}$")])
    name_fr = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["name_fr"]
        verbose_name = "pays"
        verbose_name_plural = "pays"

    def __str__(self):
        return f"{self.name_fr} ({self.code_alpha2})"
