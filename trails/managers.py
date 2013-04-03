# Django
from django.db import models

__all__ = ['TrailManager']


class TrailManager(models.Manager):
    """Manager for the Trail class."""

    use_for_related_objects = True
