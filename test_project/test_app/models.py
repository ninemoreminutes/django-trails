# Django
from django.conf import settings
from django.db import models

# Django-Polymorphic
from polymorphic.models import PolymorphicModel

# Django-SortedM2M
# from sortedm2m


class AllTheFields(models.Model):
    '''
    Test model with all of the supported Django field types (excluding relations).
    '''

    big_int_val = models.BigIntegerField(default=0)
    # binary_val = models.BinaryField(default='')
    bool_val = models.BooleanField(default=False)
    char_val = models.CharField(max_length=100, default='')
    # csi_val = models.CommaSeparatedIntegerField(max_length=100, default='')
    date_val = models.DateField(null=True, default=None)
    created_dt = models.DateTimeField(auto_now_add=True)
    modified_dt = models.DateTimeField(auto_now=True)
    decimal_val = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    email_val = models.EmailField()
    file_val = models.FileField(upload_to='files')
    file_path_val = models.FilePathField(path='')
    float_val = models.FloatField(default=0.0)
    image_val = models.ImageField(upload_to='images')
    int_val = models.IntegerField(default=0)
    # ip_val = models.IPAddressField()
    generic_ip_val = models.GenericIPAddressField(default='0.0.0.0')
    null_bool_val = models.NullBooleanField()


class UserProfile(models.Model):
    '''
    Test model with a one-to-one field.
    '''

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name='user_profile',
        on_delete=models.CASCADE,
    )
    nickname = models.CharField(
        max_length=100,
        default='',
    )


class UserEmail(models.Model):
    '''
    Test model with foreign key relationship that can be null and related accessor.
    '''

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='emails',
        null=True,
        default=None,
        on_delete=models.SET_NULL,
    )
    email = models.EmailField(
        unique=True,
    )


class Team(models.Model):
    '''
    Test model with a many to many relationship using an explicit through table.
    '''

    name = models.CharField(
        max_length=100,
        unique=True,
    )
    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='teams',
        through='UserTeamAssociation',
        blank=True,
    )


class UserTeamAssociation(models.Model):
    '''
    Test model that is an explicit through table for a many-to-many relationship,
    where foreign key fields do not have a related name defined.
    '''

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='+',
        on_delete=models.CASCADE,
    )
    team = models.ForeignKey(
        'Team',
        related_name='+',
        on_delete=models.CASCADE,
    )
    manager = models.BooleanField(
        default=False,
    )


class Node(models.Model):

    siblings = models.ManyToManyField(
        'self',
        symmetrical=True,
        blank=True,
    )


class Fruit(PolymorphicModel):

    name = models.CharField(max_length=100)


class Apple(Fruit):

    pass


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


# m2m with self = symmetric vs. not
# o2o
# fk with +related_name
# m2m with +related_name
# sortedm2m
