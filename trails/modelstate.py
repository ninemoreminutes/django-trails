# Python
import threading

# Django
from django.db.models.signals import pre_save, post_save
from django.db.models.signals import pre_delete, post_delete
from django.db.models.signals import m2m_changed

# Django-Trails
from trails.utils import serialize_instance
from trails.signals import model_added, model_changed, model_deleted

__all__ = []


class ModelState(threading.local):
    """Thread-local cache for tracking model changes."""

    def __init__(self):
        pre_save.connect(self.on_pre_save)
        post_save.connect(self.on_post_save)
        pre_delete.connect(self.on_pre_delete)
        post_delete.connect(self.on_post_delete)
        m2m_changed.connect(self.on_m2m_changed)
        self.cache = {}

    def get_cache_key(self, instance, signal=None):
        app_label = instance._meta.app_label
        model_name = getattr(instance._meta, 'model_name',
                             getattr(instance._meta, 'module_name'))
        return '%s.%s-%s' % (app_label, model_name, signal), instance.pk

    def compare_dicts(self, a, b):
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

    def on_pre_save(self, sender, **kwargs):
        instance = kwargs['instance']
        value = serialize_instance(instance, before=True)
        if value:
            key = self.get_cache_key(instance, 'save')
            self.cache[key] = value

    def on_post_save(self, sender, **kwargs):
        instance = kwargs['instance']
        created = kwargs['created']
        if not created:
            key = self.get_cache_key(instance, 'save')
            before = self.cache.pop(key, None)
            if before:
                after = serialize_instance(instance)
                diff = self.compare_dicts(before, after)
                if diff:
                    model_changed.send(sender, instance=instance,
                                       raw=kwargs.get('raw'),
                                       using=kwargs.get('using'), data=diff)
        else:
            data = serialize_instance(instance)
            model_added.send(sender, instance=instance, raw=kwargs.get('raw'),
                             using=kwargs.get('using'), data=data)

    def on_pre_delete(self, sender, **kwargs):
        instance = kwargs['instance']
        value = serialize_instance(instance, before=True)
        if value:
            key = self.get_cache_key(instance, 'delete')
            self.cache[key] = value

    def on_post_delete(self, sender, **kwargs):
        instance = kwargs['instance']
        key = self.get_cache_key(instance, 'delete')
        data = self.cache.pop(key, None)
        model_deleted.send(sender, instance=kwargs.get('instance'),
                           raw=kwargs.get('raw'), using=kwargs.get('using'),
                           data=data)

    def on_m2m_changed(self, sender, **kwargs):
        # FIXME: Not currently tracking M2M changes!!!
        #print
        #print 'm2m_changed', sender, kwargs
        action = kwargs['action']
        instance = kwargs['instance']
        other_model = kwargs['model']
        rev = kwargs['reverse']
        field_name = None
        try:
            if rev:
                for m2m_field in other_model._meta.many_to_many:
                    if m2m_field.rel.through == sender:
                        field_name = m2m_field.related.get_accessor_name()
                        break
            else:
                for m2m_field in instance._meta.many_to_many:
                    if m2m_field.rel.through == sender:
                        field_name = m2m_field.name
                        break
        except AttributeError:
            raise
        print instance, field_name, other_model
        if action in ('pre_clear', 'pre_add', 'pre_remove'):
            key = self.get_cache_key(sender, action.replace('pre_', ''))
            value = set(sender.objects.values_list('pk', flat=True))
            self.cache[key] = value
        elif action in ('post_clear', 'post_add', 'post_remove'):
            key = self.get_cache_key(sender, action.replace('post_', ''))
            before = self.cache.pop(key, set())
            after = set(sender.objects.values_list('pk', flat=True))
            for item in before - after:
                print item, 'removed from', field_name, 'for', instance
            for item in after - before:
                print item, 'added to', field_name, 'for', instance


model_state = ModelState()
