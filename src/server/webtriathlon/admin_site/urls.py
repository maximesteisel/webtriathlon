from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template

from webtriathlon import LOG
from webtriathlon.misc import get_all_models

from webtriathlon import user_site
from webtriathlon.admin_site import views

urlpatterns = patterns('',
    (r'^modified_passages/$', views.modified),
    (r'^deleted_passages/$', views.deleted),
    (r'^disqualified_teams/$', views.disqualified),
    (r'^errors/$', views.errors),
    (r'^jobs/$', views.jobs),
    (r'^add_team/$', views.add_team),
    (r'^add_passages/$', views.add_passages),
    (r'^refresh_all/$', views.refresh_all),
    (r'^refresh_errors/$', views.refresh_errors),
    (r'^align_all/$', views.align_all),
    (r'^create_all/$', views.create_all),
    (r'^delete_passages/$', views.delete_passages),
    (r'^delete_all/$', views.delete_all),
    (r'^open/', views.open),
    (r'^open_passages/', views.open_passages),
    (r'^success/', direct_to_template, {"template": "save/sucess.html"}),
    (r'^error/', direct_to_template, {"template": "save/error.html"}),
    (r'^save/', views.save, {"models": get_all_models()}),
    (r'^ranking/', views.printable_ranking),
    (r'^teams/', views.printable_teams),
    (r'^stats/', views.printable_stats),
    (r'^$', direct_to_template, {"template": "admin_tools/index.html"}),
    )
