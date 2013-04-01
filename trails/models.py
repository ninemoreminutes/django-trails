# Django
from django.db import models
from django.contrib.contenttypes import generic
from django.utils.translation import ugettext_lazy as _

# Django-JSONField
from jsonfield import JSONField

__all__ = ['Trail']

class Trail(models.Model): 
    """Audit trail of changes to models."""
    
    #ACTION_CHOICES = [
    #    ('add', _('Add')),
    #    ('change', _('Change')),
    #    ('delete', _('Delete')),
    #    ('read', _('Read')),
    #]

    class Meta:
        ordering = ['-created']
        verbose_name = _('audit trail')

    created = models.DateTimeField(
        auto_now_add=True,
    )
    user = models.ForeignKey(
        'auth.User',
        related_name='trails',
        editable=False,
        null=True,
        on_delete=models.CASCADE,
    )
    user_unicode = models.CharField(
        max_length=200,
    )
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        related_name='trails',
    )
    object_id = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')
    content_unicode = models.CharField(max_length=200)
    action = models.CharField(max_length=100, db_index=True)
    changes = JSONField(blank=True, default='')

    def save(self, *args, **kwargs):
        if not self.pk and not self.content_unicode:
            self.content_unicode = unicode(self.content_object)
        if not self.pk: # Never save after initial creation.
            super(Trail, self).save(*args, **kwargs)

import signals
