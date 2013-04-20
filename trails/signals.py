# Django
from django.dispatch import Signal

# Django-Trails
from trails.utils import serialize_instance, record_trail

__all__ = []

# Signals used internally for capturing model changes.
model_added = Signal(providing_args=['instance', 'raw', 'using'])
model_changed = Signal(providing_args=['instance', 'raw', 'using', 'changes'])
model_deleted = Signal(providing_args=['instance', 'raw', 'using'])


def on_model_added(sender, **kwargs):
    record_trail('add', kwargs.get('instance', None),
                 serialize_instance(kwargs.get('instance')))
model_added.connect(on_model_added)


def on_model_changed(sender, **kwargs):
    record_trail('change', kwargs.get('instance', None),
                 kwargs.get('changes', {}))
model_changed.connect(on_model_changed)


def on_model_deleted(sender, **kwargs):
    record_trail('delete', kwargs.get('instance', None))
model_deleted.connect(on_model_deleted)

# Future: Signal to allow customizable filtering of what is recorded.
#trail_should_log = Signal(providing_args=['action', 'instance', 'data',
#                                          'user'])
