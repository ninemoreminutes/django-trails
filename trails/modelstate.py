# Python
import threading

# Django
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models.signals import m2m_changed
from django.contrib.contenttypes.models import ContentType

# Django-Trails
from trails.utils import serialize_instance
from trails.signals import model_added, model_changed, model_deleted

__all__ = []


class ModelState(threading.local):
    """Thread-local cache for tracking model changes."""

    def __init__(self):
        pre_save.connect(self.pre_save_callback)
        post_save.connect(self.post_save_callback)
        post_delete.connect(self.post_delete_callback)
        m2m_changed.connect(self.m2m_changed_callback)
        self.cache = {}

    def _get_key_for_instance(self, instance):
        pk = instance.pk
        ct = ContentType.objects.get_for_model(instance)
        return u'%s.%s' % (ct.app_label, ct.model), pk

    def _compare_dicts(self, a, b):
        d = {}
        akeys = set(a.keys())
        bkeys = set(b.keys())
        for key in akeys - bkeys:
            d[key] = (a[key], None)
        for key in bkeys - akeys:
            d[key] = (None, b[key])
        for key in akeys & bkeys:
            if a[key] != b[key]:
                d[key] = (a[key], b[key])
        return d

    def pre_save_callback(self, sender, **kwargs):
        instance = kwargs['instance']
        value = serialize_instance(instance, before=True)
        if value:
            key = self._get_key_for_instance(instance)
            self.cache[key] = value

    def post_save_callback(self, sender, **kwargs):
        instance = kwargs['instance']
        created = kwargs['created']
        if not created:
            key = self._get_key_for_instance(instance)
            before = self.cache.pop(key, None)
            if before:
                after = serialize_instance(instance)
                diff = self._compare_dicts(before, after)
                if diff:
                    model_changed.send(sender, instance=instance,
                                       raw=kwargs.get('raw'),
                                       using=kwargs.get('using'), changes=diff)
        else:
            model_added.send(sender, instance=instance, raw=kwargs.get('raw'),
                             using=kwargs.get('using'))

    def m2m_changed_callback(self, sender, **kwargs):
        # FIXME: Not currently tracking M2M changes!!!
        #print 'm2m_changed', sender, kwargs
        action = kwargs['action']
        instance = kwargs['instance']
        other_model = kwargs['model']
        rev = kwargs['reverse']
        if action in ('pre_clear', 'pre_add', 'pre_remove'):
            pass
            #name = field.m2m_reverse_name()
            #old = [ str(getattr(x, name)) for x in sender.objects.all() ]
            #print old
            #print sender.objects.all()
            # we know the new will exclude this, so its just all without this
            #ex = {"%s__in" % field.m2m_reverse_field_name():kwargs["pk_set"]}
            #new = [ str(getattr(x, name)) for x in
            #       sender.objects.exclude(**ex)]
            #diff = { "old": old, "new": new }
        elif action in ('post_clear', 'post_add', 'post_remove'):
            pass

    def post_delete_callback(self, sender, **kwargs):
        model_deleted.send(sender, instance=kwargs.get('instance'),
                           raw=kwargs.get('raw'), using=kwargs.get('using'))

model_state = ModelState()
