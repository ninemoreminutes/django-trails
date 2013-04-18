# Python
import contextlib
import threading

_thread_locals = threading.local()

__all__ = ['get_current_user', 'impersonate']


@contextlib.contextmanager
def impersonate(user=None):
    """Temporarily impersonate the given user for audit trails."""
    try:
        current_user = get_current_user()
        set_current_user(user)
        yield user
    finally:
        set_current_user(current_user)


def get_current_user():
    """Return the user associated with the current request thread."""
    return getattr(_thread_locals, 'user', None)


def set_current_user(user):
    """Update the user associated with the current request thread."""
    _thread_locals.user = user


class RequestUserMiddleware(object):
    """Middleware to capture the current user from the request object."""

    def process_request(self, request):
        from django.contrib.auth import get_user
        set_current_user(get_user(request))

    def process_response(self, request, response):
        set_current_user(None)
        return response

    def process_exception(self, request, exception):
        set_current_user(None)
