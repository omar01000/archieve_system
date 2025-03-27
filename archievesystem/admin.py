from django.contrib import admin
from .models import InternalEntity, InternalDepartment, ExternalEntity, ExternalDepartment, Document

admin.site.register(InternalDepartment)
admin.site.register(InternalEntity)
admin.site.register(ExternalEntity)
admin.site.register(ExternalDepartment)
admin.site.register(Document)