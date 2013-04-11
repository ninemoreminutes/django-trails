# Python
import logging

# Django
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.forms.models import model_to_dict

# Django-Trails
from trails.models import Trail
from trails.middleware import get_current_user

__all__ = ['log_action', 'serialize_instance']

logger = logging.getLogger('trails')


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
        related_objects.extend(model_class._meta.get_all_related_many_to_many_objects())
        for related_object in related_objects:
            field_name = related_object.get_accessor_name()
            d[field_name] = [x._get_pk_val() for x in \
                             getattr(instance, field_name).iterator()]
    for parent_class in instance._meta.get_parent_list():
        parent_obj = parent_class.objects.get(pk=instance.pk)
        d = dict(d.items() + serialize_instance(parent_obj).items())
    for field in instance._meta.many_to_many:
        m2m_pks = getattr(instance, field.name).values_list('pk', flat=True)
        #print field.name, values
        #d[field.name] = m2m_pks
    print 'NEW DICT...', d
    return d


def log_action(action, instance, changes=None, user=None):
    """Record an action taken against a model instance."""
    user = user or get_current_user()
    #logger.debug('%s on %r by %r (%r)', action, instance, user, changes)
    #print '%s %r by %r (%r)' % (action, instance, user, changes)
    
    if not user:
        return # Skip logging anything not done by a user account.
    # Don't log actions taken on the Trail model itself.
    if not instance or isinstance(instance, Trail):
        return
    # FIXME: model_to_dict isn't JSON serializable if there's a file field.
    #if action == 'add' and changes is None:
    #    changes = model_to_dict(instance)
    # FIXME: Store changes on delete?
    user_unicode = unicode(user)
    if not getattr(user, 'pk', 0):
        user = None
    try:
        content_type = ContentType.objects.get_for_model(instance)
    except ContentType.DoesNotExist:
        return
    try:
        object_id = int(instance.pk)
    except (AttributeError, ValueError):
        return 
    kwargs = {
        'user': user,
        'user_unicode': user_unicode,
        'content_type': content_type,
        'object_id': object_id,
        'action': action,
        'changes': changes or {},
    }
    return Trail.objects.create(**kwargs)
