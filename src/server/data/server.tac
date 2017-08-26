#!/usr/bin/twistd -ny 
import sys
import os

from twisted.application import internet, service
from twisted.web import server, resource, wsgi, static
from twisted.python import threadpool
from twisted.internet import reactor

from django.core.management import call_command

DJANGO_APP_NAME = "webtriathlon"
PORT = 8000
try:
    if os.getuid() == 0:
        PORT = 80
except Exception:
    pass

# Environment setup for your Django project files:
SETTINGS_MODULE = '%s.settings'%DJANGO_APP_NAME
os.environ['DJANGO_SETTINGS_MODULE'] = SETTINGS_MODULE

from webtriathlon import settings

import django
DJANGO_ROOT_PATH = os.path.dirname(django.__file__)

ROOT_PATH = sys.argv[0]

SITE_MEDIA_PATH = settings.MEDIA_ROOT
SITE_MEDIA_URL = settings.MEDIA_URL.strip("/")

sys.path.pop(0) # remove current dir
sys.path.insert(0, ROOT_PATH)


from django.core.handlers.wsgi import WSGIHandler

class Root(resource.Resource):
    def __init__(self, wsgi_resource):
        resource.Resource.__init__(self)
        self.wsgi_resource = wsgi_resource

    def getChild(self, path, request):
        path0 = request.prepath.pop(0)
        request.postpath.insert(0, path0)
        return self.wsgi_resource

def wsgi_resource():
    pool = threadpool.ThreadPool()
    pool.start()
    # Allow Ctrl-C to get you out cleanly:
    reactor.addSystemEventTrigger('after', 'shutdown', pool.stop)
    wsgi_resource = wsgi.WSGIResource(reactor, pool, WSGIHandler())
    return wsgi_resource


# Twisted Application Framework setup:
application = service.Application('twisted-django')

# WSGI container for Django, combine it with twisted.web.Resource:
# XXX this is the only 'ugly' part: see the 'getChild' method in Root 
wsgi_root = wsgi_resource()
root = Root(wsgi_root)

# Servce Django media files off of SITE_MEDIA_URL:
staticrsrc = static.File(SITE_MEDIA_PATH)
root.putChild(SITE_MEDIA_URL, staticrsrc)
print SITE_MEDIA_PATH
print SITE_MEDIA_URL

# Serve it up:
main_site = server.Site(root)
internet.TCPServer(PORT, main_site).setServiceParent(application)


import webtriathlon.monkeypatch

from webtriathlon.dynamic.async import start_workers, create_all
from webtriathlon.dynamic.errors import check_all
create_all()
check_all()

start_workers()
