# Django
from django.conf import settings
from django.contrib import admin
try:
    from django.urls import include, re_path
except ImportError:
    raise
    from django.conf.urls import include, url as re_path


admin.autodiscover()

urlpatterns = [
    re_path(r'^admin/', admin.site.urls),
    re_path(r'^test_app/', include('test_project.test_app.urls')),
]

if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            re_path(r'^__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass

if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
