# Python
import json

# Django
from django.contrib import admin

# Django-Trails
from trails.models import *


class TrailAdmin(admin.ModelAdmin):
    """Admin interface for audit trails."""

    list_display = ('created', 'get_user_display', 'action', 'content_type',
                    'object_id', 'content_unicode')
    list_filter = ('user', 'action', 'content_type')
    fields = ('created', 'get_user_display', 'action', 'content_type',
              'object_id', 'content_unicode', 'get_data_display')
    readonly_fields = ('created', 'get_user_display', 'action', 'content_type',
                       'object_id', 'content_unicode', 'get_data_display')

    def has_add_permission(self, request):
        return False

    def get_user_display(self, obj):
        if obj.user:
            return unicode(obj.user)
        else:
            return obj.user_unicode
    get_user_display.short_description = 'User'

    def get_data_display(self, obj):
        json_data = json.dumps(obj.data, indent=4)
        return '<pre style="display: inline-block; margin: 0; padding: 0; ' + \
               'font-size: 0.9em;">%s</pre>' % json_data
    get_data_display.short_description = 'Data'
    get_data_display.allow_tags = True

admin.site.register(Trail, TrailAdmin)
