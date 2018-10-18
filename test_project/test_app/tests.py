from __future__ import with_statement

# Python
from copy import copy
import datetime
import os
from urllib.parse import urlparse

# py.test
import pytest

# BeautifulSoup4
from bs4 import BeautifulSoup

# Django
from django.test import TestCase
from django.test.signals import template_rendered
from django.test.utils import ContextList
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.core.files.base import ContentFile
from django.db.models.signals import pre_save, post_save
from django.utils.encoding import force_text, smart_text
from django.utils import timezone


# Django-CRUM
from crum import get_current_user, impersonate

# Django-Trails
from trails.models import Trail, TrailMarker
from trails.utils import serialize_instance


class AssertTemplateUsedContext(object):
    # Borrowed from Django >= 1.4 to test using Django 1.3.

    def __init__(self, test_case, template_name):
        self.test_case = test_case
        self.template_name = template_name
        self.rendered_templates = []
        self.rendered_template_names = []
        self.context = ContextList()

    def on_template_render(self, sender, signal, template, context, **kwargs):
        self.rendered_templates.append(template)
        self.rendered_template_names.append(template.name)
        self.context.append(copy(context))

    def test(self):
        return self.template_name in self.rendered_template_names

    def message(self):
        return '%s was not rendered.' % self.template_name

    def __enter__(self):
        template_rendered.connect(self.on_template_render)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        template_rendered.disconnect(self.on_template_render)
        if exc_type is not None:
            return

        if not self.test():
            message = self.message()
            if len(self.rendered_templates) == 0:
                message += ' No template was rendered.'
            else:
                message += ' Following templates were rendered: %s' % (
                    ', '.join(self.rendered_template_names))
            self.test_case.fail(message)


def test_trails_api():
    '''
    Test that expected attributes are available when importing the "API".
    '''
    import trails.api as trails_api
    assert trails_api.Trail
    assert trails_api.record_trail


def test_serialize_instance(user_instance):
    '''
    Test that normal serialization of a model instance works and includes local many-to-many fields.
    '''
    user_dict = serialize_instance(user_instance)
    assert user_dict['__model'] == 'auth.user'
    assert user_dict['__pk'] == user_instance.pk
    assert user_dict['username'] == user_instance.username
    assert set(user_dict['groups']) == set(user_instance.groups.values_list('pk', flat=True))


def test_serialize_instance_in_memory(user_instance):
    '''
    Test that serialization of an in-memory model captures local changes made on the model.
    '''
    user_instance.first_name = 'First'
    user_dict = serialize_instance(user_instance)
    assert user_dict['first_name'] == user_instance.first_name


def test_serialize_instance_before(user_instance):
    '''
    Test that serialization before save retrieves unmodified model from the database.
    '''
    original_last_name = user_instance.last_name
    user_instance.last_name = 'Last'
    user_dict = serialize_instance(user_instance, before=True)
    assert user_dict['last_name'] == original_last_name


def test_serialize_deferred_instance(user_instance, django_user_model):
    '''
    Test that serialization of an instance with a deferred field includes the deferred field.
    '''
    user_deferred = django_user_model.objects.filter(pk=user_instance.pk).defer('first_name').first()
    user_dict = serialize_instance(user_deferred)
    assert 'first_name' in user_dict


def test_serialize_instance_fields(user_instance):
    '''
    Test that serializing an instance with certain fields only serializes the fields specified.
    '''
    user_dict = serialize_instance(user_instance, fields=('username', 'first_name', 'last_name'))
    assert set(user_dict.keys()) == {'__model', '__pk', 'username', 'first_name', 'last_name'}


def test_add_model(settings, minimal_trails_settings, mock_record_trail, allthefields_model):
    '''
    Test that creating an instance results in a call to record_trail with 'add' action and
    instance_data values for all fields.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('test_app.AllTheFields',)})
    settings.TRAILS = minimal_trails_settings
    mock_record_trail.reset_mock()
    allthefields_model.objects.create(
        big_int_val=999999,
        bool_val=True,
        char_val='added',
        date_val=timezone.now().date(),
        decimal_val=22.22,
        email_val='django@trails.com',
        file_path_val='trails.txt',
        float_val=10.15,
        int_val=3,
        generic_ip_val='10.10.10.10',
        null_bool_val=False,
    )
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('add',)
    assert set(mock_record_trail.call_args[1].keys()) == {'instance', 'instance_data'}
    expected_keys = {
        '__model',
        '__pk',
        'big_int_val',
        'bool_val',
        'char_val',
        'date_val',
        'created_dt',
        'modified_dt',
        'decimal_val',
        'email_val',
        'file_path_val',
        'file_val',
        'float_val',
        'image_val',
        'int_val',
        'generic_ip_val',
        'null_bool_val',
        'modified_dt',
    }
    assert set(mock_record_trail.call_args[1]['instance_data'].keys()) == expected_keys
    assert mock_record_trail.call_args[1]['instance_data']['__model']
    assert mock_record_trail.call_args[1]['instance_data']['__pk']
    assert mock_record_trail.call_args[1]['instance_data']['big_int_val'] == 999999
    assert mock_record_trail.call_args[1]['instance_data']['bool_val'] == True
    assert mock_record_trail.call_args[1]['instance_data']['char_val'] == 'added'
    assert mock_record_trail.call_args[1]['instance_data']['created_dt'] is not None
    assert mock_record_trail.call_args[1]['instance_data']['modified_dt'] is not None
    assert mock_record_trail.call_args[1]['instance_data']['date_val'] == timezone.now().date()
    assert mock_record_trail.call_args[1]['instance_data']['decimal_val'] == 22.22
    assert mock_record_trail.call_args[1]['instance_data']['email_val'] == 'django@trails.com'
    assert mock_record_trail.call_args[1]['instance_data']['file_val'] == ''
    assert mock_record_trail.call_args[1]['instance_data']['file_path_val'] == 'trails.txt'
    assert mock_record_trail.call_args[1]['instance_data']['float_val'] == 10.15
    assert mock_record_trail.call_args[1]['instance_data']['image_val'] == ''
    assert mock_record_trail.call_args[1]['instance_data']['int_val'] == 3
    assert mock_record_trail.call_args[1]['instance_data']['generic_ip_val'] == '10.10.10.10'
    assert mock_record_trail.call_args[1]['instance_data']['null_bool_val'] == False


def test_change_model(settings, minimal_trails_settings, mock_record_trail, allthefields_model):
    '''
    Test that changing an instance results in a call to record_trail with 'change' action and
    instance_data populated with all of the changes.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('test_app.AllTheFields',)})
    settings.TRAILS = minimal_trails_settings
    instance = allthefields_model.objects.create()
    mock_record_trail.reset_mock()
    instance.big_int_val = 987654321
    instance.bool_val = True
    instance.char_val = 'changed'
    instance.date_val = timezone.now().date() - datetime.timedelta(days=3)
    instance.decimal_val = 33.33
    instance.email_val = 'trails@django.com'
    instance.file_path_val = 'trails.ini'
    instance.float_val = 15.10
    instance.int_val = 7
    instance.generic_ip_val = '10.20.30.40'
    instance.null_bool_val = True
    instance.save()
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('change',)
    assert set(mock_record_trail.call_args[1].keys()) == {'instance', 'instance_data'}
    expected_keys = {
        'big_int_val',
        'bool_val',
        'char_val',
        'date_val',
        'modified_dt',
        'decimal_val',
        'email_val',
        'file_path_val',
        'float_val',
        'int_val',
        'generic_ip_val',
        'null_bool_val',
    }
    assert set(mock_record_trail.call_args[1]['instance_data'].keys()) == expected_keys
    assert mock_record_trail.call_args[1]['instance_data']['big_int_val'] == (0, 987654321)
    assert mock_record_trail.call_args[1]['instance_data']['bool_val'] == (False, True)
    assert mock_record_trail.call_args[1]['instance_data']['char_val'] == ('', 'changed')
    assert mock_record_trail.call_args[1]['instance_data']['date_val'] == (None, timezone.now().date() - datetime.timedelta(days=3))
    assert mock_record_trail.call_args[1]['instance_data']['modified_dt'][1] > mock_record_trail.call_args[1]['instance_data']['modified_dt'][0]
    assert mock_record_trail.call_args[1]['instance_data']['decimal_val'] == (0, 33.33)
    assert mock_record_trail.call_args[1]['instance_data']['email_val'] == ('', 'trails@django.com')
    assert mock_record_trail.call_args[1]['instance_data']['file_path_val'] == ('', 'trails.ini')
    assert mock_record_trail.call_args[1]['instance_data']['float_val'] == (0.0, 15.10)
    assert mock_record_trail.call_args[1]['instance_data']['int_val'] == (0, 7)
    assert mock_record_trail.call_args[1]['instance_data']['generic_ip_val'] == ('0.0.0.0', '10.20.30.40')
    assert mock_record_trail.call_args[1]['instance_data']['null_bool_val'] == (None, True)


def test_change_model_with_update_fields(settings, minimal_trails_settings, mock_record_trail, allthefields_model):
    '''
    Test that changing an instance using update_fields in the save() call only records the fields specified in
    update_fields.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('test_app.AllTheFields',)})
    settings.TRAILS = minimal_trails_settings
    instance = allthefields_model.objects.create()
    mock_record_trail.reset_mock()
    instance.big_int_val = 987654321
    instance.bool_val = True
    instance.char_val = 'changed'
    instance.save(update_fields=['big_int_val'])
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('change',)
    assert set(mock_record_trail.call_args[1].keys()) == {'instance', 'instance_data'}
    assert set(mock_record_trail.call_args[1]['instance_data'].keys()) == {'big_int_val'}
    assert mock_record_trail.call_args[1]['instance_data']['big_int_val'] == (0, 987654321)
    mock_record_trail.reset_mock()
    instance.save()
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('change',)
    assert set(mock_record_trail.call_args[1].keys()) == {'instance', 'instance_data'}
    assert set(mock_record_trail.call_args[1]['instance_data'].keys()) == {'bool_val', 'char_val', 'modified_dt'}
    assert mock_record_trail.call_args[1]['instance_data']['bool_val'] == (False, True)
    assert mock_record_trail.call_args[1]['instance_data']['char_val'] == ('', 'changed')
    assert mock_record_trail.call_args[1]['instance_data']['modified_dt'][1] > mock_record_trail.call_args[1]['instance_data']['modified_dt'][0]


def test_change_model_file_field(settings, minimal_trails_settings, mock_record_trail, allthefields_model, media_root):
    '''
    Test that changing a file field on an instance records a change to the file path relative to the media root.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('test_app.AllTheFields',)})
    settings.TRAILS = minimal_trails_settings
    instance = allthefields_model.objects.create()
    mock_record_trail.reset_mock()
    instance.file_val.save('test_file.txt', ContentFile('test file content'), save=True)
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('change',)
    assert set(mock_record_trail.call_args[1].keys()) == {'instance', 'instance_data'}
    assert set(mock_record_trail.call_args[1]['instance_data'].keys()) == {'file_val', 'modified_dt'}
    print(mock_record_trail.call_args[1]['instance_data'])
    assert mock_record_trail.call_args[1]['instance_data']['file_val'] == ('', 'files/test_file.txt')
    assert mock_record_trail.call_args[1]['instance_data']['modified_dt'][1] > mock_record_trail.call_args[1]['instance_data']['modified_dt'][0]


def test_change_model_image_field(settings, minimal_trails_settings, mock_record_trail, allthefields_model, media_root):
    '''
    Test that changing an image field on an instance records a change to the image file path relative to the media root.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('test_app.AllTheFields',)})
    settings.TRAILS = minimal_trails_settings
    instance = allthefields_model.objects.create()
    mock_record_trail.reset_mock()
    with open(os.path.join(os.path.dirname(__file__), '..', 'static', 'step.png'), 'rb') as f:
        cf = ContentFile(f.read())
    instance.image_val.save('test_file.png', cf, save=True)
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('change',)
    assert set(mock_record_trail.call_args[1].keys()) == {'instance', 'instance_data'}
    assert set(mock_record_trail.call_args[1]['instance_data'].keys()) == {'image_val', 'modified_dt'}
    print(mock_record_trail.call_args[1]['instance_data'])
    assert mock_record_trail.call_args[1]['instance_data']['image_val'] == ('', 'images/test_file.png')
    assert mock_record_trail.call_args[1]['instance_data']['modified_dt'][1] > mock_record_trail.call_args[1]['instance_data']['modified_dt'][0]


def test_delete_model(settings, minimal_trails_settings, mock_record_trail, allthefields_model):
    '''
    Test that deleting an instance results in a call to record_trail with 'delete' action and
    instance_text set to the string representation of the instance before deletion.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('test_app.AllTheFields',)})
    settings.TRAILS = minimal_trails_settings
    instance = allthefields_model.objects.create()
    instance_text = force_text(instance)
    mock_record_trail.reset_mock()
    instance.delete()
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('delete',)
    assert set(mock_record_trail.call_args[1].keys()) == {'instance', 'instance_text'}
    assert mock_record_trail.call_args[1]['instance_text'] == instance_text


def test_add_model_not_included(settings, minimal_trails_settings, mock_record_trail, allthefields_model):
    '''
    Test that creating an instance of a model not in included models does not result in a call to record_trail.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ()})
    settings.TRAILS = minimal_trails_settings
    mock_record_trail.reset_mock()
    allthefields_model.objects.create()
    assert mock_record_trail.call_count == 0


def test_change_model_not_included(settings, minimal_trails_settings, mock_record_trail, allthefields_model):
    '''
    Test that updating an instance of a model not in included models does not result in a call to record_trail.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ()})
    settings.TRAILS = minimal_trails_settings
    instance = allthefields_model.objects.create()
    mock_record_trail.reset_mock()
    instance.char_val = 'not included'
    instance.save()
    assert mock_record_trail.call_count == 0


def test_delete_model_not_included(settings, minimal_trails_settings, mock_record_trail, allthefields_model):
    '''
    Test that deleting an instance of a model not in included models does not result in a call to record_trail.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ()})
    settings.TRAILS = minimal_trails_settings
    instance = allthefields_model.objects.create()
    mock_record_trail.reset_mock()
    instance.delete()
    assert mock_record_trail.call_count == 0


TEST_MODELS_PATTERNS = [
    ('test_app.AllTheFields',),
    ('test_app.*',),
    ('*.AllTheFields',),
    ('test_?pp.AllTheFields',),
    ('test_app.AllT?eFields',),
    ('*',),
    ('*.*',),
]

@pytest.mark.parametrize('include_models', TEST_MODELS_PATTERNS)
def test_add_model_included(settings, minimal_trails_settings, mock_record_trail, allthefields_model, include_models):
    '''
    Test that creating an instance of a model in included models results in a call to record_trail.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': include_models})
    settings.TRAILS = minimal_trails_settings
    mock_record_trail.reset_mock()
    allthefields_model.objects.create()
    assert mock_record_trail.call_count == 1


@pytest.mark.parametrize('include_models', TEST_MODELS_PATTERNS)
def test_change_model_included(settings, minimal_trails_settings, mock_record_trail, allthefields_model, include_models):
    '''
    Test that updating an instance of a model in included models results in a call to record_trail.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': include_models})
    settings.TRAILS = minimal_trails_settings
    instance = allthefields_model.objects.create()
    mock_record_trail.reset_mock()
    instance.char_val = 'not included'
    instance.save()
    assert mock_record_trail.call_count == 1


@pytest.mark.parametrize('include_models', TEST_MODELS_PATTERNS)
def test_delete_model_included(settings, minimal_trails_settings, mock_record_trail, allthefields_model, include_models):
    '''
    Test that deleting an instance of a model in included models results in a call to record_trail.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': include_models})
    settings.TRAILS = minimal_trails_settings
    instance = allthefields_model.objects.create()
    mock_record_trail.reset_mock()
    instance.delete()
    assert mock_record_trail.call_count == 1


@pytest.mark.parametrize('exclude_models', TEST_MODELS_PATTERNS)
def test_add_model_excluded(settings, minimal_trails_settings, mock_record_trail, allthefields_model, exclude_models):
    '''
    Test that creating an instance of a model in excluded models does not result in a call to record_trail.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('*',), 'EXCLUDE_MODELS': exclude_models})
    settings.TRAILS = minimal_trails_settings
    mock_record_trail.reset_mock()
    allthefields_model.objects.create()
    assert mock_record_trail.call_count == 0


@pytest.mark.parametrize('exclude_models', TEST_MODELS_PATTERNS)
def test_change_model_excluded(settings, minimal_trails_settings, mock_record_trail, allthefields_model, exclude_models):
    '''
    Test that updating an instance of a model in excluded models does not result in a call to record_trail.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('*',), 'EXCLUDE_MODELS': exclude_models})
    settings.TRAILS = minimal_trails_settings
    instance = allthefields_model.objects.create()
    mock_record_trail.reset_mock()
    instance.char_val = 'not included'
    instance.save()
    assert mock_record_trail.call_count == 0


@pytest.mark.parametrize('exclude_models', TEST_MODELS_PATTERNS)
def test_delete_model_excluded(settings, minimal_trails_settings, mock_record_trail, allthefields_model, exclude_models):
    '''
    Test that deleting an instance of a model in excluded models does not result in a call to record_trail.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('*',), 'EXCLUDE_MODELS': exclude_models})
    settings.TRAILS = minimal_trails_settings
    instance = allthefields_model.objects.create()
    mock_record_trail.reset_mock()
    instance.delete()
    assert mock_record_trail.call_count == 0


TEST_EXCLUDE_FIELDS_PATTERNS = [
    ('*char_val',),
    ('*.char_val',),
    ('*.*.char_val',),
    ('test_app.*.char_val',),
    ('*.AllTheFields.char_val',),
    ('test_app.AllTheFields.char_val',),
    ('test_ap?.AllTheFields.char_val',),
    ('test_app.AllTheFie?ds.char_val',),
    ('test_app.AllTheFields.cha?_val',),
    ('test_app.AllTheFie?ds.char*',),
]


@pytest.mark.parametrize('exclude_fields', TEST_EXCLUDE_FIELDS_PATTERNS)
def test_add_model_with_exclude_fields(settings, minimal_trails_settings, mock_record_trail, allthefields_model, exclude_fields):
    '''
    Test that adding an instance of a model with excluded fields does not record the excluded field.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('test_app.AllTheFields',), 'EXCLUDE_FIELDS': exclude_fields})
    settings.TRAILS = minimal_trails_settings
    mock_record_trail.reset_mock()
    allthefields_model.objects.create(
        big_int_val=999999,
        char_val='added',
    )
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('add',)
    assert set(mock_record_trail.call_args[1].keys()) == {'instance', 'instance_data'}
    expected_keys = {
        '__model',
        '__pk',
        'big_int_val',
        'bool_val',
        'date_val',
        'created_dt',
        'modified_dt',
        'decimal_val',
        'email_val',
        'file_path_val',
        'file_val',
        'float_val',
        'image_val',
        'int_val',
        'generic_ip_val',
        'null_bool_val',
        'modified_dt',
    }
    assert set(mock_record_trail.call_args[1]['instance_data'].keys()) == expected_keys
    assert mock_record_trail.call_args[1]['instance_data']['__model']
    assert mock_record_trail.call_args[1]['instance_data']['__pk']
    assert mock_record_trail.call_args[1]['instance_data']['big_int_val'] == 999999
    assert mock_record_trail.call_args[1]['instance_data']['bool_val'] == False
    assert mock_record_trail.call_args[1]['instance_data']['created_dt'] is not None
    assert mock_record_trail.call_args[1]['instance_data']['modified_dt'] is not None
    assert mock_record_trail.call_args[1]['instance_data']['date_val'] == None
    assert mock_record_trail.call_args[1]['instance_data']['decimal_val'] == 0
    assert mock_record_trail.call_args[1]['instance_data']['email_val'] == ''
    assert mock_record_trail.call_args[1]['instance_data']['file_val'] == ''
    assert mock_record_trail.call_args[1]['instance_data']['file_path_val'] == ''
    assert mock_record_trail.call_args[1]['instance_data']['float_val'] == 0.0
    assert mock_record_trail.call_args[1]['instance_data']['image_val'] == ''
    assert mock_record_trail.call_args[1]['instance_data']['int_val'] == 0
    assert mock_record_trail.call_args[1]['instance_data']['generic_ip_val'] == '0.0.0.0'
    assert mock_record_trail.call_args[1]['instance_data']['null_bool_val'] == None


@pytest.mark.parametrize('exclude_fields', TEST_EXCLUDE_FIELDS_PATTERNS)
def test_change_model_with_excluded_fields(settings, minimal_trails_settings, mock_record_trail, allthefields_model, exclude_fields):
    '''
    Test that changing an instance results in a call to record_trail with 'change' action and
    instance_data populated with all of the changes.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('test_app.AllTheFields',), 'EXCLUDE_FIELDS': exclude_fields})
    settings.TRAILS = minimal_trails_settings
    instance = allthefields_model.objects.create()
    mock_record_trail.reset_mock()
    instance.big_int_val = 987654321
    instance.char_val = 'changed'
    instance.save()
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('change',)
    assert set(mock_record_trail.call_args[1].keys()) == {'instance', 'instance_data'}
    expected_keys = {
        'big_int_val',
        'modified_dt',
    }
    assert set(mock_record_trail.call_args[1]['instance_data'].keys()) == expected_keys
    assert mock_record_trail.call_args[1]['instance_data']['big_int_val'] == (0, 987654321)
    assert mock_record_trail.call_args[1]['instance_data']['modified_dt'][1] > mock_record_trail.call_args[1]['instance_data']['modified_dt'][0]


TEST_EXCLUDE_FIELDS_PATTERNS = [
    ('*char_val',),
    ('*.char_val',),
    ('*.*.char_val',),
    ('test_app.*.char_val',),
    ('*.AllTheFields.char_val',),
    ('test_app.AllTheFields.char_val',),
    ('test_ap?.AllTheFields.char_val',),
    ('test_app.AllTheFie?ds.char_val',),
    ('test_app.AllTheFields.cha?_val',),
    ('test_app.AllTheFie?ds.char*',),
]


@pytest.mark.parametrize('exclude_fields', TEST_EXCLUDE_FIELDS_PATTERNS)
def test_add_model_with_exclude_fields(settings, minimal_trails_settings, mock_record_trail, allthefields_model, exclude_fields):
    '''
    Test that adding an instance of a model with excluded fields does not record the excluded field.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('test_app.AllTheFields',), 'EXCLUDE_FIELDS': exclude_fields})
    settings.TRAILS = minimal_trails_settings
    mock_record_trail.reset_mock()
    allthefields_model.objects.create(
        big_int_val=999999,
        char_val='added',
    )
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('add',)
    assert set(mock_record_trail.call_args[1].keys()) == {'instance', 'instance_data'}
    expected_keys = {
        '__model',
        '__pk',
        'big_int_val',
        'bool_val',
        'date_val',
        'created_dt',
        'modified_dt',
        'decimal_val',
        'email_val',
        'file_path_val',
        'file_val',
        'float_val',
        'image_val',
        'int_val',
        'generic_ip_val',
        'null_bool_val',
        'modified_dt',
    }
    assert set(mock_record_trail.call_args[1]['instance_data'].keys()) == expected_keys
    assert mock_record_trail.call_args[1]['instance_data']['__model']
    assert mock_record_trail.call_args[1]['instance_data']['__pk']
    assert mock_record_trail.call_args[1]['instance_data']['big_int_val'] == 999999
    assert mock_record_trail.call_args[1]['instance_data']['bool_val'] == False
    assert mock_record_trail.call_args[1]['instance_data']['created_dt'] is not None
    assert mock_record_trail.call_args[1]['instance_data']['modified_dt'] is not None
    assert mock_record_trail.call_args[1]['instance_data']['date_val'] == None
    assert mock_record_trail.call_args[1]['instance_data']['decimal_val'] == 0
    assert mock_record_trail.call_args[1]['instance_data']['email_val'] == ''
    assert mock_record_trail.call_args[1]['instance_data']['file_val'] == ''
    assert mock_record_trail.call_args[1]['instance_data']['file_path_val'] == ''
    assert mock_record_trail.call_args[1]['instance_data']['float_val'] == 0.0
    assert mock_record_trail.call_args[1]['instance_data']['image_val'] == ''
    assert mock_record_trail.call_args[1]['instance_data']['int_val'] == 0
    assert mock_record_trail.call_args[1]['instance_data']['generic_ip_val'] == '0.0.0.0'
    assert mock_record_trail.call_args[1]['instance_data']['null_bool_val'] == None


@pytest.mark.parametrize('exclude_fields', TEST_EXCLUDE_FIELDS_PATTERNS)
def test_change_model_with_excluded_fields(settings, minimal_trails_settings, mock_record_trail, allthefields_model, exclude_fields):
    '''
    Test that changing an instance results in a call to record_trail with 'change' action and
    instance_data populated with all of the changes.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('test_app.AllTheFields',), 'EXCLUDE_FIELDS': exclude_fields})
    settings.TRAILS = minimal_trails_settings
    instance = allthefields_model.objects.create()
    mock_record_trail.reset_mock()
    instance.big_int_val = 987654321
    instance.char_val = 'changed'
    instance.save()
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('change',)
    assert set(mock_record_trail.call_args[1].keys()) == {'instance', 'instance_data'}
    expected_keys = {
        'big_int_val',
        'modified_dt',
    }
    assert set(mock_record_trail.call_args[1]['instance_data'].keys()) == expected_keys
    assert mock_record_trail.call_args[1]['instance_data']['big_int_val'] == (0, 987654321)
    assert mock_record_trail.call_args[1]['instance_data']['modified_dt'][1] > mock_record_trail.call_args[1]['instance_data']['modified_dt'][0]


def test_add_o2o_model(settings, minimal_trails_settings, mock_record_trail, user_instance, userprofile_model):
    '''
    Test that adding an instance with a one-to-one field results in a call to record_trail with 'add' action,
    instance_data set for all fields with the one-to-one field specified as field_id, and the related object
    captured in related_instances.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('auth.User', 'test_app.UserProfile')})
    settings.TRAILS = minimal_trails_settings
    mock_record_trail.reset_mock()
    userprofile = userprofile_model.objects.create(user=user_instance, nickname='uno')
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('add',)
    assert set(mock_record_trail.call_args[1].keys()) == {'instance', 'instance_data', 'related_instances'}
    assert mock_record_trail.call_args[1]['instance'] == userprofile
    assert set(mock_record_trail.call_args[1]['instance_data'].keys()) == {'__model', '__pk', 'user_id', 'nickname'}
    assert mock_record_trail.call_args[1]['instance_data']['user_id'] == user_instance.pk
    assert mock_record_trail.call_args[1]['instance_data']['nickname'] == 'uno'
    assert mock_record_trail.call_args[1]['related_instances'] == [{'rel': 'user', 'instance': user_instance}]


def test_change_o2o_model(settings, minimal_trails_settings, mock_record_trail, user_instance, another_user_instance, userprofile_model):
    '''
    Test that changing an instance with a one-to-one field results in a call to record_trail with 'change' action,
    instance_data set for all fields changed with the one-to-one field specified as field_id, and the related objects
    before and after captured in related_instances.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('auth.User', 'test_app.UserProfile')})
    settings.TRAILS = minimal_trails_settings
    userprofile = userprofile_model.objects.create(user=user_instance, nickname='uno')
    mock_record_trail.reset_mock()
    userprofile.user = another_user_instance
    userprofile.nickname = 'dos'
    userprofile.save()
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('change',)
    assert set(mock_record_trail.call_args[1].keys()) == {'instance', 'instance_data', 'related_instances'}
    assert mock_record_trail.call_args[1]['instance'] == userprofile
    assert set(mock_record_trail.call_args[1]['instance_data'].keys()) == {'user_id', 'nickname'}
    assert mock_record_trail.call_args[1]['instance_data']['user_id'] == (user_instance.pk, another_user_instance.pk)
    assert mock_record_trail.call_args[1]['instance_data']['nickname'] == ('uno', 'dos')
    assert mock_record_trail.call_args[1]['related_instances'] == [{'rel': '-user', 'instance': user_instance}, {'rel': '+user', 'instance': another_user_instance}]


def test_delete_o2o_model(settings, minimal_trails_settings, mock_record_trail, user_instance, userprofile_model):
    '''
    Test that deleting an instance with a one-to-one field results in a call to record_trail with 'delete' action
    and instance_text set to the string representation of the instance before deletion.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('auth.User', 'test_app.UserProfile')})
    settings.TRAILS = minimal_trails_settings
    userprofile = userprofile_model.objects.create(user=user_instance, nickname='uno')
    userprofile_text = force_text(userprofile)
    mock_record_trail.reset_mock()
    userprofile.delete()
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('delete',)
    assert set(mock_record_trail.call_args[1].keys()) == {'instance', 'instance_text'}
    assert mock_record_trail.call_args[1]['instance_text'] == userprofile_text


def test_delete_o2o_related_model_cascade(settings, minimal_trails_settings, mock_record_trail, user_instance, userprofile_model):
    '''
    Test that deleting the related model for an instance with a one-to-one field results in two calls to
    record_trail with 'delete' action. The first call will be for the instance with the one-to-one field
    and the second call for the related instance.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('auth.User', 'test_app.UserProfile')})
    settings.TRAILS = minimal_trails_settings
    user_instance_text = force_text(user_instance)
    userprofile = userprofile_model.objects.create(user=user_instance, nickname='uno')
    userprofile_text = force_text(userprofile)
    mock_record_trail.reset_mock()
    user_instance.delete()
    assert mock_record_trail.call_count == 2
    assert mock_record_trail.call_args_list[0][0] == ('delete',)
    assert set(mock_record_trail.call_args_list[0][1].keys()) == {'instance', 'instance_text'}
    assert mock_record_trail.call_args_list[0][1]['instance_text'] == userprofile_text
    assert mock_record_trail.call_args_list[1][0] == ('delete',)
    assert set(mock_record_trail.call_args_list[1][1].keys()) == {'instance', 'instance_text'}
    assert mock_record_trail.call_args_list[1][1]['instance_text'] == user_instance_text


def test_add_fk_model(settings, minimal_trails_settings, mock_record_trail, user_instance, useremail_model):
    '''
    Test that adding an instance with a foreign key field that can be null results in a call to
    record_trail with 'add' action, instance_data set for all fields with the one-to-one field specified as
    field_id, and the related object captured in related_instances.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('auth.User', 'test_app.UserEmail')})
    settings.TRAILS = minimal_trails_settings
    mock_record_trail.reset_mock()
    useremail = useremail_model.objects.create(user=user_instance, email='test@trails.com')
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('add',)
    assert set(mock_record_trail.call_args[1].keys()) == {'instance', 'instance_data', 'related_instances'}
    assert mock_record_trail.call_args[1]['instance'] == useremail
    assert set(mock_record_trail.call_args[1]['instance_data'].keys()) == {'__model', '__pk', 'user_id', 'email'}
    assert mock_record_trail.call_args[1]['instance_data']['user_id'] == user_instance.pk
    assert mock_record_trail.call_args[1]['instance_data']['email'] == 'test@trails.com'
    assert mock_record_trail.call_args[1]['related_instances'] == [{'rel': 'user', 'instance': user_instance}]


def test_add_fk_model_null(settings, minimal_trails_settings, mock_record_trail, useremail_model):
    '''
    Test that adding an instance with a foreign key field set to null results in a call to
    record_trail with 'add' action, instance_data set for all fields with the one-to-one field specified as
    field_id, no related objects captured in related_instances.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('auth.User', 'test_app.UserEmail')})
    settings.TRAILS = minimal_trails_settings
    mock_record_trail.reset_mock()
    useremail = useremail_model.objects.create(email='test@trails.com')
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('add',)
    assert set(mock_record_trail.call_args[1].keys()) == {'instance', 'instance_data'}
    assert mock_record_trail.call_args[1]['instance'] == useremail
    assert set(mock_record_trail.call_args[1]['instance_data'].keys()) == {'__model', '__pk', 'user_id', 'email'}
    assert mock_record_trail.call_args[1]['instance_data']['user_id'] == None
    assert mock_record_trail.call_args[1]['instance_data']['email'] == 'test@trails.com'


def test_change_fk_model_to_null(settings, minimal_trails_settings, mock_record_trail, user_instance, useremail_model):
    '''
    Test that changing an instance with a foreign key field by setting it to null results in a call to
    record_trail with 'change' action, instance_data set for all fields with the one-to-one field specified as
    field_id, and the previous related object captured in related_instances.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('auth.User', 'test_app.UserEmail')})
    settings.TRAILS = minimal_trails_settings
    useremail = useremail_model.objects.create(user=user_instance, email='test@trails.com')
    mock_record_trail.reset_mock()
    useremail.user = None
    useremail.save()
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('change',)
    assert set(mock_record_trail.call_args[1].keys()) == {'instance', 'instance_data', 'related_instances'}
    assert mock_record_trail.call_args[1]['instance'] == useremail
    assert set(mock_record_trail.call_args[1]['instance_data'].keys()) == {'user_id'}
    assert mock_record_trail.call_args[1]['instance_data']['user_id'] == (user_instance.pk, None)
    assert mock_record_trail.call_args[1]['related_instances'] == [{'rel': '-user', 'instance': user_instance}]


def test_change_fk_model_from_null(settings, minimal_trails_settings, mock_record_trail, user_instance, useremail_model):
    '''
    Test that changing an instance with a foreign key field by setting it to a value from null results in a call to
    record_trail with 'change' action, instance_data set for all fields with the one-to-one field specified as
    field_id, and the new related object captured in related_instances.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('auth.User', 'test_app.UserEmail')})
    settings.TRAILS = minimal_trails_settings
    useremail = useremail_model.objects.create(email='test@trails.com')
    mock_record_trail.reset_mock()
    useremail.user = user_instance
    useremail.save()
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('change',)
    assert set(mock_record_trail.call_args[1].keys()) == {'instance', 'instance_data', 'related_instances'}
    assert mock_record_trail.call_args[1]['instance'] == useremail
    assert set(mock_record_trail.call_args[1]['instance_data'].keys()) == {'user_id'}
    assert mock_record_trail.call_args[1]['instance_data']['user_id'] == (None, user_instance.pk)
    assert mock_record_trail.call_args[1]['related_instances'] == [{'rel': '+user', 'instance': user_instance}]


@pytest.mark.xfail
def test_delete_fk_related_model_set_null(settings, minimal_trails_settings, mock_record_trail, user_instance, useremail_model):
    '''
    Test that deleting the related model for an instance with a foreign key field results in two calls to
    record_trail. The first call will be a 'change' action for the instance with the foreign key field,
    and the second call will be a 'delete' action for the related instance.
    '''
    minimal_trails_settings.update({'INCLUDE_MODELS': ('auth.User', 'test_app.UserEmail')})
    settings.TRAILS = minimal_trails_settings
    user_instance_text = force_text(user_instance)
    user_instance_pk = user_instance.pk
    useremail = useremail_model.objects.create(user=user_instance, email='test@trails.com')
    mock_record_trail.reset_mock()
    user_instance.delete()
    print(mock_record_trail.call_args_list)
    useremail.refresh_from_db()
    assert useremail.user == None
    # FIXME: Uses batch_update so the change isn't captured. Ugh.
    assert mock_record_trail.call_count == 2
    assert mock_record_trail.call_args_list[0][0] == ('change',)
    assert set(mock_record_trail.call_args_list[0][1].keys()) == {'instance', 'instance_data', 'related_instances'}
    assert mock_record_trail.call_args_list[0][1]['instance'] == useremail
    assert mock_record_trail.call_args_list[0][1]['instance_data'] == {'user_id': (user_instance_pk, None)}
    assert mock_record_trail.call_args_list[0][1]['related_instances'] == [{'rel': '-user', 'instance': user_instance}]
    assert mock_record_trail.call_args_list[1][0] == ('delete',)
    assert set(mock_record_trail.call_args_list[1][1].keys()) == {'instance', 'instance_text'}
    assert mock_record_trail.call_args_list[1][1]['instance_text'] == user_instance_text




def test_m2m(user_instance, group_instance, another_user_instance, another_group_instance):
    user_instance.groups.remove(group_instance)
    another_group_instance.user_set.remove(another_user_instance)
    user_instance.groups.add(group_instance, another_group_instance)
    user_instance.groups.add(group_instance)
    user_instance.groups.clear()
    assert False



def test_track_user_login(settings, minimal_trails_settings, mock_record_trail, client, user_instance):
    '''
    Test that trail is recorded for user login.
    '''
    minimal_trails_settings.update({'TRACK_LOGIN': True})
    settings.TRAILS = minimal_trails_settings
    mock_record_trail.reset_mock()
    client.force_login(user_instance)
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('login',)
    assert set(mock_record_trail.call_args[1].keys()) == {'user', 'request'}
    assert mock_record_trail.call_args[1]['user'] == user_instance


def test_track_user_login_disabled(settings, minimal_trails_settings, mock_record_trail, client, user_instance):
    '''
    Test that trail is not recorded for login with tracking disabled.
    '''
    minimal_trails_settings.update({'TRACK_LOGIN': False})
    settings.TRAILS = minimal_trails_settings
    mock_record_trail.reset_mock()
    client.force_login(user_instance)
    assert not mock_record_trail.called


def test_track_user_logout(settings, minimal_trails_settings, mock_record_trail, client, user_instance):
    '''
    Test that trail is recorded for user logout.
    '''
    minimal_trails_settings.update({'TRACK_LOGOUT': True})
    settings.TRAILS = minimal_trails_settings
    client.force_login(user_instance)
    mock_record_trail.reset_mock()
    client.logout()
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('logout',)
    assert set(mock_record_trail.call_args[1].keys()) == {'user', 'request'}
    assert mock_record_trail.call_args[1]['user'] == user_instance


def test_track_user_logout_without_login(settings, minimal_trails_settings, mock_record_trail, client, user_instance):
    '''
    Test that trail is recorded for user logout even if user hasn't logged in.
    '''
    minimal_trails_settings.update({'TRACK_LOGOUT': True})
    settings.TRAILS = minimal_trails_settings
    mock_record_trail.reset_mock()
    client.logout()
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('logout',)
    assert set(mock_record_trail.call_args[1].keys()) == {'user', 'request'}
    assert mock_record_trail.call_args[1]['user'] is None


def test_track_user_logout_disabled(settings, minimal_trails_settings, mock_record_trail, client, user_instance):
    '''
    Test that trail is not recorded for user logout with tracking disabled.
    '''
    minimal_trails_settings.update({'TRACK_LOGOUT': False})
    settings.TRAILS = minimal_trails_settings
    client.force_login(user_instance)
    mock_record_trail.reset_mock()
    client.logout()
    assert not mock_record_trail.called


def test_track_user_failed_login(settings, minimal_trails_settings, mock_record_trail, client, user_instance):
    '''
    Test that trail is recorded for a failed user login.
    '''
    minimal_trails_settings.update({'TRACK_FAILED_LOGIN': True})
    settings.TRAILS = minimal_trails_settings
    mock_record_trail.reset_mock()
    client.login(username=user_instance.username, password='badpass')
    assert mock_record_trail.call_count == 1
    assert mock_record_trail.call_args[0] == ('failed-login',)
    assert set(mock_record_trail.call_args[1].keys()) == {'data', 'request'}
    assert mock_record_trail.call_args[1]['data']['username'] == user_instance.username
    assert '****' in mock_record_trail.call_args[1]['data']['password']


def test_track_user_failed_login_disabled(settings, minimal_trails_settings, mock_record_trail, client, user_instance):
    '''
    Test that trail is not recorded for a failed user login when tracking is disabled.
    '''
    minimal_trails_settings.update({'TRACK_FAILED_LOGIN': False})
    settings.TRAILS = minimal_trails_settings
    mock_record_trail.reset_mock()
    client.login(username=user_instance.username, password='badpass')
    assert not mock_record_trail.called


@pytest.mark.xfail(raises=NotImplementedError)
def test_trail_model():
    raise NotImplementedError
    pre_tsh = TestSignalHandler()
    pre_save.connect(pre_tsh)
    post_tsh = TestSignalHandler()
    post_save.connect(post_tsh)
    # Content unicode should be set automatically.
    trail = Trail.objects.create(**{
        'user': self.superuser,
        'user_unicode': unicode(self.superuser),
        'content_type': ContentType.objects.get_for_model(self.superuser),
        'object_id': self.superuser.pk,
        'action': 'some other action',
    })
    self.assertTrue(trail.content_unicode)
    self.assertTrue(pre_tsh)
    self.assertTrue(post_tsh)
    # Model should never save again after initially created.
    pre_tsh.reset()
    post_tsh.reset()
    self.assertFalse(pre_tsh)
    self.assertFalse(post_tsh)
    trail.save()
    self.assertFalse(pre_tsh)
    self.assertFalse(post_tsh)


@pytest.mark.xfail(raises=NotImplementedError)
def test_trails_manager():
    raise NotImplementedError
    with impersonate(self.superuser):
        self.create_test_users_and_groups()
    # All normal users.
    instances = self.users
    trails = Trail.objects.for_models(*instances)
    self.assertTrue(trails.count())
    for trail in trails:
        self.assertTrue(trail.content_object in instances)
    # All normal groups.
    instances = self.groups
    trails = Trail.objects.for_models(*instances)
    self.assertTrue(trails.count())
    for trail in trails:
        self.assertTrue(trail.content_object in instances)
    # Mix of user and group.
    instances = [self.users[0], self.groups[0]]
    trails = Trail.objects.for_models(*instances)
    self.assertTrue(trails.count())
    for trail in trails:
        self.assertTrue(trail.content_object in instances)
    # Multiples of one type, mixed with another type.
    instances = self.users + [self.groups[0]]
    trails = Trail.objects.for_models(*instances)
    self.assertTrue(trails.count())
    for trail in trails:
        self.assertTrue(trail.content_object in instances)
    # Passing None as an instance should work, but return no trails.
    instances = [None]
    trails = Trail.objects.for_models(*instances)
    self.assertFalse(trails.count())
    # Passing a single Queryset instead of a list.
    instances = Group.objects.all()
    trails = Trail.objects.for_models(*instances)
    self.assertTrue(trails.count())
    for trail in trails:
        self.assertTrue(trail.content_object in instances)
    # Passing a list of Querysets.
    instances = [Group.objects.all(), User.objects.all()]
    trails = Trail.objects.for_models(*instances)
    self.assertTrue(trails.count())
    for trail in trails:
        self.assertTrue(trail.content_object in instances[0] or
                        trail.content_object in instances[1])


@pytest.mark.xfail(raises=NotImplementedError)
def test_trails_render():
    raise NotImplementedError
    # Create test user/group data with changes/deletes.
    with impersonate(self.superuser):
        self.create_test_users_and_groups()
        user = self.users[0]
        user.first_name = 'Firsty'
        user.last_name = 'The Userman'
        user.save()
        user = self.users[1]
        user.delete()
        group = self.groups[0]
        group.name = 'Grouper Gropers'
        group.save()
        group = self.groups[1]
        group.delete()
        site = Site.objects.get_current()
        site.name = 'example.org'
        site.domain = 'example.org'
        site.save()
    # Verify that each trail is rendered with the appropriate template.
    for trail in Trail.objects.all():
        template_key = (trail.content_type.model_class(), trail.action)
        html_template = {
            (Group, 'add'):     'trails/auth/group/add.html',
            (Group, 'change'):  'trails/auth/group/default.html',
            (Group, 'delete'):  'trails/auth/group/default.html',
            (User, 'add'):      'trails/auth/default.html',
            (User, 'change'):   'trails/auth/user/change.html',
            (User, 'delete'):   'trails/auth/delete.html',
        }.get(template_key, 'trails/default.html')
        txt_template = {
            (Site, 'change'):   'trails/sites/change.txt',
        }.get(template_key, 'trails/_default.txt')
        with AssertTemplateUsedContext(self, html_template):
            trail.render('html')
        with AssertTemplateUsedContext(self, txt_template):
            trail.render('txt')


@pytest.mark.xfail(raises=NotImplementedError)
def test_trails_admin():
    raise NotImplementedError
    app_label = Trail._meta.app_label
    model_name = (getattr(Trail._meta, 'model_name', None) or
                  getattr(Trail._meta, 'module_name', None))
    self.assertTrue(model_name)
    self.client.login(username=self.superuser.username,
                      password=self.superuser_password)
    with impersonate(self.superuser):
        self.create_test_users_and_groups()
    with impersonate(self.users[0]):
        self.create_test_users_and_groups(prefix='extra')
    with impersonate(self.superuser):
        self.users[0].delete()
        self.users.pop(0)
        self.user_passwords.pop(0)
    self.assertTrue(Trail.objects.count())
    # Change list view.
    changelist_url = reverse('admin:%s_%s_changelist' %
                             (app_label, model_name))
    response = self.client.get(changelist_url)
    self.assertEquals(response.status_code, 200)
    for trail in Trail.objects.all():
        change_url = reverse('admin:%s_%s_change' %
                             (app_label, model_name), args=(trail.pk,))
        change_url_found = False
        soup = BeautifulSoup(response.content)
        for atag in soup.findAll('a', href=True):
            target_url = urlparse.urljoin(changelist_url, atag['href'])
            if target_url == change_url:
                change_url_found = True
                break
        self.assertTrue(change_url_found)
    # Change view (should have no editable fields).
    response = self.client.get(change_url)
    self.assertEquals(response.status_code, 200)
    soup = BeautifulSoup(response.content)
    for fs in soup.findAll('fieldset'):
        self.assertFalse(fs.findAll('input'))
        self.assertFalse(fs.findAll('select'))
        self.assertFalse(fs.findAll('textarea'))
    # Delete view via GET, then POST.
    delete_url = reverse('admin:%s_%s_delete' % (app_label, model_name),
                         args=(trail.pk,))
    response = self.client.get(delete_url)
    self.assertEquals(response.status_code, 200)
    # Add view should raise a 403.
    add_url = reverse('admin:%s_%s_add' % (app_label, model_name))
    response = self.client.get(add_url)
    self.assertEquals(response.status_code, 403)
    # FIXME: History view (normal vs. override)
