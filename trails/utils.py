# Python
import logging

# Django
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.forms.models import model_to_dict

# Django-Trails
from trails import settings as trails_settings
from trails.models import Trail
from trails.middleware import get_current_user

__all__ = ['record_trail', 'serialize_instance']

logger = logging.getLogger('trails')


def get_setting(name):
    """Return a trails setting, falling back to the defaults."""
    return getattr(settings, name, getattr(trails_settings, name))


def serialize_instance(instance, before=False, related=False):
    """Serialize a model instance to a dictionary."""
    if not instance or not instance.pk:
        return {}
    content_type = ContentType.objects.get_for_model(instance)
    model_class = content_type.model_class()
    if before:
        try:
            instance = model_class.objects.get(pk=instance.pk)
        except model_class.DoesNotExist:
            return {}
    #print instance, before
    serialized = serializers.serialize('python', [instance])[0]
    #print serialized
    d = serialized['fields']
    d['pk'] = serialized['pk']
    if related:
        related_objects = []
        related_objects.extend(model_class._meta.get_all_related_objects())
        related_objects.extend(
            model_class._meta.get_all_related_many_to_many_objects())
        for related_object in related_objects:
            field_name = related_object.get_accessor_name()
            d[field_name] = [x._get_pk_val() for x in
                             getattr(instance, field_name).iterator()]
    for parent_class in instance._meta.get_parent_list():
        parent_obj = parent_class.objects.get(pk=instance.pk)
        d = dict(d.items() + serialize_instance(parent_obj).items())
    for field in instance._meta.many_to_many:
        m2m_pks = getattr(instance, field.name).values_list('pk', flat=True)
        #print field.name, values
        #d[field.name] = m2m_pks
    #print 'NEW DICT...', d
    return d


def record_trail(action, instance, data=None, user=None):
    """Record an action taken against a model instance."""
    user = user or get_current_user()
    #logger.debug('%s on %r by %r (%r)', action, instance, user, data)
    #print '%s %r by %r (%r)' % (action, instance, user, data)

    # Based on setting, skip recording anything not done by a user account.
    if not get_setting('TRAILS_LOG_USER_NONE') and user is None:
        return
    # Based on setting, skip recording anything done by the anonymous user.
    if not get_setting('TRAILS_LOG_USER_ANONYMOUS') and user and \
            user.is_anonymous():
        return
    # Skip recording changes for the Trail model itself.
    if isinstance(instance, Trail):
        return
    # Skip excluded apps and models.
    app_label = instance._meta.app_label
    model_name = getattr(instance._meta, 'model_name',
                         getattr(instance._meta, 'module_name'))
    excludes = get_setting('TRAILS_EXCLUDE')
    if app_label in excludes:
        return
    if '%s.%s' % (app_label, model_name) in excludes:
        return

    # FIXME: model_to_dict isn't JSON serializable if there's a file field.
    #if action == 'add' and data is None:
    #    data = model_to_dict(instance)
    # FIXME: Store data on delete?

    # Get user instance and unicode string from user.
    if user is None:
        user_unicode = get_setting('TRAILS_USER_NONE')
    elif user.is_anonymous():
        user_unicode = get_setting('TRAILS_USER_ANONYMOUS')
    else:
        user_unicode = unicode(user)
    if not getattr(user, 'pk', 0):
        user = None
    # Get content type for the given instance.
    try:
        content_type = ContentType.objects.get_for_model(instance)
    except ContentType.DoesNotExist:
        return
    # Get primary key for the given instance.
    try:
        object_id = int(instance.pk)
    except (AttributeError, ValueError):
        return  # FIXME: Handle non-integer primary keys.
    # Based on setting, recording action to the Python logging module.
    if get_setting('TRAILS_USE_LOGGING'):
        pass  # FIXME: Log to logging module.
    # Based on setting, recording action to the database.
    if get_setting('TRAILS_USE_DATABASE'):
        kwargs = {
            'user': user,
            'user_unicode': user_unicode,
            'content_type': content_type,
            'object_id': object_id,
            'action': action,
            'data': data or {},
        }
        Trail.objects.create(**kwargs)
