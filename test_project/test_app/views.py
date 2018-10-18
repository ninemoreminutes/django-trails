from __future__ import with_statement

# Django
from django.http import HttpResponse
from django.utils.encoding import smart_text

# Django-CRUM
from crum import get_current_user, impersonate


def index(request):
    if request.GET.get('raise', ''):
        raise RuntimeError()
    if request.GET.get('impersonate', ''):
        with impersonate(None):
            current_user = smart_text(get_current_user())
    else:
        current_user = smart_text(get_current_user())
    return HttpResponse(current_user, content_type='text/plain')
