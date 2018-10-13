# Django
from django.db import models

# Django-Polymorphic
from polymorphic.models import PolymorphicModel


class Fruit(PolymorphicModel):

    name = models.CharField(max_length=100)


class Apple(Fruit):
    """Test model with all built-in Django field types."""

    big_int_val = models.BigIntegerField(default=0)
    #binary_val = models.BinaryField(default='')
    bool_val = models.BooleanField(default=False)
    char_val = models.CharField(max_length=100)
    #csi_val = models.CommaSeparatedIntegerField(max_length=100, default='')
    date_val = models.DateField(null=True, default=None)
    created_date = models.DateField(auto_now_add=True)
    modified_date = models.DateField(auto_now=True)
    decimal_val = models.DecimalField(max_digits=10, decimal_places=2)
    email_val = models.EmailField()
    file_val = models.FileField(upload_to='apple_files')
    file_path_val = models.FilePathField(path='')
    float_val = models.FloatField()
    image_val = models.ImageField(upload_to='apple_images')
    int_val = models.IntegerField()
    #ip_val = models.IPAddressField()
    generic_ip_val = models.GenericIPAddressField()
    null_bool_val = models.NullBooleanField()
    # FIXME


class Banana(Fruit):

    the_apple = models.ForeignKey(  # Can't be named `apple` with polymorphic.
        'Apple',
        related_name='bananas',
        on_delete=models.SET_NULL,
        null=True,
        default=None,
    )


class Cherry(Fruit):

    bananas = models.ManyToManyField(
        'Banana',
        related_name='cherries',
        blank=True,
    )
