# Python
import collections
import logging

# Django
from django.core import serializers

__all__ = ['record_trail', 'serialize_instance']

logger = logging.getLogger('trails')


def log_trace(msg, *args, **kwargs):
    '''
    Log details for tracing the behavior of trails when debugging/testing.
    '''
    logger.log(5, msg, *args, **kwargs)


def serialize_instance(instance, before=False, fields=None, using=None):
    '''
    Serialize a model instance to a Python dictionary.
    '''
    # FIXME: Honor using argument!
    result = collections.OrderedDict()
    if not instance or not instance.pk:
        return result
    model_class = instance._meta.model
    if before:
        try:
            instance = model_class.objects.get(pk=instance.pk)
        except model_class.DoesNotExist:
            return result
    if fields:
        serialized = serializers.serialize('python', [instance], fields=fields)[0]
    else:
        serialized = serializers.serialize('python', [instance])[0]
    result['__model'] = serialized['model']
    result['__pk'] = serialized['pk']
    result.update(serialized['fields'].items())
    return result


def record_trail(action, request=None, session=None, user=None, user_text=None,
                 data=None, instance=None, instance_text=None,
                 instance_data=None, related_instances=None):
    '''
    Record an action taken against a model instance.
    '''
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
