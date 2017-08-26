# coding: utf-8
import time
import threading
from twisted.internet import reactor
from datetime import datetime

from django.db.models.signals import pre_save, post_save, post_delete, m2m_changed
from django.core.signals import request_started


from webtriathlon import LOG, BATCH_MODE

from webtriathlon.core.models import *
from webtriathlon.debug import dtime
from webtriathlon.dynamic.path import *
from webtriathlon.misc import last_or_none, randid
from webtriathlon.dynamic.ranking import *
from webtriathlon.dynamic.models import *
from webtriathlon.dynamic.path import *

MIN_DELTA = 60

def initialize_team(sender, instance, **others):
# not instance.path can raise Path.DoesNotExist
    try:
        if not instance.path:
            instance.path = get_default_path(instance.category)
    except Path.DoesNotExist:
        instance.path = get_default_path(instance.category)

def initialize_person(sender, instance, **others):
    if not instance.uuid:
        instance.uuid = randid()

def initialize_passage(sender, instance, **others):
    if not instance.uuid:
        instance.uuid = randid()
    if not instance.stage:
        instance.stage = find_stage(instance)
        instance.start = not instance.stage

def initialize_stage(sender, instance, **others):
    if not instance.pk:
        instance.index = instance.path.stage_set.all().count()


def enum_stages(sender, instance, **others):
    path = instance.path
    for i, s in enumerate(path):
        if s.index != i:
            s.index = i
            s.save()

def team_refresh_state(instance, **others):
    print "team refresh state"
    instance.state.refresh()

def passage_refresh_state(instance, **others):
    instance.team.state.refresh()

def pre_initialize(sender, instance, **others):
    if not instance.pk:
        instance.compute()

def post_initialize(instance, created, **others):
    if created:
        instance.refresh()

def ignore_view(obj):
    def wrapped(request):
        obj._checked = True
        try:
            obj.save()
        except IntegrityError:
            pass
        return HttpResponseRedirect(obj.get_absolute_url())
    return wrapped

def fix_view(function, obj):
    def wrapped(request):
        if function:
            function(obj)
        if hasattr(function, "redirect_to"):
            return HttpResponseRedirect(function.redirect_to)
        else:
            return HttpResponseRedirect(obj.get_absolute_url())
    return wrapped

def create_fix_url(sender, instance, created, **others):
    from webtriathlon.urls import urlpatterns, patterns
    if created:
        urlpatterns += patterns('',
                (instance.get_url(), fix_view(instance.fix_f, instance.target)),
                (instance.get_ignore_url(), ignore_view(instance.target)),
                )

def register_all(pre_initialize_models=(), post_initialize_models=()):
    LOG.debug( "registering signals" )
    pre_save.connect(initialize_team, sender=Team)
    pre_save.connect(initialize_passage, sender=Passage)
    pre_save.connect(initialize_person, sender=Person)
    post_save.connect(enum_stages, sender=Stage)
    post_delete.connect(enum_stages, sender=Stage)
    post_save.connect(team_refresh_state, sender=Team)
    post_save.connect(passage_refresh_state, sender=Passage)
    post_save.connect(create_fix_url, sender=Error)

    for m in pre_initialize_models:
        pre_save.connect(pre_initialize, sender=m)
    for m in post_initialize_models:
        post_save.connect(post_initialize, sender=m)


