# Django
from django.db import models
from django.conf import settings
from django.contrib.contenttypes import generic
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _

# Django-JSONField
from jsonfield import JSONField

# Django-Trails
from trails.managers import TrailManager

__all__ = ['Trail']


class BaseTrailModel(models.Model):

    class Meta:
        abstract = True

    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        related_name='%(app_label)s_%(class)s_related+',
        on_delete=models.SET_NULL,
        editable=False,
    )
    content_type_unicode = models.TextField(
        editable=False,
    )
    content_pk = models.CharField(
        max_length=255,
        editable=False,
    )
    content_object = generic.GenericForeignKey(
        'content_type',
        'content_pk',
    )
    content_unicode = models.TextField(
        editable=False,
    )

    def save(self, *args, **kwargs):
        if not self.pk and not self.content_type_unicode:
            self.content_type_unicode = unicode(self.content_type)
        if not self.pk and not self.content_unicode:
            self.content_unicode = unicode(self.content_object)
        if not self.pk:  # Never save after initial creation.
            super(BaseTrailModel, self).save(*args, **kwargs)


class Trail(BaseTrailModel):
    """Audit trail of changes to models."""

    objects = TrailManager()

    created = models.DateTimeField(
        auto_now_add=True,
    )
    user = models.ForeignKey(
        getattr(settings, 'AUTH_USER_MODEL', 'auth.User'),
        related_name='trails+',
        null=True,
        on_delete=models.SET_NULL,
        editable=False,
    )
    user_is_anonymous = models.NullBooleanField(
        default=None,
        editable=False,
    )
    user_unicode = models.TextField(
        editable=False,
    )
    action = models.SlugField(
        db_index=True,
        editable=False,
    )
    data = JSONField(
        blank=True,
        null=True,
        default=None,
        editable=False,
    )

    class Meta:
        ordering = ['-created']
        verbose_name = _('audit trail')

    def get_user_display(self):
        return unicode(self.user or self.user_unicode or '')

    def get_content_object_display(self):
        try:
            return = unicode(self.content_object)
        except:
            return self.content_unicode

    def get_action_display(self):
        return self.action.capitalize()

    def __unicode__(self):
        return u'%(action)s %(content)s by %(user)s on %(created)s' % {
            'action': self.get_action_display(),
            'content': self.get_content_object_display(),
            'user': self.get_user_display(),
            'created': unicode(self.created),
        }

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


class TrailRelated(BaseTrailModel):
    '''
    Related objects for a given trail.
    '''

    trail = models.ForeignKey(
        'Trail',
        related_name='related',
        on_delete=models.CASCADE,
        editable=False,
    )
    before = models.BooleanField(
        default=False
    )
    relationship = models.CharField(
        max_length=255,
        editable=False,
        default='',
    )

    def save(self, *args, **kwargs):
        if not self.pk and not self.content_unicode:
            self.content_unicode = unicode(self.content_object)
        if not self.pk:  # Never save after initial creation.
            super(TrailRelated, self).save(*args, **kwargs)


import trails.signals
import trails.modelstate
