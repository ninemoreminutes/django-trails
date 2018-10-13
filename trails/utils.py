# Python
import collections
import json
import logging
import uuid

# Django
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.db import models
from django.forms.models import model_to_dict
from django.utils.encoding import smart_text

# Django-CRUM
from crum import get_current_request, get_current_user

# Django-Trails
#from .settings import trails_settings
#from .models import Trail
#from .pipeline import run_pipeline

__all__ = ['record_trail', 'serialize_instance']

logger = logging.getLogger('trails')


def log_trace(msg, *args, **kwargs):
    '''Log details for tracing the behavior of trails when debugging/testing.'''
    logger.log(5, msg, *args, **kwargs)


def serialize_instance(instance, before=False, related=False, using=None, fields=None):
    """Serialize a model instance to a Python dictionary."""
    result = collections.OrderedDict()
    if not instance or not instance.pk:
        return result
    # content_type = ContentType.objects.get_for_model(instance)
    model_class = instance._meta.model
    if before:
        try:
            instance = model_class.objects.get(pk=instance.pk)
        except model_class.DoesNotExist:
            return result
    # print(instance, before, fields)
    # serialized = json.loads(serializers.serialize('json', [instance]))[0]
    if fields:
        serialized = serializers.serialize('python', [instance], fields=fields)[0]
    else:
        serialized = serializers.serialize('python', [instance])[0]
    # print(serialized)
    result['__model'] = serialized['model']
    result['__pk'] = serialized['pk']
    result.update(serialized['fields'].items())
    if False:
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
            print('parent', parent_class)
            parent_obj = parent_class.objects.get(pk=instance.pk)
            d = dict(d.items() + serialize_instance(parent_obj).items())
        for field in instance._meta.many_to_many:
            m2m_pks = getattr(instance, field.name).values_list('pk', flat=True)
            #print field.name, values
            #d[field.name] = m2m_pks
        #print 'NEW DICT...', d
    return result


def record_trail(action, request=None, session=None, user=None, user_text=None,
                 data=None, instance=None, instance_text=None,
                 instance_data=None, related_instances=None):
    """Record an action taken against a model instance."""
    from .pipeline import run_pipeline
    run_pipeline(
        action=action,
        request=request,
        session=session,
        user=user,
        user_text=user_text,
        data=data,
        instance=instance,
        instance_text=instance_text,
        instance_data=instance_data,
        related_instances=related_instances,
    )
    return
                 
                 
                 
    request = request or get_current_request()
    session = session or getattr(request, 'session', None)
    user = user or get_current_user()
    #logger.debug('%s on %r by %r (%r)', action, instance, user, data)
    print('%s %r by %r (%r)' % (action, instance, user, data))
    #return

    # Based on setting, skip recording anything not done by a user account.
    if not trails_settings.TRACK_NO_USER and user is None:
        return

    # Based on setting, skip recording anything done by the anonymous user.
    if not trails_settings.TRACK_ANON_USER and user and user.is_anonymous:
        return

    #return

    #if request and not hasattr(request, '_trails_uuid') and trails_settings.TRACK_REQUEST:
    #    request._trails_uuid = uuid.uuid4()


    # Get user instance and unicode string from user.
    if user_text is None:
        if user is None:
            user_text = smart_text(trails_settings.NO_USER_TEXT)
        elif user.is_anonymous:
            user_text = smart_text(trails_settings.ANON_USER_TEXT)
        else:
            user_text = smart_text(user)
    if not getattr(user, 'pk', 0):
        user = None

    # Based on setting, recording action to the Python logging module.
    #if trails_settings.USE_LOGGING:
    #    pass  # FIXME: Log to logging module.
    # Based on setting, recording action to the database.
    if trails_settings.USE_DATABASE:
        kwargs = {
            'action': action,
            'user': user,
            'user_text': user_text,
            'data': data or {},
        }
        trail = Trail.objects.create(**kwargs)
        if instance:
            if instance_text is None:
                instance_text = smart_text(instance)
            # Get content type for the given instance.
            try:
                ctype = ContentType.objects.get_for_model(instance)
            except ContentType.DoesNotExist:
                ctype = None
            # Get primary key for the given instance.
            try:
                obj_pk = int(instance.pk)
            except (AttributeError, ValueError):
                obj_pk = None  # FIXME: Handle non-integer primary keys.
            if ctype and obj_pk:
                trail.markers.create(
                    ctype=ctype,
                    obj_pk=obj_pk,
                    obj_text=instance_text,
                    data=instance_data,
                )
        for ri in (related_instances or []):
            rel_text = None
            rel_data = None
            rel_rel = None
            if isinstance(ri, models.Model):
                rel_obj = ri
            elif isinstance(ri, (list, tuple)):
                if len(ri) >= 1:
                    rel_obj = ri[0]
                if len(ri) >= 2:
                    rel_text = ri[1]
                if len(ri) >= 3:
                    rel_data = ri[2]
                if len(ri) >= 4:
                    rel_rel = ri[3]
            elif isinstance(ri, dict):
                rel_obj = ri.get('instance', None)
                rel_text = ri.get('text', None)
                rel_data = ri.get('data', None)
                rel_rel = ri.get('rel', None)
            else:
                raise NotImplementedError()
            if not rel_obj:
                continue
            if rel_text is None:
                rel_text = smart_text(rel_obj)
            rel_data = rel_data or {}
            rel_rel = rel_rel or ''
            # Get content type for the given instance.
            try:
                ctype = ContentType.objects.get_for_model(rel_obj)
            except ContentType.DoesNotExist:
                ctype = None
            # Get primary key for the given instance.
            try:
                obj_pk = int(rel_obj.pk)
            except (AttributeError, ValueError):
                obj_pk = None  # FIXME: Handle non-integer primary keys.
            if ctype and obj_pk:
                trail.markers.create(
                    rel=rel_rel,
                    ctype=ctype,
                    obj_pk=obj_pk,
                    obj_text=rel_text,
                    data=rel_data,
                )
            
