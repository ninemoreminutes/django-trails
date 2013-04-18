# Django
from django.http import HttpResponse

# Django-Trails
from trails.api import get_current_user


def index(request):
    if request.GET.get('raise', ''):
        raise RuntimeError()
    return HttpResponse(unicode(get_current_user()), content_type='text/plain')
