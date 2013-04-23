# Django
from django.db import models
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType

__all__ = ['TrailManager']


class TrailManager(models.Manager):
    """Manager for the Trail class."""

    use_for_related_objects = True

    def for_models(self, *instances):
        """Return a all trails for the given model instances or querysets."""
        opts = {}
        for item in instances:
            # Allow each item (positional argument) to be iterable itself, so
            # that querysets can be passed in addition to individual instances.
            try:
                item_iter = iter(item)
            except TypeError:
                item_iter = iter([item])
            for instance in item_iter:
                if not instance:
                    continue
                ct = ContentType.objects.get_for_model(instance)
                ct_pks = opts.setdefault(ct, set())
                ct_pks.add(instance.pk)
        q = Q(pk=0)
        for ct, pks in opts.items():
            q = q | Q(content_type=ct, object_id__in=pks)
        return self.filter(q)
