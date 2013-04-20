# Django
from django.test import TestCase
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User, Group

# Django-Trails
from trails.models import *
from trails.middleware import *
from trails.utils import *


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

    def test_middleware(self):
        self.assertEqual(get_current_user(), None)
        url = reverse('test_app:index')
        # Test anonymous user.
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, 'AnonymousUser')
        self.assertEqual(get_current_user(), None)
        # Test logged in user.
        self.client.login(username=self.users[0].username,
                          password=self.user_passwords[0])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, unicode(self.users[0]))
        self.assertEqual(get_current_user(), None)
        # Test impersonate context manager.
        with impersonate(self.users[0]):
            self.assertEqual(get_current_user(), self.users[0])
        self.assertEqual(get_current_user(), None)
        # Test impersonate(None) within view requested by logged in user.
        self.client.login(username=self.users[0].username,
                          password=self.user_passwords[0])
        response = self.client.get(url + '?impersonate=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, unicode(None))
        self.assertEqual(get_current_user(), None)
        # Test when request raises exception.
        try:
            response = self.client.get(url + '?raise=1')
        except RuntimeError:
            response = None
        self.assertEqual(response, None)
        self.assertEqual(get_current_user(), None)

    def test_serialize_instance(self):
        # Test normal serialization.
        user = User.objects.get(pk=self.users[0].pk)
        user_dict = serialize_instance(user)
        self.assertEqual(user_dict['pk'], user.pk)
        self.assertEqual(user_dict['username'], user.username)
        self.assertEqual(set(user_dict['groups']),
                         set(user.groups.values_list('pk', flat=True)))
        # Test that serialization defaults to in-memory version of object.
        user = User.objects.get(pk=self.users[0].pk)
        user.first_name = 'Firsty'
        user_dict = serialize_instance(user)
        self.assertEqual(user_dict['first_name'], 'Firsty')
        # Test serialization before (retrieves unmodified from database).
        user = User.objects.get(pk=self.users[0].pk)
        original_last_name = user.last_name
        user.last_name = 'Lasterson'
        user_dict = serialize_instance(user, before=True)
        self.assertEqual(user_dict['last_name'], original_last_name)

    def _test_admin(self):
        raise NotImplementedError

    def _test_trails(self):
        raise NotImplementedError
