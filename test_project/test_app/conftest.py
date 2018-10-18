# Python
import copy

# py.test
import pytest

# Django
from django.utils.encoding import force_text


@pytest.fixture
def media_root(settings, tmpdir_factory):
    settings.MEDIA_ROOT = force_text(tmpdir_factory.mktemp('media'))
    return settings.MEDIA_ROOT


@pytest.fixture
def apps(request, db):
    from django.apps import apps
    return apps


@pytest.fixture
def group_model(apps):
    return apps.get_model('auth', 'Group')


@pytest.fixture
def group_instance(group_model):
    return group_model.objects.create(name='group1')


@pytest.fixture
def another_group_instance(group_model):
    return group_model.objects.create(name='group2')


@pytest.fixture
def user_instance(django_user_model, group_instance):
    user = django_user_model.objects.create(username='user1', password='pass1')
    user.groups.add(group_instance)
    return user


@pytest.fixture
def another_user_instance(django_user_model, another_group_instance):
    user = django_user_model.objects.create(username='user2', password='pass2')
    another_group_instance.user_set.add(user)
    return user


@pytest.fixture
def trails_model(apps):
    return apps.get_model('trails', 'Trail')


@pytest.fixture
def allthefields_model(apps):
    return apps.get_model('test_app', 'AllTheFields')


@pytest.fixture
def userprofile_model(apps):
    return apps.get_model('test_app', 'UserProfile')


@pytest.fixture
def useremail_model(apps):
    return apps.get_model('test_app', 'UserEmail')


@pytest.fixture
def apple_model(apps):
    return apps.get_model('test_app', 'Apple')


@pytest.fixture
def apple_model_instance(apple_model):
    return apple_model.objects.create(name='test apple')


@pytest.fixture
def default_trails_settings():
    from trails.settings import trails_settings
    return copy.deepcopy(trails_settings.defaults)


@pytest.fixture
def minimal_trails_settings(default_trails_settings):
    minimal_settings = copy.deepcopy(default_trails_settings)
    minimal_settings.update({
        'INCLUDE_MODELS': (),
        'EXCLUDE_MODELS': (),
        'EXCLUDE_FIELDS': (),
        'SENSITIVE_FIELDS': (),
        'LINKED_MODELS': {},
        'TRACK_NO_USER': False,
        'TRACK_ANON_USER': False,
        'TRACK_LOGIN': False,
        'TRACK_LOGOUT': False,
        'TRACK_FAILED_LOGIN': False,
        'TRACK_REQUEST': False,
        'TRACK_SESSION': False,
        'TRACK_MIGRATIONS': False,
        'TRACK_RAW': False,
        'USE_DATABASE': False,
        'USE_LOGGER': False,
        'ADMIN_HISTORY': False,
        'PIPELINE': [],
    })
    return minimal_settings


@pytest.fixture
def mock_record_trail(mocker):
    return mocker.patch('trails.tracker.record_trail', return_value=None)


class SignalCatcher(object):

    def __init__(self):
        self.reset()

    def __call__(self, sender, **kwargs):
        self.invocations.append((sender, kwargs))

    def __nonzero__(self):
        return bool(self.invocations)

    def get(self, key, default=None):
        for invocation in self.invocations:
            if key in invocation[1]:
                return key
        return default

    def reset(self):
        self.invocations = []


@pytest.fixture
def signal_catcher_class():
    return SignalCatcher


@pytest.fixture
def signal_catcher(signal_catcher_class):
    return signal_catcher_class()
