# Django
from django.db import models
from django.contrib.contenttypes import generic
from django.template.loader import render_to_string
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
        on_delete=models.CASCADE,  # Don't keep trails for stale content types.
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
    action = models.SlugField(
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
        return u'%(action)s %(content)s by %(user)s on %(created)s' % {
            'action': self.action.capitalize(),
            'content': unicode(self.content_object),
            'user': unicode(self.user or self.user_unicode),
            'created': unicode(self.created),
        }

    def save(self, *args, **kwargs):
        if not self.pk and not self.content_unicode:
            self.content_unicode = unicode(self.content_object)
        if not self.pk:  # Never save after initial creation.
            super(Trail, self).save(*args, **kwargs)

    def render(self, format='html'):
        """Render this trail in the given format."""
        model_meta = self.content_type.model_class()._meta
        opts = {
            'app_label': model_meta.app_label,
            'model_name': getattr(model_meta, 'model_name',
                                  getattr(model_meta, 'module_name')),
            'action': self.action,
            'format': format,
        }
        template_list = [
            'trails/%(app_label)s/%(model_name)s/%(action)s.%(format)s' % opts,
            'trails/%(app_label)s/%(model_name)s/default.%(format)s' % opts,
            'trails/%(app_label)s/%(action)s.%(format)s' % opts,
            'trails/%(app_label)s/default.%(format)s' % opts,
            'trails/%(action)s.%(format)s' % opts,
            'trails/default.%(format)s' % opts,
            'trails/_default.txt',
        ]
        return render_to_string(template_list, {'trail': self})


import trails.signals
import trails.modelstate
