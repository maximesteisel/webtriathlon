import os

from django.conf.urls.defaults import *
from django.conf import settings

from django.contrib import admin

### Import admin modules here because they need to be imported soonish
import webtriathlon.core.admin

if settings.DEBUG:
    import webtriathlon.dynamic.admin

urlpatterns = patterns('',
    (r'^accounts/login/$', 'django.contrib.auth.views.login',
        {'template_name': 'admin/login.html'}),

    (r'^media/(?P<path>.*)$', 'django.views.static.serve', {'document_root':
        settings.MEDIA_ROOT }),

    (r'files/(?P<path>.*)$', 'django.views.static.serve', {'document_root':
        os.path.join(settings.MEDIA_ROOT, "files") }),

    (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    (r'^admin/', include(admin.site.urls)),

    (r'^api/', include("webtriathlon.api.urls")),
    (r'^admin_tools/', include("webtriathlon.admin_site.urls")),
    (r'^', include("webtriathlon.user_site.urls")),
)
