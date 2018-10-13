# Python
import collections
import functools
import logging
import threading

# Django
from django.db import models
from django.core.signals import (
    request_started,
    request_finished,
    got_request_exception,
)
from django.db.models.signals import (
    pre_init,
    post_init,
    pre_save,
    post_save,
    pre_delete,
    post_delete,
    m2m_changed,
    pre_migrate,
    post_migrate,
)
from django.contrib.auth import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.utils.encoding import force_text, smart_text

# Django-CRUM
from crum import get_current_request

# Django-Trails
from .settings import trails_settings
from .utils import log_trace, serialize_instance, record_trail
# from trails.signals import model_added, model_changed, model_deleted

__all__ = []


class ModelTracker(object):
    '''
    Tracker for signals related to model instance changes.
    '''

    def __init__(self, model_class, model_fields):
        log_trace('ModelTracker.__init__(%r, %r)', model_class, model_fields)
        self.model_class = model_class
        self.model_fields = model_fields
        self.trails_tls = threading.local()
        self.connect()

    def __del__(self):
        try:
            self.disconnect()
        except Exception:
            pass

    def __repr__(self):
        return '<ModelTracker for {!r}>'.format(self.model_class)

    @property
    def discrete_fields(self):
        return [field_name for field_name, field_action in self.model_fields.items() if field_action in (True, '__SENSITIVE__')]

    @property
    def sensitive_fields(self):
        return [field_name for field_name, field_action in self.model_fields.items() if field_action == '__SENSITIVE__']

    @property
    def m2m_fields(self):
        return collections.OrderedDict([
            (field_name, field_action)
            for field_name, field_action in self.model_fields.items()
            if isinstance(field_action, type) and issubclass(field_action, models.Model)
        ])

    def get_dispatch_uid(self, signal_name):
        opts = self.model_class._meta
        return 'trails-{}.{}-{}[{}]'.format(opts.app_label, opts.model_name, signal_name, id(self))

    def connect(self):
        for signal_name in ('pre_migrate', 'post_migrate'):
            signal = globals()[signal_name]
            dispatch_uid = self.get_dispatch_uid(signal_name)
            signal.connect(
                getattr(self, 'on_{}'.format(signal_name)),
                sender=self.model_class._meta.app_config,
                dispatch_uid=dispatch_uid,
            )
            log_trace('%r: connect %s', self, dispatch_uid)
        for signal_name in ('pre_save', 'post_save', 'pre_delete', 'post_delete'):
            signal = globals()[signal_name]
            dispatch_uid = self.get_dispatch_uid(signal_name)
            signal.connect(
                getattr(self, 'on_{}'.format(signal_name)),
                sender=self.model_class,
                dispatch_uid=dispatch_uid,
            )
            log_trace('%r: connect %s', self, dispatch_uid)

    def disconnect(self):
        for signal_name in ('pre_migrate', 'post_migrate', 'pre_save', 'post_save', 'pre_delete', 'post_delete'):
            signal = globals()[signal_name]
            dispatch_uid = self.get_dispatch_uid(signal_name)
            signal.disconnect(
                dispatch_uid=dispatch_uid,
            )
            log_trace('%r: disconnect %s', self, dispatch_uid)

    @property
    def migrating(self):
        return getattr(self.trails_tls, 'migrating', False)

    def on_pre_migrate(self, sender, **kwargs):
        log_trace('%r: on_pre_migrate(%r, **%r)', self, sender, kwargs)
        self.trails_tls.migrating = True

    def on_post_migrate(self, sender, **kwargs):
        log_trace('%r: on_post_migrate(%r, **%r)', self, sender, kwargs)
        self.trails_tls.migrating = False

    def on_pre_save(self, sender, **kwargs):
        log_trace('%r: on_pre_save(%r, **%r)', self, sender, kwargs)
        if self.migrating and not trails_settings.TRACK_MIGRATIONS:
            return
        instance = kwargs['instance']
        raw = kwargs['raw']
        if raw and not trails_settings.TRACK_RAW:
            return
        using = kwargs['using']
        update_fields = kwargs['update_fields']
        fields = self.discrete_fields
        if update_fields:
            fields = [f for f in fields if f in update_fields]
        serialized = serialize_instance(instance, before=True, using=using, fields=fields)
        if serialized:
            if not hasattr(instance, '_trails_tls'):
                instance._trails_tls = threading.local()
            instance._trails_tls.pre_save = serialized

    def on_post_save(self, sender, **kwargs):
        log_trace('%r: on_post_save(%r, **%r)', self, sender, kwargs)
        if self.migrating and not trails_settings.TRACK_MIGRATIONS:
            return
        instance = kwargs['instance']
        created = kwargs['created']
        raw = kwargs['raw']
        if raw and not trails_settings.TRACK_RAW:
            return
        using = kwargs['using']
        update_fields = kwargs['update_fields']
        fields = self.discrete_fields
        if update_fields:
            fields = [f for f in fields if f in update_fields]
        if created:
            serialized = serialize_instance(instance, using=using, fields=fields)
            for field, value in serialized.items():
                if field in self.sensitive_fields and value:  # FIXME: Indicate empty value or not?
                    serialized[field] = trails_settings.SENSITIVE_TEXT
            record_trail('add', instance=instance, instance_data=serialized)
        else:
            before = getattr(getattr(instance, '_trails_tls', None), 'pre_save', None) or {}
            after = serialize_instance(instance, using=using, fields=fields) or {}
            changes = collections.OrderedDict()
            for field in fields:
                if field in after and field in before:
                    if after[field] != before[field]:
                        changes[field] = (before[field], after[field])
                elif field in after:
                    changes[field] = (None, after[field])
                elif field in before:
                    changes[field] = (before[field], None)
            for field, values in changes.items():
                if field in self.sensitive_fields:  # FIXME: Indicate empty value or not?
                    changes[field] = (values[0] or trails_settings.SENSITIVE_TEXT, values[1] or trails_settings.SENSITIVE_TEXT)
            if changes:
                record_trail('change', instance=instance, instance_data=changes)

    def on_pre_delete(self, sender, **kwargs):
        log_trace('%r: on_pre_delete(%r, **%r)', self, sender, kwargs)
        if self.migrating and not trails_settings.TRACK_MIGRATIONS:
            return
        instance = kwargs['instance']
        if not hasattr(instance, '_trails_tls'):
            instance._trails_tls = threading.local()
        instance._trails_tls.pre_delete = force_text(instance)

    def on_post_delete(self, sender, **kwargs):
        log_trace('%r: on_post_delete(%r, **%r)', self, sender, kwargs)
        if self.migrating and not trails_settings.TRACK_MIGRATIONS:
            return
        instance = kwargs['instance']
        instance_text = getattr(getattr(instance, '_trails_tls', None), 'pre_delete', None)
        if instance_text is not None:
            record_trail('delete', instance=instance, instance_text=instance_text)


class ManyToManyTracker(object):

    def __init__(self, m2m_model_class, related_model_fields):
        log_trace('ManyToManyTracker.__init__(%r)', m2m_model_class)
        self.m2m_model_class = m2m_model_class
        self.related_model_fields = related_model_fields
        self.trails_tls = threading.local()
        self.connect()

    def __del__(self):
        try:
            self.disconnect()
        except Exception:
            pass

    def __repr__(self):
        return '<ManyToManyTracker for {!r}>'.format(self.m2m_model_class)

    def get_dispatch_uid(self, signal_name):
        opts = self.m2m_model_class._meta
        return 'trails-{}.{}-{}[{}]'.format(opts.app_label, opts.model_name,
                                            signal_name, id(self))

    def connect(self):
        for signal_name in ('pre_migrate', 'post_migrate'):
            signal = globals()[signal_name]
            dispatch_uid = self.get_dispatch_uid(signal_name)
            signal.connect(
                getattr(self, 'on_{}'.format(signal_name)),
                sender=self.m2m_model_class._meta.app_config,
                dispatch_uid=dispatch_uid,
            )
            log_trace('%r: connect %s', self, dispatch_uid)
        dispatch_uid = self.get_dispatch_uid('m2m_changed')
        m2m_changed.connect(
            self.on_m2m_changed,
            sender=self.m2m_model_class,
            dispatch_uid=dispatch_uid,
        )
        log_trace('%r: connect %s', self, dispatch_uid)

    def disconnect(self):
        for signal_name in ('pre_migrate', 'post_migrate'):
            signal = globals()[signal_name]
            dispatch_uid = self.get_dispatch_uid(signal_name)
            signal.disconnect(
                dispatch_uid=dispatch_uid,
            )
            log_trace('%r: disconnect %s', self, dispatch_uid)
        dispatch_uid = self.get_dispatch_uid('m2m_changed')
        m2m_changed.disconnect(
            dispatch_uid=dispatch_uid,
        )
        log_trace('%r: disconnect %s', self, dispatch_uid)

    @property
    def migrating(self):
        return getattr(self.trails_tls, 'migrating', False)

    def on_pre_migrate(self, sender, **kwargs):
        log_trace('%r: on_pre_migrate(%r, **%r)', self, sender, kwargs)
        self.trails_tls.migrating = True

    def on_post_migrate(self, sender, **kwargs):
        log_trace('%r: on_post_migrate(%r, **%r)', self, sender, kwargs)
        self.trails_tls.migrating = False

    def _get_rel_names(self, instance, model):
        primary_rel, related_rel = '', ''
        for model_class, field_name in self.related_model_fields:
            if model_class == model:
                related_rel = field_name
            elif isinstance(instance, model_class):
                primary_rel = field_name
        return primary_rel, related_rel

    def on_m2m_pre_add(self, sender, instance, model, pk_set):
        pass

    def on_m2m_post_add(self, sender, instance, model, pk_set):
        if not pk_set:
            return
        primary_rel, related_rel = self._get_rel_names(instance, model)
        related_list = [dict(rel=primary_rel, instance=instance)]
        for related_instance in model.objects.filter(pk__in=pk_set):
            related_list.append(dict(rel=related_rel, instance=related_instance))
        record_trail('associate', related_instances=related_list)

    def on_m2m_pre_remove(self, sender, instance, model, pk_set):
        pass

    def on_m2m_post_remove(self, sender, instance, model, pk_set):
        if not pk_set:
            return
        primary_rel, related_rel = self._get_rel_names(instance, model)
        related_list = [dict(rel=primary_rel, instance=instance)]
        for related_instance in model.objects.filter(pk__in=pk_set):
            related_list.append(dict(rel=related_rel, instance=related_instance))
        record_trail('disassociate', related_instances=related_list)

    def on_m2m_pre_clear(self, sender, instance, model, pk_set=None):
        primary_rel, related_rel = self._get_rel_names(instance, model)
        related_pks = list(getattr(instance, primary_rel).values_list('pk', flat=True))
        if not hasattr(instance, '_trails_tls'):
            instance._trails_tls = threading.local()
        setattr(instance._trails_tls, 'pre_clear_{}'.format(primary_rel), related_pks)

    def on_m2m_post_clear(self, sender, instance, model, pk_set=None):
        primary_rel, related_rel = self._get_rel_names(instance, model)
        related_pks = getattr(getattr(instance, '_trails_tls', None), 'pre_clear_{}'.format(primary_rel), None) or []
        related_list = [dict(rel=primary_rel, instance=instance)]
        for related_instance in model.objects.filter(pk__in=related_pks):
            related_list.append(dict(rel=related_rel, instance=related_instance))
        record_trail('disassociate', related_instances=related_list)

    def on_m2m_changed(self, sender, **kwargs):
        log_trace('%r: on_m2m_changed(%r, **%r)', self, sender, kwargs)
        if self.migrating and not trails_settings.TRACK_MIGRATIONS:
            return

        method = getattr(self, 'on_m2m_{}'.format(kwargs['action']))
        method(sender, kwargs['instance'], kwargs['model'], kwargs['pk_set'])
        return

        if action in {'pre_add', 'pre_remove'}:
            return
        
        instance = kwargs['instance']
        model = kwargs['model']
        pk_set = set(kwargs['pk_set'] or [])
        reverse = kwargs['reverse']
        using = kwargs['using']


        primary_instances = [instance]
        if action == 'pre_clear':
            if related_model == self.model_class:
                related_field = getattr(related_model, field_name)
                if not related_field.reverse:
                    reverse_field_name = related_field.rel.get_accessor_name()
                else:
                    reverse_field_name = getattr(related_field.field, 'attname', related_field.field.name)
                related_pks = list(getattr(instance, reverse_field_name).values_list('pk', flat=True))
            else:
                related_pks = list(getattr(instance, field_name).values_list('pk', flat=True))
        elif action == 'post_clear':
            related_pks = []  # FIXME: Load from those saved pre_clear

        related_instances = related_model.objects.filter(pk__in=related_pks)

        # If signaled from the reverse side of the relation, swap primary and
        # related instances.
        if related_model == self.model_class:
            #print('backwards!!')
            primary_instances, related_instances = related_instances, primary_instances

        for pi in primary_instances:
            
            related_pks = [ri.pk for ri in related_instances]
            if not related_pks:
                continue
                
            related = [dict(rel=field_name, instance=ri) for ri in related_instances]
            if action == 'post_add':
                record_trail('associate', instance=pi, related_instances=related)
            elif action == 'post_remove':
                record_trail('disassociate', instance=pi, related_instances=related)

            
            continue
            for ri in related_instances:
                if action == 'post_add':
                    print('==== M2M:', pi, '.', field_name, '+=', ri)
                    record_trail('associate', instance=pi, related_instance=ri, data={field_name: ri.pk})
                elif action == 'post_remove':
                    print('==== M2M:', pi, '.', field_name, '-=', ri)
                    record_trail('disassociate', instance=pi, related_instance=ri, data={field_name: ri.pk})
                elif action == 'pre_clear':
                    print('==== M2M:', pi, '.', field_name, 'x=', ri)
                    # FIXME: Save temporarily.
                elif action == 'post_clear':
                    print('==== M2M:', pi, '.', field_name, 'X=', ri)


        #field_name = None
        #for m2m_field_name, m2m_model in self.m2m_fields.items():
        #    if m2m_model._meta.model == sender:
        #        field_name = m2m_field_name
        #        break
        #if not field_name:
        #    return

        #print('m2m:', instance, '.', field_name, '->', related_model, 'rev?', reverse, 'other?', related_model == self.model_class)

        return
        if action in ('pre_clear', 'pre_add', 'pre_remove'):
            key = self.get_cache_key(sender, action.replace('pre_', ''))
            value = set(sender.objects.values_list('pk', flat=True))
            self.cache[key] = value
        elif action in ('post_clear', 'post_add', 'post_remove'):
            key = self.get_cache_key(sender, action.replace('post_', ''))
            before = self.cache.pop(key, set())
            after = set(sender.objects.values_list('pk', flat=True))
            #for item in before - after:
            #    print item, 'removed from', field_name, 'for', instance
            #for item in after - before:
            #    print item, 'added to', field_name, 'for', instance


class UserTracker(object):
    
    def __init__(self, track_login=True, track_logout=True,
                 track_failed_login=True):
        log_trace('UserTracker.__init__(track_login=%r, track_logout=%r, track_failed_login=%r)',
                  track_login, track_logout, track_failed_login)
        self.track_login = track_login
        self.track_logout = track_logout
        self.track_failed_login = track_failed_login
        self.dispatch_uid_map = collections.OrderedDict()
        self.connect()

    def __del__(self):
        try:
            self.disconnect()
        except Exception:
            pass

    def __repr__(self):
        return '<UserTracker>'

    def connect_signal(self, signal, signal_name):
        dispatch_uid = 'trails-{}[{}]'.format(signal_name, id(self))
        if dispatch_uid not in self.dispatch_uid_map:
            signal.connect(
                getattr(self, 'on_{}'.format(signal_name)),
                dispatch_uid=dispatch_uid,
            )
            self.dispatch_uid_map[dispatch_uid] = signal
            log_trace('%r: connect %s', self, dispatch_uid)

    def connect(self):
        if self.track_login:
            self.connect_signal(user_logged_in, 'user_logged_in')
        if self.track_logout:
            self.connect_signal(user_logged_out, 'user_logged_out')
        if self.track_failed_login:
            self.connect_signal(user_login_failed, 'user_login_failed')

    def disconnect(self):
        while self.dispatch_uid_map:
            dispatch_uid, signal = self.dispatch_uid_map.popitem(False)
            signal.disconnect(dispatch_uid=dispatch_uid)
            log_trace('%r: disconnect %s', self, dispatch_uid)

    def on_user_logged_in(self, sender, **kwargs):
        log_trace('%r: on_user_logged_in(%r, **%r)', self, sender, kwargs)
        record_trail(
            'login',
            request=kwargs.get('request', None),
            user=kwargs.get('user', None),
        )

    def on_user_logged_out(self, sender, **kwargs):
        log_trace('%r: on_user_logged_out(%r, **%r)', self, sender, kwargs)
        record_trail(
            'logout',
            request=kwargs.get('request', None),
            user=kwargs.get('user', None),
        )

    def on_user_login_failed(self, sender, **kwargs):
        log_trace('%r: on_user_login_failed(%r, **%r)', self, sender, kwargs)
        record_trail(
            'failed-login',
            request=kwargs.get('request', None),
            data=kwargs.get('credentials', None),
        )
