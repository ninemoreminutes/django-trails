# Python
from importlib import import_module

# Django
from django.conf import settings
from django.test.signals import setting_changed
from django.utils import six
from django.utils.translation import ugettext_lazy as _


DEFAULT_SETTINGS = {
    # List of strings specifying app_label or app_label.ModelName to include.
    # Shell-style wildcards are supported.
    'INCLUDE_MODELS': (
        '*',
    ),

    # List of strings specifying app_label or app_label.ModelName to exclude.
    # Shell-style wildcards are supported.
    'EXCLUDE_MODELS': (
        'sessions.Session',
        'contenttypes.ContentType',
        'auth.Permission',
        'admin.LogEntry',
    ),

    # List of strings specifying fields to exclude from tracking, in the format
    # "app_label.ModelName.field_name". Shell-style wildcards are supported.
    'EXCLUDE_FIELDS': (
        'auth.User.last_login',
    ),

    # List of strings specifying fields containing sensitive information, in the
    # format "app_label.ModelName.field_name". Shell-style wildcards are
    # supported. Changes to these fields will be tracked, but the value of the
    # SENSITIVE_TEXT setting will be substituted for the actual field value.
    'SENSITIVE_FIELDS': (
        'auth.User.password',
    ),

    # Replacement text to use instead of the actual value for sensitive fields.
    'SENSITIVE_TEXT': '(hidden)',

    # Indicate when sensitive fields contain empty values?
    'SENSITIVE_SHOW_EMPTY': True,

    # TBD: Track changes to models as part of changes related to other models?
    'LINKED_MODELS': {
    },

    # Translatable labels for displaying trails actions.
    'ACTION_LABELS': {
        'add': _('add'),
        'change': _('change'),
        'delete': _('delete'),
        'associate': _('associate'),
        'disassociate': _('disassociate'),
        'login': _('login'),
        'logout': _('logout'),
        'failed-login': _('failed login'),
        'snapshot': _('Snapshot'),
    },

    # String to use for user_text when user is None.
    'NO_USER_TEXT': '(none)',

    # Record trails when request.user is None or not set; usually during
    # management commands or background tasks.
    'TRACK_NO_USER': False,

    # String to use for user_text when user.is_anonymous.
    'ANON_USER_TEXT': '(anonymous)',

    # Record trails when request.user is the anonymous user.
    'TRACK_ANON_USER': True,

    # Record successful user logins.
    'TRACK_LOGIN': True,

    # Record user logouts.
    'TRACK_LOGOUT': True,

    # Record failed user logins.
    'TRACK_FAILED_LOGIN': True,

    # Generate and record a unique ID for each request to associate changes made
    # within the same request.
    'TRACK_REQUEST': False,

    # Record the session ID associated with each trail.
    'TRACK_SESSION': False,

    # Record changes made during migrations.
    'TRACK_MIGRATIONS': False,

    # Record changes made when raw=True (e.g. during fixture loading).
    'TRACK_RAW': False,

    # Record trails to the database.
    'USE_DATABASE': True,

    # Record trails to the logging module.
    'USE_LOGGER': True,

    # Logger name to use for the Python logging module.
    'LOGGER': 'trails',

    # Replace default admin history view with trails history view.
    'ADMIN_HISTORY': False,

    # Pipeline functions to run when recording a trail.
    'PIPELINE': (
        'trails.pipeline.assert_action',
        'trails.pipeline.add_request',
        'trails.pipeline.add_request_uuid',
        'trails.pipeline.add_session',
        'trails.pipeline.add_user',
        'trails.pipeline.check_no_user',
        'trails.pipeline.add_user_is_anonymous',
        'trails.pipeline.check_anonymous_user',
        'trails.pipeline.add_request_text',
        'trails.pipeline.add_session_text',
        'trails.pipeline.add_user_text',
        'trails.pipeline.log_trail',
        'trails.pipeline.create_database_trail',
        'trails.pipeline.create_primary_database_trail_marker',
        'trails.pipeline.create_related_database_trail_markers',
    ),

    # JSON encoder class to use when serializing trail data (model changes).
    'JSON_ENCODER': 'django.core.serializers.json.DjangoJSONEncoder',
}


# List of settings that may be in string import notation.
STRING_IMPORTS = (
    'JSON_ENCODER',
    'PIPELINE',
)

# Set of settings that trigger a reload of the model tracker registry.
REGISTRY_SETTINGS = {
    'INCLUDE_MODELS', 'EXCLUDE_MODELS', 'EXCLUDE_FIELDS', 'SENSITIVE_FIELDS',
    'TRACK_LOGIN', 'TRACK_LOGOUT', 'TRACK_FAILED_LOGIN',
}


class TrailsSettings(object):

    def __init__(self, user_settings=None, defaults=None, string_imports=None):
        if user_settings:
            self._user_settings = user_settings
        self.defaults = defaults or DEFAULT_SETTINGS
        self.string_imports = string_imports or STRING_IMPORTS
        self._cached_attrs = set()

    def _import_from_string(self, value):
        module_path, class_name = value.rsplit('.', 1)
        module = import_module(module_path)
        return getattr(module, class_name)

    def _import_setting_from_string(self, attr, value):
        try:
            if isinstance(value, six.string_types):
                return self._import_from_string(value)
            if isinstance(value, (list, tuple)):
                return [self._import_from_string(item) for item in value]
            return value
        except (ImportError, AttributeError) as e:
            raise ImportError('Could not import {} for trails setting "{}". {}: {}'.format(value, attr, e.__class__.__name__, e))

    @property
    def user_settings(self):
        if not hasattr(self, '_user_settings'):
            self._user_settings = getattr(settings, 'TRAILS', {})
        return self._user_settings

    def __getattr__(self, attr):
        if attr not in self.defaults:
            raise AttributeError('Invalid trails setting: "{}"'.format(attr))
        try:
            value = self.user_settings[attr]
        except KeyError:
            value = self.defaults[attr]
        if attr in self.string_imports:
            value = self._import_setting_from_string(attr, value)
        self._cached_attrs.add(attr)
        setattr(self, attr, value)
        return value

    def reload(self):
        update_registry = bool(REGISTRY_SETTINGS & self._cached_attrs)
        for attr in self._cached_attrs:
            delattr(self, attr)
        self._cached_attrs.clear()
        if hasattr(self, '_user_settings'):
            delattr(self, '_user_settings')
        if update_registry:
            from .registry import registry
            registry.update_from_settings()


trails_settings = TrailsSettings()


def reload_trails_settings(sender, **kwargs):
    from .utils import log_trace
    log_trace('setting changed: %r, %r', sender, kwargs)
    if kwargs['setting'] == 'TRAILS':
        trails_settings.reload()


setting_changed.connect(reload_trails_settings)
