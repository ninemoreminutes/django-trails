# Django
from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class TrailsConfig(AppConfig):

    name = 'trails'
    verbose_name = _('Trails')

    def ready(self):
        from .registry import registry
        registry.update_from_settings()
        # FIXME: Check that CRUM middleware is installed?
