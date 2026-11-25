from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.core.exceptions import ValidationError

from apps.audit.services import record_event

from .models import AccountProfile, ProfessionalVerificationRequest
from .services import review_professional_request

User = get_user_model()


class AccountProfileInline(admin.StackedInline):
    model = AccountProfile
    can_delete = False
    extra = 0
    fields = ("status", "phone_number", "country", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    inlines = (AccountProfileInline,)
    list_display = (*DjangoUserAdmin.list_display, "account_status")
    list_filter = (*DjangoUserAdmin.list_filter, "account_profile__status")

    @admin.display(description="Statut du compte", ordering="account_profile__status")
    def account_status(self, obj):
        return obj.account_profile.get_status_display()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        record_event(actor=request.user, action="account.updated" if change else "account.created", target=obj, request=request)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        record_event(actor=request.user, action="account_profile.admin_saved", target=form.instance.account_profile, request=request)

    def delete_model(self, request, obj):
        record_event(actor=request.user, action="account.deleted", target=obj, request=request)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for user in queryset.iterator():
            record_event(actor=request.user, action="account.deleted", target=user, request=request)
        super().delete_queryset(request, queryset)


@admin.register(AccountProfile)
class AccountProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "country", "phone_number", "updated_at")
    list_filter = ("status", "country")
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name", "phone_number")
    autocomplete_fields = ("user", "country")
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        record_event(actor=request.user, action="account_profile.updated", target=obj, request=request)

    def delete_model(self, request, obj):
        record_event(actor=request.user, action="account_profile.deleted", target=obj, request=request)
        super().delete_model(request, obj)


@admin.register(ProfessionalVerificationRequest)
class ProfessionalVerificationRequestAdmin(admin.ModelAdmin):
    list_display = ("organization_name", "category", "user", "country", "status", "created_at", "reviewed_by")
    list_filter = ("status", "category", "country", "created_at")
    search_fields = ("organization_name", "license_number", "user__username", "user__email")
    autocomplete_fields = ("user", "country", "reviewed_by")
    readonly_fields = ("created_at", "updated_at", "reviewed_by", "reviewed_at", "status")
    actions = ("approve_selected", "reject_selected")

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Approuver les demandes sélectionnées")
    def approve_selected(self, request, queryset):
        self._review_selected(request, queryset, ProfessionalVerificationRequest.Status.APPROVED)

    @admin.action(description="Refuser les demandes sélectionnées")
    def reject_selected(self, request, queryset):
        self._review_selected(request, queryset, ProfessionalVerificationRequest.Status.REJECTED)

    def _review_selected(self, request, queryset, status):
        updated = 0
        for verification in queryset:
            try:
                review_professional_request(verification=verification, actor=request.user, status=status, request=request)
            except ValidationError as exc:
                self.message_user(request, f"{verification}: {' '.join(exc.messages)}", level=messages.ERROR)
            else:
                updated += 1
        if updated:
            self.message_user(request, f"{updated} demande(s) traitée(s).", level=messages.SUCCESS)

