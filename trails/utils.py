# Python
import logging

# Django
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.forms.models import model_to_dict

# Django-Trails
from trails.models import Trail
from trails.middleware import get_current_user

__all__ = ['log_action']

logger = logging.getLogger('trails')


def log_action(action, instance, changes=None, user=None):
    """Record an action taken against a model instance."""
    # Don't log actions taken on the Trail model itself.
    if not instance or isinstance(instance, Trail):
        return
    # FIXME: model_to_dict isn't JSON serializable if there's a file field.
    #if action == 'add' and changes is None:
    #    changes = model_to_dict(instance)
    # FIXME: Store changes on delete?
    user = user or get_current_user()
    if not user:
        return # Skip logging anything not done by a user account.
    user_unicode = unicode(user)
    if not getattr(user, 'pk', 0):
        user = None
    try:
        content_type = ContentType.objects.get_for_model(instance)
    except ContentType.DoesNotExist:
        return
    kwargs = {
        'user': user,
        'user_unicode': user_unicode,
        'content_type': content_type,
        'object_id': getattr(instance, 'pk', 0),
        'action': action,
        'changes': changes or {},
    }
    pass#return Trail.objects.create(**kwargs)
