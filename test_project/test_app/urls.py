# Django
from django.urls import re_path

# Test App
from .views import index


urlpatterns = [
    re_path(r'^$', index, name='index'),
]
