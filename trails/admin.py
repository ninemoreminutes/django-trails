# Django
from django.contrib import admin
from django.utils.translation import ugettext_lazy as _
try:
    import json
except ImportError:
    from django.utils import simplejson as json

# Django-Trails
from trails.models import Trail
from trails.utils import get_setting


class TrailAdmin(admin.ModelAdmin):
    """Admin interface for audit trails."""

    list_display = ('created', 'get_user_display', 'action', 'content_type',
                    'object_id', 'content_unicode')
    list_filter = ('user', 'action', 'content_type')
    fields = ('created', 'get_user_display', 'action', 'content_type',
              'object_id', 'content_unicode', 'get_data_display',
              'get_render_display')
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def get_user_display(self, obj):
        if obj.user:
            return unicode(obj.user)
        else:
            return obj.user_unicode
    get_user_display.short_description = _('User')

    def get_data_display(self, obj):
        json_data = json.dumps(obj.data, indent=4)
        return '<pre style="display: inline-block; margin: 0; padding: 0; ' + \
               'font-size: 0.9em;">%s</pre>' % json_data
    get_data_display.short_description = _('Data')
    get_data_display.allow_tags = True

    def get_render_display(self, obj):
        return obj.render('html')
    get_render_display.short_description = _('Rendered (HTML)')
    get_render_display.allow_tags = True


admin.site.register(Trail, TrailAdmin)


if get_setting('TRAILS_ADMIN_HISTORY'):

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

    # FIXME: Monkeypatch!
