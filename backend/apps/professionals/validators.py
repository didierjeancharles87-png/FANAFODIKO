import re

from django.core.exceptions import ValidationError


def validate_opening_hours(value):
    if not isinstance(value, dict) or len(value) > 7:
        raise ValidationError("Les horaires doivent être un objet par jour de la semaine.")
    valid_days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
    for day, periods in value.items():
        if day not in valid_days or not isinstance(periods, list) or len(periods) > 4:
            raise ValidationError("Format d’horaires invalide.")
        for period in periods:
            if not isinstance(period, dict) or set(period) != {"open", "close"}:
                raise ValidationError("Chaque plage horaire doit contenir open et close.")
            if any(not isinstance(period[key], str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", period[key]) for key in ("open", "close")):
                raise ValidationError("Les heures doivent suivre le format HH:MM.")


def validate_string_list(value):
    if not isinstance(value, list) or len(value) > 100:
        raise ValidationError("Saisissez une liste de 1 à 100 valeurs.")
    if any(not isinstance(item, str) or not item.strip() or len(item.strip()) > 120 for item in value):
        raise ValidationError("Chaque valeur doit contenir entre 1 et 120 caractères.")


def validate_service_areas(value):
    if not isinstance(value, list) or len(value) > 100:
        raise ValidationError("Saisissez au maximum 100 zones de service.")
    for area in value:
        if not isinstance(area, dict) or set(area) - {"country_code", "region", "city"}:
            raise ValidationError("Une zone doit contenir uniquement country_code, region et city.")
        if any(not isinstance(area.get(key), str) or not area[key].strip() or len(area[key].strip()) > 100 for key in ("country_code", "region", "city")):
            raise ValidationError("Chaque zone doit indiquer un pays, une région et une ville.")
        if not re.fullmatch(r"[A-Z]{2}", area["country_code"]):
            raise ValidationError("Le code pays d’une zone doit être un code ISO alpha-2 en majuscules.")
