from django.contrib import admin

from apps.audit.services import record_event
from .models import Country


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name_fr", "name_en", "code_alpha2", "code_alpha3", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name_fr", "name_en", "code_alpha2", "code_alpha3")
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        record_event(actor=request.user, action="reference.country.updated" if change else "reference.country.created", target=obj, request=request)

    def delete_model(self, request, obj):
        record_event(actor=request.user, action="reference.country.deleted", target=obj, request=request)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for country in queryset.iterator():
            record_event(actor=request.user, action="reference.country.deleted", target=country, request=request)
        super().delete_queryset(request, queryset)
