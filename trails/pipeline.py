# Python
import logging
import pprint
import uuid

# Django
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.encoding import smart_text

# Django-CRUM
from crum import get_current_request, get_current_user

# Django-Trails
from .models import Trail, TrailMarker
from .settings import trails_settings
from .utils import log_trace


def run_pipeline(**kwargs):
    '''
    Run pipeline functions in order, updating kwargs for the next function with
    the results of the previous one.
    '''
    for pipeline_function in trails_settings.PIPELINE:
        try:
            log_trace('running pipeline function: %r(**%r)', pipeline_function, kwargs)
            result = pipeline_function(**kwargs)
        except Exception as e:
            print('err', e)
            raise
        if isinstance(result, dict):
            kwargs.update(result)
        elif result is False:
            break


def debug(**kwargs):
    '''
    Print kwargs passed to the pipeline function.
    '''
    pprint.pprint(kwargs)


def assert_action(**kwargs):
    '''
    Assert that every trail has an action.
    '''
    assert kwargs.get('action'), 'action must be present!'


def add_request(**kwargs):
    '''
    Add the current request to the pipeline.
    '''
    request = kwargs.get('request') or get_current_request()
    return dict(request=request)


def add_request_uuid(**kwargs):
    '''
    Add a UUID to the request object and return it to the pipeline.
    '''
    request = kwargs.get('request')
    if request:
        if not hasattr(request, 'trails_uuid'):
            request.trails_uuid = uuid.uuid4()
        return dict(request_uuid=request.trails_uuid)


def add_session(**kwargs):
    '''
    Add the current session to the pipeline.
    '''
    session = kwargs.get('session') or getattr(kwargs.get('request'), 'session', None)
    return dict(session=session)


def add_user(**kwargs):
    '''
    Add the current user to the pipeline.
    '''
    user = kwargs.get('user') or get_current_user()
    return dict(user=user)


def check_no_user(**kwargs):
    '''
    Based on setting, skip recording anything not done by a user account.
    '''
    user = kwargs.get('user')
    if not trails_settings.TRACK_NO_USER and user is None:
        return False


def add_user_is_anonymous(**kwargs):
    '''
    If user is anonymous, add a boolean flag and set user to None.
    '''
    user = kwargs.get('user')
    if user and getattr(user, 'is_anonymous', False):
        return dict(user=None, user_is_anonymous=True)
    else:
        return dict(user_is_anonymous=False)


def check_anonymous_user(**kwargs):
    '''
    Based on setting, skip recording anything done by the anonymous user.
    '''
    user_is_anonymous = kwargs.get('user_is_anonymous')
    if not trails_settings.TRACK_ANON_USER and user_is_anonymous:
        return False


def add_request_text(**kwargs):
    '''
    Add text representation of request (UUID + method + path).
    '''
    request = kwargs.get('request')
    request_uuid = kwargs.get('request_uuid') or getattr(request, 'trails_uuid', None)
    if request:
        parts = []
        if request_uuid:
            parts.append('[{}]'.format(request_uuid))
        if request.method:
            parts.append(smart_text(request.method))
        if request.get_full_path():
            parts.append(smart_text(request.get_full_path()))
        return dict(request_text=' '.join(parts))


def add_session_text(**kwargs):
    '''
    Add text representation of session (session key/id).
    '''
    session = kwargs.get('session')
    session_key = getattr(session, 'session_key', '')
    return dict(session_text=smart_text(session_key))


def add_user_text(**kwargs):
    '''
    Add text representation of user instance.
    '''
    user = kwargs.get('user')
    user_is_anonymous = kwargs.get('user_is_anonymous')
    user_text = kwargs.get('user_text')
    if user_text is None:
        if user_is_anonymous:
            user_text = smart_text(trails_settings.ANON_USER_TEXT)
        elif user is None:
            user_text = smart_text(trails_settings.NO_USER_TEXT)
        else:
            user_text = smart_text(user)
    return dict(user_text=user_text)


def log_trail(**kwargs):
    '''
    Log the trail to the configured logger.
    '''
    if not trails_settings.USE_LOGGER:
        return
    logger = logging.getLogger(trails_settings.LOGGER)  # noqa
    # FIXME: Implement!


def create_database_trail(**kwargs):
    '''
    Create the main trail record in the database.
    '''
    if not trails_settings.USE_DATABASE:
        return
    trail = Trail.objects.create(
        action=kwargs.get('action'),
        request=kwargs.get('request_text'),
        session=kwargs.get('session_text'),
        user=kwargs.get('user'),
        user_text=kwargs.get('user_text'),
        data=kwargs.get('data'),
    )
    return dict(trail=trail)


def _create_database_trail_marker(trail, obj=None, obj_text=None, data=None, rel=None):
    '''
    Helper to create a trail marker in the database for a model instance.
    '''
    if not trail or not obj:
        return
    if obj_text is None:
        obj_text = smart_text(obj)
    data = data or {}
    rel = rel or ''
    # Get content type for the given instance.
    try:
        ctype = ContentType.objects.get_for_model(obj)
    except ContentType.DoesNotExist:
        ctype = None
    # Get primary key for the given instance.
    try:
        obj_pk = int(obj.pk)
    except (AttributeError, ValueError):
        obj_pk = None  # FIXME: Handle non-integer primary keys.
    if ctype and obj_pk:
        return TrailMarker.objects.create(
            trail=trail,
            rel=rel,
            ctype=ctype,
            obj_pk=obj_pk,
            obj_text=obj_text,
            data=data,
        )


def create_primary_database_trail_marker(**kwargs):
    '''
    Create a trail marker for the primary model instance affected.
    '''
    if not trails_settings.USE_DATABASE:
        return
    primary_trail_marker = _create_database_trail_marker(
        trail=kwargs.get('trail'),
        obj=kwargs.get('instance'),
        obj_text=kwargs.get('instance_text'),
        data=kwargs.get('instance_data'),
    )
    return dict(primary_trail_marker=primary_trail_marker)


def create_related_database_trail_markers(**kwargs):
    '''
    Create a trail marker for any related model instances affected.
    '''
    if not trails_settings.USE_DATABASE:
        return
    related_instances = kwargs.get('related_instances') or []
    related_trail_markers = []
    for related_instance in related_instances:
        instance = None
        instance_text = None
        instance_data = None
        instance_rel = None
        if isinstance(related_instance, models.Model):
            instance = related_instance
        elif isinstance(related_instance, (list, tuple)):
            if len(related_instance) >= 1:
                instance = related_instance[0]
            if len(related_instance) >= 2:
                instance_text = related_instance[1]
            if len(related_instance) >= 3:
                instance_data = related_instance[2]
            if len(related_instance) >= 4:
                instance_rel = related_instance[3]
        elif isinstance(related_instance, dict):
            instance = related_instance.get('instance', None) or related_instance.get('obj', None)
            instance_text = related_instance.get('text', None) or related_instance.get('obj_text', None)
            instance_data = related_instance.get('data', None)
            instance_rel = related_instance.get('rel', None)
        related_trail_marker = _create_database_trail_marker(
            trail=kwargs.get('trail'),
            obj=instance,
            obj_text=instance_text,
            data=instance_data,
            rel=instance_rel,
        )
        if related_trail_marker:
            related_trail_markers.append(related_trail_marker)
    return dict(related_trail_markers=related_trail_markers)
