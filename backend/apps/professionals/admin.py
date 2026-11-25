from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils.html import format_html

from apps.audit.services import record_event
from apps.accounts.models import AccountProfile
from .models import DeliveryDetails, LaboratoryDetails, PharmacyDetails, PractitionerDetails, ProfessionalDocument, ProfessionalProfile
from .services import set_professional_account_status
from .views import stream_document


class PharmacyDetailsInline(admin.StackedInline):
    model = PharmacyDetails
    extra = 0
    can_delete = False


class PractitionerDetailsInline(admin.StackedInline):
    model = PractitionerDetails
    extra = 0
    can_delete = False


class LaboratoryDetailsInline(admin.StackedInline):
    model = LaboratoryDetails
    extra = 0
    can_delete = False


class DeliveryDetailsInline(admin.StackedInline):
    model = DeliveryDetails
    extra = 0
    can_delete = False


@admin.register(ProfessionalProfile)
class ProfessionalProfileAdmin(admin.ModelAdmin):
    list_display = ("legal_name", "category", "account_status", "verification_status", "country", "city", "updated_at")
    list_filter = ("category", "verification_status", "account__status", "country")
    search_fields = ("legal_name", "manager_name", "contact_email", "contact_phone", "account__user__email", "city", "region")
    autocomplete_fields = ("account", "country")
    readonly_fields = ("verification_status", "verification_request", "created_at", "updated_at", "missing_fields")
    actions = ("suspend_selected", "reactivate_selected")

    @admin.display(description="Statut du compte", ordering="account__status")
    def account_status(self, obj):
        return obj.account.get_status_display()

    @admin.display(description="Informations manquantes")
    def missing_fields(self, obj):
        return ", ".join(obj.missing_information) or "Profil complet"

    def get_inlines(self, request, obj=None):
        if obj is None:
            return ()
        if obj.category == "pharmacy":
            return (PharmacyDetailsInline,)
        if obj.category in ("doctor", "dentist"):
            return (PractitionerDetailsInline,)
        if obj.category == "laboratory":
            return (LaboratoryDetailsInline,)
        return (DeliveryDetailsInline,)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        record_event(actor=request.user, action="professional_profile.admin_updated" if change else "professional_profile.admin_created", target=obj, request=request)

    @admin.action(description="Suspendre les comptes professionnels sélectionnés")
    def suspend_selected(self, request, queryset):
        self._set_selected_status(request, queryset, AccountProfile.Status.SUSPENDED)

    @admin.action(description="Réactiver les comptes professionnels sélectionnés")
    def reactivate_selected(self, request, queryset):
        self._set_selected_status(request, queryset, AccountProfile.Status.ACTIVE)

    def _set_selected_status(self, request, queryset, status):
        updated = 0
        for profile in queryset.select_related("account"):
            try:
                set_professional_account_status(profile=profile, actor=request.user, status=status, request=request)
            except ValidationError as exc:
                self.message_user(request, f"{profile}: {' '.join(exc.messages)}", level=messages.ERROR)
            else:
                updated += 1
        if updated:
            self.message_user(request, f"{updated} compte(s) mis à jour.", level=messages.SUCCESS)


@admin.register(ProfessionalDocument)
class ProfessionalDocumentAdmin(admin.ModelAdmin):
    list_display = ("profile", "category", "document_type", "original_filename", "size_bytes", "review_status", "created_at", "private_download")
    list_filter = ("document_type", "review_status", "profile__category", "created_at")
    search_fields = ("profile__legal_name", "profile__account__user__email", "original_filename")
    fields = ("profile", "document_type", "original_filename", "content_type", "size_bytes", "review_status", "created_at", "updated_at", "private_download")
    readonly_fields = ("profile", "document_type", "original_filename", "content_type", "size_bytes", "created_at", "updated_at", "private_download")
    date_hierarchy = "created_at"

    @admin.display(description="Catégorie", ordering="profile__category")
    def category(self, obj):
        return obj.profile.get_category_display()

    @admin.display(description="Téléchargement privé")
    def private_download(self, obj):
        url = reverse("admin:professionals_professionaldocument_download", args=(obj.pk,))
        return format_html('<a href="{}">Télécharger le justificatif</a>', url)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        record_event(actor=request.user, action=f"professional_document.review_{obj.review_status}", target=obj, request=request)

    def get_urls(self):
        custom = [path("<int:object_id>/download/", self.admin_site.admin_view(self.download_view), name="professionals_professionaldocument_download")]
        return custom + super().get_urls()

    def download_view(self, request, object_id):
        document = get_object_or_404(ProfessionalDocument.objects.select_related("profile"), pk=object_id)
        if not self.has_view_permission(request, document):
            raise Http404
        return stream_document(document, actor=request.user, request=request)
