# Python
import collections
import fnmatch

# Django
from django.apps import apps
from django.db import models

# Django-Trails
from .settings import trails_settings
from .tracker import ModelTracker, ManyToManyTracker, UserTracker

__all__ = ['registry']


class ModelRegistry(object):
    '''
    Registry of model classes and ModelTracker instances for each model.
    '''

    def __init__(self):
        self.model_trackers = collections.OrderedDict()
        self.m2m_trackers = collections.OrderedDict()
        self.user_tracker = None

    def add(self, model_class, model_fields):
        model_tracker = self.model_trackers.get(model_class, None)
        if not model_tracker or model_tracker.model_fields != model_fields:
            self.model_trackers[model_class] = ModelTracker(model_class, model_fields)

    def remove(self, model_class):
        model_tracker = self.model_trackers.pop(model_class, None)
        if model_tracker:
            model_tracker.disconnect()

    def add_m2m(self, m2m_model_class, related_model_fields):
        m2m_tracker = self.m2m_trackers.get(m2m_model_class, None)
        if not m2m_tracker or m2m_tracker.related_model_fields != related_model_fields:
            self.m2m_trackers[m2m_model_class] = ManyToManyTracker(m2m_model_class, related_model_fields)

    def remove_m2m(self, m2m_model_class):
        m2m_tracker = self.m2m_trackers.pop(m2m_model_class, None)
        if m2m_tracker:
            m2m_tracker.disconnect()

    def update_from_settings(self):
        model_label_map = collections.OrderedDict()  # Model label -> model class.
        model_class_map = collections.OrderedDict()  # Model class -> include/exclude boolean.
        model_field_map = collections.OrderedDict()  # Model class -> field name -> field action.
        model_field_label_map = collections.OrderedDict()  # app.model.field -> (model class, field name).

        # Build mappings of models and fields.
        for app_config in apps.get_app_configs():
            for model_class in app_config.get_models():
                opts = model_class._meta

                # Indicate model class is neither explicitly included or excluded.
                model_class_map[model_class] = None

                # Add mapping by app_label.modelname
                model_label = '{}.{}'.format(opts.app_label, opts.model_name)
                model_label_map[model_label.lower()] = model_class

                # Add alternate mapping by app.full.path.modelname
                model_label_alt = '{}.{}'.format(opts.app_config.name, opts.model_name)
                model_label_map[model_label_alt.lower()] = model_class

                # Build mapping of model fields for each model class.
                model_field_map[model_class] = collections.OrderedDict()
                for field in opts.get_fields(include_hidden=True):
                    if hasattr(field, 'get_accessor_name'):
                        field_name = field.get_accessor_name()
                    else:
                        field_name = getattr(field, 'attname', field.name)
                    if field.many_to_many and field_name:
                        m2m_model_class = getattr(model_class, field_name).through
                        model_field_map[model_class][field_name] = m2m_model_class
                    elif not field.concrete:
                        continue
                    elif not field.is_relation:
                        model_field_map[model_class][field_name] = True
                    else:
                        if field.one_to_one or (field.many_to_one and field.related_model):
                            if field_name != field.name:
                                model_field_map[model_class][field.name] = True
                                model_field_map[model_class][field_name] = (field.name, field.related_model)  # fk_field_id -> (fk_field, rel_model)
                            else:
                                model_field_map[model_class][field_name] = True

                # Update mapping of app.model.field labels from model fields.
                for field_name, field_status in model_field_map[model_class].items():
                    field_label = '{}.{}.{}'.format(opts.app_label, opts.model_name, field_name)
                    model_field_label_map[field_label.lower()] = (model_class, field_name)

        # Explicitly include models matching configured include patterns.
        for include_pattern in trails_settings.INCLUDE_MODELS:
            include_labels = fnmatch.filter(model_label_map.keys(), include_pattern.lower())
            if not include_labels:
                print('warning: include pattern does not match any known models', include_pattern)
            for include_label in include_labels:
                model_class = model_label_map[include_label]
                model_class_map[model_class] = True

        # Explicitly exclude models matching configured exclude patterns.
        for exclude_pattern in trails_settings.EXCLUDE_MODELS:
            exclude_labels = fnmatch.filter(model_label_map.keys(), exclude_pattern.lower())
            if not exclude_labels:
                print('warning: exclude pattern does not match any known models', exclude_pattern)
            for exclude_label in exclude_labels:
                model_class = model_label_map[exclude_label]
                model_class_map[model_class] = False

        # Always exclude trails model(s).
        if 'trails.trail' in model_label_map:
            model_class = model_label_map['trails.trail']
            model_class_map[model_class] = False
        if 'trails.trailmarker' in model_label_map:
            model_class = model_label_map['trails.trailmarker']
            model_class_map[model_class] = False

        # Explicitly exclude fields matching configured exclude patterns.
        for field_pattern in trails_settings.EXCLUDE_FIELDS:
            field_labels = fnmatch.filter(model_field_label_map.keys(), field_pattern.lower())
            if not field_labels:
                print('warning: exclude pattern does not match any known fields', field_pattern)
            for field_label in field_labels:
                model_class, field_name = model_field_label_map[field_label]
                model_field_map[model_class][field_name] = False

        # Mark sensitive fields matching configured field patterns.
        for field_pattern in trails_settings.SENSITIVE_FIELDS:
            field_labels = fnmatch.filter(model_field_label_map.keys(), field_pattern.lower())
            if not field_labels:
                print('warning: sensitive fields pattern does not match any known fields', field_pattern)
            for field_label in field_labels:
                model_class, field_name = model_field_label_map[field_label]
                if model_field_map[model_class][field_name] is True:
                    model_field_map[model_class][field_name] = '__SENSITIVE__'

        # Update registry with models included/excluded.
        for model_class, model_included in model_class_map.items():
            if model_included:
                model_fields = model_field_map[model_class]
                self.add(model_class, model_fields)
            else:
                self.remove(model_class)

        # Build mapping of M2M model classes to the (model_class, field_name) of
        # each side of the M2M relationship.
        m2m_model_classes = collections.OrderedDict()
        for model_class, model_included in model_class_map.items():
            model_fields = model_field_map[model_class]
            for field_name, field_action in model_fields.items():
                if not isinstance(field_action, type) or not issubclass(field_action, models.Model):
                    continue
                m2m_model_class = field_action
                m2m_related_model_fields = m2m_model_classes.setdefault(m2m_model_class, collections.OrderedDict())
                m2m_related_model_fields[(model_class, field_name)] = model_included

        # Update registry with many to many models included/excluded.
        for m2m_model_class, related_model_fields in m2m_model_classes.items():
            if any(related_model_fields.values()):
                self.add_m2m(m2m_model_class, set(related_model_fields.keys()))
            else:
                self.remove_m2m(m2m_model_class)

        # Register a single tracker for user login/logout signals.
        self.user_tracker = UserTracker(
            track_login=trails_settings.TRACK_LOGIN,
            track_logout=trails_settings.TRACK_LOGOUT,
            track_failed_login=trails_settings.TRACK_FAILED_LOGIN,
        )


registry = ModelRegistry()
