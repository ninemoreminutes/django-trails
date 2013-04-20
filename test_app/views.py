# Django
from django.http import HttpResponse

# Django-Trails
from trails.api import get_current_user, impersonate


def index(request):
    if request.GET.get('raise', ''):
        raise RuntimeError()
    if request.GET.get('impersonate', ''):
        with impersonate(None):
            current_user = unicode(get_current_user())
    else:
        current_user = unicode(get_current_user())
    return HttpResponse(current_user, content_type='text/plain')
