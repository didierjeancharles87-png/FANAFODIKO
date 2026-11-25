from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin

from .models import AuditEvent
from .services import record_event


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "actor", "action", "target_type", "target_id", "remote_addr")
    list_filter = ("action", "target_type", "occurred_at")
    search_fields = ("actor__username", "actor__email", "target_type", "target_id", "action")
    date_hierarchy = "occurred_at"
    readonly_fields = tuple(field.name for field in AuditEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(DjangoGroupAdmin):
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        record_event(actor=request.user, action="access_role.updated" if change else "access_role.created", target=obj, request=request)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        record_event(actor=request.user, action="access_role.permissions_updated", target=form.instance, request=request)

    def delete_model(self, request, obj):
        record_event(actor=request.user, action="access_role.deleted", target=obj, request=request)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for group in queryset.iterator():
            record_event(actor=request.user, action="access_role.deleted", target=group, request=request)
        super().delete_queryset(request, queryset)
