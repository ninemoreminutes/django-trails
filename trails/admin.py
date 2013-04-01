# Django
from django.contrib import admin

# Django-Trails
from trails.models import *


class TrailAdmin(admin.ModelAdmin):
    """Admin interface for audit trails."""

    list_display = ('created', 'user', 'action', 'content_type', 'object_id',
                    'content_unicode')
    list_filter = ('user', 'action', 'content_type')
    fields = ('created', 'user', 'action', 'content_type', 'object_id',
              'content_unicode', 'changes')
    readonly_fields = ('created', 'user', 'action', 'content_type',
                       'object_id', 'content_unicode', 'changes')

    def has_add_permission(self, request):
        return False

admin.site.register(Trail, TrailAdmin)
