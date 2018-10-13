# Django
from django.apps import AppConfig, apps
from django.conf import settings
from django.utils.translation import ugettext_lazy as _


class TrailsConfig(AppConfig):

    name = 'trails'
    verbose_name = _('Trails')

    def ready(self):
        print('ready?')

        from .registry import registry
        registry.update_from_settings()
