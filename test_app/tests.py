from __future__ import with_statement

# Python
from copy import copy
import urlparse

# BeautifulSoup4
from bs4 import BeautifulSoup

# Django
from django.test import TestCase
from django.test.signals import template_rendered
from django.test.utils import ContextList
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.db.models.signals import pre_save, post_save

# Django-CRUM
from crum import get_current_user, impersonate

# Django-Trails
from trails.models import *
from trails.signals import model_added, model_changed, model_deleted
from trails.utils import *


class AssertTemplateUsedContext(object):
    # Borrowed from Django >= 1.4 to test using Django 1.3.

    def __init__(self, test_case, template_name):
        self.test_case = test_case
        self.template_name = template_name
        self.rendered_templates = []
        self.rendered_template_names = []
        self.context = ContextList()

    def on_template_render(self, sender, signal, template, context, **kwargs):
        self.rendered_templates.append(template)
        self.rendered_template_names.append(template.name)
        self.context.append(copy(context))

    def test(self):
        return self.template_name in self.rendered_template_names

    def message(self):
        return '%s was not rendered.' % self.template_name

    def __enter__(self):
        template_rendered.connect(self.on_template_render)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        template_rendered.disconnect(self.on_template_render)
        if exc_type is not None:
            return

        if not self.test():
            message = self.message()
            if len(self.rendered_templates) == 0:
                message += ' No template was rendered.'
            else:
                message += ' Following templates were rendered: %s' % (
                    ', '.join(self.rendered_template_names))
            self.test_case.fail(message)


class TestSignalHandler(object):

    def __init__(self):
        self.reset()

    def __call__(self, sender, **kwargs):
        self.sender, self.kwargs = sender, kwargs

    def __nonzero__(self):
        return bool(self.sender and self.kwargs)

    def get(self, key, default=None):
        return self.kwargs.get(key, default)

    def reset(self):
        self.sender, self.kwargs = None, {}


class TestTrails(TestCase):
    """Test cases for the trails app."""

    def setUp(self):
        super(TestTrails, self).setUp()
        self.user_passwords = []
        self.users = []
        self.groups = []
        self.superuser_password = User.objects.make_random_password()
        self.superuser = User.objects.create_superuser('admin', 'adm@ixmm.net',
                                                       self.superuser_password)

    def create_test_users_and_groups(self, n=2, prefix=''):
        for x in xrange(n):
            user_password = User.objects.make_random_password()
            self.user_passwords.append(user_password)
            username = '%suser%d' % (prefix, x)
            user = User.objects.create_user(username, '%s@ixmm.net' % username,
                                            user_password)
            self.users.append(user)
            group = Group.objects.create(name='%sgroup%d' % (prefix, x))
            self.groups.append(group)
            if x % 2:
                user.groups.add(group)
            else:
                group.user_set.add(user)

    def test_middleware(self):
        self.create_test_users_and_groups()
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
        self.create_test_users_and_groups()
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

    def test_model_added(self):
        # Test that the model_added signal is called when an instance is added.
        tsh = TestSignalHandler()
        model_added.connect(tsh)
        self.assertFalse(tsh)
        group = Group.objects.create(name='Trail Blazers')
        self.assertTrue(tsh)
        self.assertEqual(tsh.sender, Group)
        self.assertEqual(tsh.get('instance'), group)
        # Shouldn't be called when an instance is created in memory, but only
        # when it is saved.
        tsh.reset()
        self.assertFalse(tsh)
        group = Group(name='Path Finders')
        self.assertFalse(tsh)
        group.save()
        self.assertTrue(tsh)
        self.assertEqual(tsh.sender, Group)
        self.assertEqual(tsh.get('instance'), group)

    def test_model_changed(self):
        # Test that the model_changed signal is called when an instance is
        # changed.
        tsh = TestSignalHandler()
        model_changed.connect(tsh)
        self.assertFalse(tsh)
        group = Group.objects.create(name='Trail Blazers')
        self.assertFalse(tsh)
        group.name = 'Path Finders'
        self.assertFalse(tsh)
        group.save()
        self.assertTrue(tsh)
        self.assertEqual(tsh.sender, Group)
        self.assertEqual(tsh.get('instance'), group)
        self.assertTrue(tsh.get('changes'))
        self.assertTrue(tsh.get('changes').get('name'))
        self.assertEqual(tsh.get('changes').get('name')[0], 'Trail Blazers')
        self.assertEqual(tsh.get('changes').get('name')[1], 'Path Finders')
        # For now, model_changed isn't called for a bulk update.
        tsh.reset()
        self.assertFalse(tsh)
        Group.objects.filter(pk=group.pk).update(name='Explorers')
        self.assertFalse(tsh)

    def test_model_deleted(self):
        # Test that the model_deleted signal is called when an instance is
        # deleted.
        tsh = TestSignalHandler()
        model_deleted.connect(tsh)
        self.assertFalse(tsh)
        group = Group.objects.create(name='Trail Blazers')
        group_pk = group.pk
        self.assertFalse(tsh)
        group.delete()
        self.assertTrue(tsh)
        self.assertEqual(tsh.sender, Group)
        #self.assertEqual(tsh.get('instance').pk, group_pk)
        # Test that model_deleted is called for a bulk delete.
        tsh.reset()
        group = Group.objects.create(name='Explorers')
        group_pk = group.pk
        self.assertFalse(tsh)
        Group.objects.filter(pk=group.pk).delete()
        self.assertTrue(tsh)
        self.assertEqual(tsh.sender, Group)
        #self.assertEqual(tsh.get('instance').pk, group_pk)

    def test_model(self):
        pre_tsh = TestSignalHandler()
        pre_save.connect(pre_tsh)
        post_tsh = TestSignalHandler()
        post_save.connect(post_tsh)
        # Content unicode should be set automatically.
        trail = Trail.objects.create(**{
            'user': self.superuser,
            'user_unicode': unicode(self.superuser),
            'content_type': ContentType.objects.get_for_model(self.superuser),
            'object_id': self.superuser.pk,
            'action': 'some other action',
        })
        self.assertTrue(trail.content_unicode)
        self.assertTrue(pre_tsh)
        self.assertTrue(post_tsh)
        # Model should never save again after initially created.
        pre_tsh.reset()
        post_tsh.reset()
        self.assertFalse(pre_tsh)
        self.assertFalse(post_tsh)
        trail.save()
        self.assertFalse(pre_tsh)
        self.assertFalse(post_tsh)

    def test_manager_for_models(self):
        with impersonate(self.superuser):
            self.create_test_users_and_groups()
        # All normal users.
        instances = self.users
        trails = Trail.objects.for_models(*instances)
        self.assertTrue(trails.count())
        for trail in trails:
            self.assertTrue(trail.content_object in instances)
        # All normal groups.
        instances = self.groups
        trails = Trail.objects.for_models(*instances)
        self.assertTrue(trails.count())
        for trail in trails:
            self.assertTrue(trail.content_object in instances)
        # Mix of user and group.
        instances = [self.users[0], self.groups[0]]
        trails = Trail.objects.for_models(*instances)
        self.assertTrue(trails.count())
        for trail in trails:
            self.assertTrue(trail.content_object in instances)
        # Multiples of one type, mixed with another type.
        instances = self.users + [self.groups[0]]
        trails = Trail.objects.for_models(*instances)
        self.assertTrue(trails.count())
        for trail in trails:
            self.assertTrue(trail.content_object in instances)
        # Passing None as an instance should work, but return no trails.
        instances = [None]
        trails = Trail.objects.for_models(*instances)
        self.assertFalse(trails.count())
        # Passing a single Queryset instead of a list.
        instances = Group.objects.all()
        trails = Trail.objects.for_models(*instances)
        self.assertTrue(trails.count())
        for trail in trails:
            self.assertTrue(trail.content_object in instances)
        # Passing a list of Querysets.
        instances = [Group.objects.all(), User.objects.all()]
        trails = Trail.objects.for_models(*instances)
        self.assertTrue(trails.count())
        for trail in trails:
            self.assertTrue(trail.content_object in instances[0] or
                            trail.content_object in instances[1])

    def test_render(self):
        # Create test user/group data with changes/deletes.
        with impersonate(self.superuser):
            self.create_test_users_and_groups()
            user = self.users[0]
            user.first_name = 'Firsty'
            user.last_name = 'The Userman'
            user.save()
            user = self.users[1]
            user.delete()
            group = self.groups[0]
            group.name = 'Grouper Gropers'
            group.save()
            group = self.groups[1]
            group.delete()
            site = Site.objects.get_current()
            site.name = 'example.org'
            site.domain = 'example.org'
            site.save()
        # Verify that each trail is rendered with the appropriate template.
        for trail in Trail.objects.all():
            template_key = (trail.content_type.model_class(), trail.action)
            html_template = {
                (Group, 'add'):     'trails/auth/group/add.html',
                (Group, 'change'):  'trails/auth/group/default.html',
                (Group, 'delete'):  'trails/auth/group/default.html',
                (User, 'add'):      'trails/auth/default.html',
                (User, 'change'):   'trails/auth/user/change.html',
                (User, 'delete'):   'trails/auth/delete.html',
            }.get(template_key, 'trails/default.html')
            txt_template = {
                (Site, 'change'):   'trails/sites/change.txt',
            }.get(template_key, 'trails/_default.txt')
            with AssertTemplateUsedContext(self, html_template):
                trail.render('html')
            with AssertTemplateUsedContext(self, txt_template):
                trail.render('txt')

    def test_admin(self):
        app_label = Trail._meta.app_label
        model_name = (getattr(Trail._meta, 'model_name', None) or
                      getattr(Trail._meta, 'module_name', None))
        self.assertTrue(model_name)
        self.client.login(username=self.superuser.username,
                          password=self.superuser_password)
        with impersonate(self.superuser):
            self.create_test_users_and_groups()
        with impersonate(self.users[0]):
            self.create_test_users_and_groups(prefix='extra')
        with impersonate(self.superuser):
            self.users[0].delete()
            self.users.pop(0)
            self.user_passwords.pop(0)
        self.assertTrue(Trail.objects.count())
        # Change list view.
        changelist_url = reverse('admin:%s_%s_changelist' %
                                 (app_label, model_name))
        response = self.client.get(changelist_url)
        self.assertEquals(response.status_code, 200)
        for trail in Trail.objects.all():
            change_url = reverse('admin:%s_%s_change' %
                                 (app_label, model_name), args=(trail.pk,))
            change_url_found = False
            soup = BeautifulSoup(response.content)
            for atag in soup.findAll('a', href=True):
                target_url = urlparse.urljoin(changelist_url, atag['href'])
                if target_url == change_url:
                    change_url_found = True
                    break
            self.assertTrue(change_url_found)
        # Change view (should have no editable fields).
        response = self.client.get(change_url)
        self.assertEquals(response.status_code, 200)
        soup = BeautifulSoup(response.content)
        for fs in soup.findAll('fieldset'):
            self.assertFalse(fs.findAll('input'))
            self.assertFalse(fs.findAll('select'))
            self.assertFalse(fs.findAll('textarea'))
        # Delete view via GET, then POST.
        delete_url = reverse('admin:%s_%s_delete' % (app_label, model_name),
                             args=(trail.pk,))
        response = self.client.get(delete_url)
        self.assertEquals(response.status_code, 200)
        # Add view should raise a 403.
        add_url = reverse('admin:%s_%s_add' % (app_label, model_name))
        response = self.client.get(add_url)
        self.assertEquals(response.status_code, 403)
        # FIXME: History view (normal vs. override)

    def test_m2m(self):
        self.create_test_users_and_groups()
        for group in Group.objects.all():
            for user in group.user_set.all():
                group.user_set.remove(user)
                break
            group.user_set.clear()
        
        raise NotImplementedError
