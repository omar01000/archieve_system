from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied

from .models import (
    InternalEntity, InternalDepartment,
    ExternalEntity, ExternalDepartment,
    Document, CustomUser
)

# =========================
# Users1
# =========================
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'username', 'is_staff', 'is_superuser')
    ordering = ('email',)

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "username", "password1", "password2", "groups")}
        ),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            form.base_fields['groups'].queryset = Group.objects.exclude(name='Admin')
        return form

    def has_delete_permission(self, request, obj=None):
        if obj and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)

    def delete_model(self, request, obj):
        if obj.is_superuser and not request.user.is_superuser:
            raise PermissionDenied("لا يمكنك حذف مستخدم SuperAdmin.")
        return super().delete_model(request, obj)


# =========================
# Document
# =========================
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'document_number', 'entity_type', 'document_type', 'uploaded_by', 'last_modified_by', 'uploaded_at')
    list_filter = ('entity_type', 'document_type', 'uploaded_at')
    search_fields = ('title', 'document_number', 'notes')
    readonly_fields = ('uploaded_at','uploaded_by','last_modified_by')

    def save_model(self, request, obj, form, change):
        if not change or not obj.uploaded_by:
            obj.uploaded_by = request.user
        obj.last_modified_by = request.user
        super().save_model(request, obj, form, change)


# =========================
# Internal Entities
# =========================
class InternalEntityAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


class InternalDepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'internal_entity')
    list_filter = ('internal_entity',)
    search_fields = ('name',)


# =========================
# External Entities
# =========================
class ExternalEntityAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


class ExternalDepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'external_entity')
    list_filter = ('external_entity',)
    search_fields = ('name',)


# =========================
# Registering All
# =========================
admin.site.register(Document, DocumentAdmin)
admin.site.register(InternalEntity, InternalEntityAdmin)
admin.site.register(InternalDepartment, InternalDepartmentAdmin)
admin.site.register(ExternalEntity, ExternalEntityAdmin)
admin.site.register(ExternalDepartment, ExternalDepartmentAdmin)
