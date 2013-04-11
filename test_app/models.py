# Django
from django.db import models


class A(models.Model):
    """Test model with all built-in Django field types."""

    big_int_val = models.BigIntegerField(default=0)
    #binary_val = models.BinaryField(default='')
    bool_val = models.BooleanField(default=False)
    char_val = models.CharField(max_length=100)
    csi_val = models.CommaSeparatedIntegerField(max_length=100, default='')
    date_val = models.DateField(null=True, default=None)
    created_date = models.DateField(auto_now_add=True)
    modified_date = models.DateField(auto_now=True)


class B(models.Model):

    name = models.CharField(max_length=100)


class C(models.Model):

    name = models.CharField(max_length=100)
