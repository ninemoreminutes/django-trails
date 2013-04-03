# Python
import json

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
              'content_unicode', 'get_changes_display')
    readonly_fields = ('created', 'user', 'action', 'content_type',
                       'object_id', 'content_unicode', 'get_changes_display')

    def has_add_permission(self, request):
        return False

    def get_changes_display(self, obj):
        return '<pre style="display: inline-block; margin: 0; padding: 0; font-size: 0.9em;">%s</pre>' % json.dumps(obj.changes, indent=4)
    get_changes_display.short_description = 'Changes'
    get_changes_display.allow_tags = True

admin.site.register(Trail, TrailAdmin)
