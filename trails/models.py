# Django
from django.db import models
from django.contrib.contenttypes import generic
from django.utils.translation import ugettext_lazy as _

# Django-JSONField
from jsonfield import JSONField

# Django-Trails
from trails.managers import TrailManager

__all__ = ['Trail']


class Trail(models.Model):
    """Audit trail of changes to models."""

    objects = TrailManager()

    created = models.DateTimeField(
        auto_now_add=True,
    )
    user = models.ForeignKey(
        'auth.User',
        related_name='trails',
        null=True,
        on_delete=models.SET_NULL,
        editable=False,
    )
    user_unicode = models.TextField(
        editable=False,
    )
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        related_name='trails',
        null=True,
        on_delete=models.SET_NULL,
        editable=False,
    )
    object_id = models.PositiveIntegerField(
        editable=False,
    )
    content_object = generic.GenericForeignKey(
        'content_type',
        'object_id',
    )
    content_unicode = models.TextField(
        editable=False
    )
    action = models.CharField(
        max_length=100,
        db_index=True,
        editable=False,
    )
    data = JSONField(
        blank=True,
        default='',
        editable=False,
    )

    class Meta:
        ordering = ['-created']
        verbose_name = _('audit trail')

    def __unicode__(self):
        return unicode(self.created)

    def save(self, *args, **kwargs):
        if not self.pk and not self.content_unicode:
            self.content_unicode = unicode(self.content_object)
        if not self.pk:  # Never save after initial creation.
            super(Trail, self).save(*args, **kwargs)


import trails.signals
import trails.modelstate
