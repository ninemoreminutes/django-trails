# Django
from django.test import TestCase
from django.contrib.auth.models import User, Group

# Django-Trails
from trails.models import *


class TestTrails(TestCase):
    """Test cases for the trails app."""

    def setUp(self):
        super(TestTrails, self).setUp()
        self.user_passwords = []
        self.users = []
        self.groups = []
        for x in xrange(2):
            user_password = User.objects.make_random_password()
            self.user_passwords.append(user_password)
            user = User.objects.create_user('user%d' % x, None, user_password)
            self.users.append(user)
            group = Group.objects.create(name='group%d' % x)
            self.groups.append(group)
            user.groups.add(group)

    def test_trails(self):
        raise NotImplementedError
