# Django
from django.db import models


class Apple(models.Model):
    """Test model with all built-in Django field types."""

    big_int_val = models.BigIntegerField(default=0)
    #binary_val = models.BinaryField(default='')
    bool_val = models.BooleanField(default=False)
    char_val = models.CharField(max_length=100)
    csi_val = models.CommaSeparatedIntegerField(max_length=100, default='')
    date_val = models.DateField(null=True, default=None)
    created_date = models.DateField(auto_now_add=True)
    modified_date = models.DateField(auto_now=True)
    decimal_val = models.DecimalField(max_digits=10, decimal_places=2)
    email_val = models.EmailField()
    file_val = models.FileField(upload_to='apple_files')
    file_path_val = models.FilePathField(path='')
    float_val = models.FloatField()
    #image_val = models.ImageField(upload_to='apple_images')
    int_val = models.IntegerField()
    ip_val = models.IPAddressField()
    generic_ip_val = models.GenericIPAddressField()
    null_bool_val = models.NullBooleanField()
    # FIXME


class Banana(models.Model):

    name = models.CharField(max_length=100)
    apple = models.ForeignKey('Apple', related_name='bananas', null=True, default=None)


class Cucumber(models.Model):

    name = models.CharField(max_length=100)
    bananas = models.ManyToManyField('Banana', blank=True, related_name='cucumbers')
