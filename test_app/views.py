# Django
from django.http import HttpResponse

# Django-Trails
from trails import get_current_user


def index(request):
    return HttpResponse(unicode(get_current_user()), content_type='text/plain')
