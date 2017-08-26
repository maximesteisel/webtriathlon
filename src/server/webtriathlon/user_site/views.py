import time
import itertools
from collections import defaultdict
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED


from django import forms, shortcuts, template, http
from django.utils import simplejson
from django.core import serializers
from django.contrib.auth.decorators import login_required


from webtriathlon.api.functions import dispatch

from webtriathlon import LOG, BATCH_MODE
from webtriathlon.core.models import *
from webtriathlon.dynamic.models import *
from webtriathlon.user_site.models import *

from webtriathlon.dynamic.ranking import get_ranking_fast, get_stage_ranking_fast
from webtriathlon.dynamic.path import refresh_laps as _refresh_laps
from webtriathlon.dynamic.path import align_laps as _align_laps
from webtriathlon.misc import *
from webtriathlon.debug import dtime


# Rankings

def all_rankings(request):
    cats = Category.objects.all()
    return shortcuts.render_to_response("user_site/rankings.html", {"categories": cats},
            context_instance=template.RequestContext(request))

def category_ranking(request, category):
    cat = shortcuts.get_object_or_404(Category, id=category)
    teams = Team.objects.filter(category=cat)
    subcats=[]
    for sc in request.GET.getlist("subcat"):
        sc = shortcuts.get_object_or_404(SubCategory, name=sc)
        subcats.append(sc)
        teams = teams.filter(subcategories=sc)
    teams = (t for r, t in get_ranking_fast(teams))

    return dtime(shortcuts.render_to_response)("user_site/ranking.html",
            {"category": cat, "subcats": subcats, "ranking": teams},
            context_instance=template.RequestContext(request))

def refresh_ranking(request, category):
    c = shortcuts.get_object_or_404(Category, pk=category)
    for t in c.team_set.all():
        t.state.refresh()
    return http.HttpResponseRedirect(c.get_absolute_url())

# Team information and list of laps

def team_laps(request, nb):
    team = shortcuts.get_object_or_404(Team, nb=nb)

    return shortcuts.render_to_response("user_site/team.html", {"team": team,},
            context_instance=template.RequestContext(request))

def refresh_laps(request, team):
    """ This view force immediate recaculation of the laps of a team """
    t = shortcuts.get_object_or_404(Team, nb=team)
    _refresh_laps(t)
    return http.HttpResponseRedirect(t.get_absolute_url())

@login_required
def align_laps(request, team):
    """ This view force immediate recalculation of the laps of a team,
    and allow changing the stage of a lap to correct 'too many laps in stage' errors """
    t = shortcuts.get_object_or_404(Team, nb=team)
    _align_laps(t)
    return http.HttpResponseRedirect(t.get_absolute_url())

def status(request):
    last_seen_teams = Team.last_seen()[:10]
    waited_teams = Team.expected()[:10]
    all_teams = Team.objects.all()
    announcements = Announcement.objects.all()

    return shortcuts.render_to_response("user_site/status.html", locals(),
            context_instance=template.RequestContext(request))


