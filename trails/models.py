# Django
from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.template.loader import render_to_string
from django.utils.encoding import smart_text
from django.utils.translation import ugettext_lazy as _

# Django-JSONField
from jsonfield import JSONField

# Django-Trails
from .managers import TrailManager
from .settings import trails_settings

__all__ = ['Trail', 'TrailMarker']


class Trail(models.Model):
    '''
    Audit trail of user activity, including changes to models.
    '''

    objects = TrailManager()

    created = models.DateTimeField(
        auto_now_add=True,
    )
    user = models.ForeignKey(
        getattr(settings, 'AUTH_USER_MODEL', 'auth.User'),
        related_name='trails',
        null=True,
        on_delete=models.SET_NULL,
        editable=False,
    )
    user_is_anonymous = models.NullBooleanField(
        default=None,
        editable=False,
    )
    user_text = models.TextField(
        editable=False,
        default='',
    )
    request = models.CharField(
        max_length=255,
        editable=False,
        default='',
    )
    session = models.CharField(
        max_length=255,
        editable=False,
        default='',
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
        verbose_name = _('trail')

    @property
    def user_display(self):
        return smart_text(self.user or self.user_text or '')

    @property
    def action_display(self):
        return trails_settings.ACTION_LABELS.get(self.action, self.action.capitalize)

    @property
    def ctypes_display(self):
        return '; '.join([m.ctype_display for m in self.markers.all()])

    @property
    def markers_display(self):
        return '; '.join([smart_text(m) for m in self.markers.all()])

    def __str__(self):
        return u'%(action)s by %(user)s on %(created)s: %(markers)s' % {
            'action': self.action_display,
            'markers': self.markers_display,
            'user': self.user_display,
            'created': smart_text(self.created),
        }

    def save(self, *args, **kwargs):
        if not self.pk:  # Never save/update after initial creation.
            if not self.user_text and self.user:
                self.user_text = smart_text(self.user)
            super(Trail, self).save(*args, **kwargs)

    def render(self, format='html'):
        """Render this trail in the given format."""
        raise NotImplementedError
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


class TrailMarker(models.Model):
    '''
    Snapshot of a model instance related to a given trail.
    '''

    class Meta:
        ordering = ['-trail__created']
        verbose_name = _('marker')

    trail = models.ForeignKey(
        'Trail',
        related_name='markers',
        on_delete=models.CASCADE,
        editable=False,
    )
    rel = models.CharField(
        max_length=255,
        editable=False,
        default='',
    )
    ctype = models.ForeignKey(
        'contenttypes.ContentType',
        related_name='trailmarkers+',
        on_delete=models.PROTECT,
        editable=False,
    )
    obj_pk = models.CharField(
        max_length=255,
        editable=False,
    )
    obj = GenericForeignKey(
        'ctype',
        'obj_pk',
    )
    obj_text = models.TextField(
        editable=False,
        default='',
    )
    data = JSONField(
        blank=True,
        null=True,
        default=None,
        editable=False,
    )

    @property
    def ctype_display(self):
        return smart_text(self.ctype)

    @property
    def obj_display(self):
        return self.obj_text

    def __str__(self):
        if self.rel:
            return '{} = {}'.format(self.rel, self.obj_display)
        else:
            return self.obj_display

    def save(self, *args, **kwargs):
        if not self.pk:  # Never save/update after initial creation.
            if not self.obj_text:
                self.obj_text = smart_text(self.obj)
            super(TrailMarker, self).save(*args, **kwargs)
