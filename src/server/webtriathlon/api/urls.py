from django.conf.urls.defaults import *

from handlers import *
from piston.resource import Resource

urlpatterns = patterns("",
        url(r'^category/$', Resource(CategoryHandler)),
        url(r'^path/$', Resource(PathHandler)),
        url(r'^station/$', Resource(StationHandler)),
        url(r'^team/(?P<nb>\w+)/$', Resource(TeamHandler)),
        url(r'^team/$', Resource(TeamHandler)),
        url(r'^passage/(?P<uuid>[\w-]+)/$', Resource(PassageHandler)),
        url(r'^passage/$', Resource(PassageHandler)),
        #url(r'^lap/(?P<id>\w+)/$', Resource(LapHandler)),
        #url(r'^lap/$', Resource(LapHandler)),
        url(r'^expected-teams/$', Resource(ExpectedTeamsHandler)),
        url(r'^execute/$', Resource(FunctionHandler)),
        url(r'^$', Resource(ServerInfoHandler)),
        )

