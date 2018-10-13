# Python
import json

# Django
from django.contrib import admin
from django.utils.html import format_html, format_html_join
from django.utils.translation import ugettext_lazy as _

# Django-Trails
from .models import Trail, TrailMarker
from .settings import trails_settings


class TrailMarkerInline(admin.StackedInline):

    model = TrailMarker
    fields = ('rel', 'get_obj_display', 'get_data_display')
    readonly_fields = fields
    extra = 0

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_obj_display(self, obj):
        return obj.obj_display
    get_obj_display.short_description = _('Object')

    def get_data_display(self, obj):
        json_data = json.dumps(obj.data, indent=4)
        return format_html('<pre style="display: inline-block; margin: 0; padding: 0; font-size: 0.9em;">{}</pre>', json_data)
    get_data_display.short_description = _('Data')
    get_data_display.allow_tags = True


class TrailAdmin(admin.ModelAdmin):

    list_display = ('created', 'get_user_display', 'get_action_display',
                    'get_ctypes_display', 'get_markers_display')
    list_filter = ('user', 'action', 'markers__ctype')
    fields = ('created', 'request', 'session', 'get_user_display',
              'get_action_display', 'get_ctypes_display', 'get_markers_display',
              'get_data_display')
    readonly_fields = fields
    inlines = [TrailMarkerInline]
    date_hierarchy = 'created'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related('user')
        qs = qs.prefetch_related('markers', 'markers__ctype')
        return qs

    def has_add_permission(self, request):
        return False

    def get_user_display(self, obj):
        return obj.user_display
    get_user_display.short_description = _('User')

    def get_action_display(self, obj):
        return obj.action_display
    get_action_display.short_description = _('Action')

    def get_ctypes_display(self, obj):
        return obj.ctypes_display
    get_ctypes_display.short_description = _('Type(s)')

    def get_markers_display(self, obj):
        return obj.markers_display
    get_markers_display.short_description = _('Details')

    def get_data_display(self, obj):
        json_data = json.dumps(obj.data, indent=4)
        return format_html('<pre style="display: inline-block; margin: 0; padding: 0; font-size: 0.9em;">{}</pre>', json_data)
    get_data_display.short_description = _('Data')

    def get_render_display(self, obj):
        return obj.render('html')
    get_render_display.short_description = _('Rendered (HTML)')


admin.site.register(Trail, TrailAdmin)


class TrailHistoryMixin(object):
    """Mixin to replace default history view with Trails history."""

    def history_view(self, request, object_id, extra_context=None):
        """Custom admin history view using Trails."""
        # First check if the user can see this history.
        model = self.model
        obj = get_object_or_404(model, pk=unquote(object_id))

        if not self.has_change_permission(request, obj):
            raise PermissionDenied

        # Then get the history for this object.
        opts = model._meta
        app_label = opts.app_label
        #action_list = LogEntry.objects.filter(
        #    object_id=unquote(object_id),
        #    content_type__id__exact=\
        #        ContentType.objects.get_for_model(model).id
        #).select_related().order_by('action_time')

        context = {
            'title': _('Change history: %s') % force_text(obj),
            #'action_list': action_list,
            'module_name': capfirst(force_text(opts.verbose_name_plural)),
            'object': obj,
            'app_label': app_label,
            'opts': opts,
        }
        context.update(extra_context or {})
        return TemplateResponse(request, self.object_history_template or [
            "admin/%s/%s/trails_history.html" % (app_label,
                                                 opts.model_name),
            "admin/%s/trails_history.html" % app_label,
            "admin/trails_history.html"
        ], context, current_app=self.admin_site.name)


if trails_settings.ADMIN_HISTORY:
    pass # FIXME: Monkeypatch!
