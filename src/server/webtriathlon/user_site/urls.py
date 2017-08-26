from django.conf.urls.defaults import *
from django.views.generic.simple import redirect_to, direct_to_template

from webtriathlon.user_site import views

urlpatterns = patterns('',
        (r'^$', redirect_to, {"url": "/status/"}),
        (r'^status/$', views.status),
        (r'^category/$', views.all_rankings),
        (r'^category/(\d+)/$', views.category_ranking),
        (r'^category/(\d+)/refresh/$', views.refresh_ranking),
        (r'^team/(\d+)/$', views.team_laps),
        (r'^team/(\d+)/refresh/$', views.refresh_laps),
        (r'^team/(\d+)/align/$', views.align_laps),
    )
