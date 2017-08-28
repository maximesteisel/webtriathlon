# coding: utf-8
import time
import random
from datetime import timedelta
from heapq import nsmallest
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED


from django import forms
from django.forms.formsets import formset_factory
from django.http import *
from django.core import serializers
from django.shortcuts import render_to_response, get_object_or_404
from django.utils import simplejson
from django.contrib.auth.decorators import login_required
from django.contrib.admin import widgets
from django.template import loader, Context
from django.db import transaction
from django.db.models import Count


from webtriathlon import LOG, BATCH_MODE, CONN_LOCK
from webtriathlon.misc import last, form_view, get_all_models, get_db_version
from webtriathlon.debug import dtime
from webtriathlon.core.models import *
from webtriathlon.dynamic.models import *
from webtriathlon.dynamic.errors import check_all
from webtriathlon.dynamic.ranking import get_ranking_fast, get_stage_ranking_fast
from webtriathlon.dynamic.path import align_laps

from webtriathlon.dynamic import async, ranking
from webtriathlon.api._functions import add_team as do_add_team
from webtriathlon.api.functions import dispatch

#from south.models import MigrationHistory


MAX_DELTA = timedelta(seconds=1)
ALL_MODELS = get_all_models()
DBVERSION = get_db_version()

def modified(request):
    ps = [
        p for p in Passage.objects.filter(deleted=False)
        if abs(p.changed - p.created) > MAX_DELTA
        ]
    return render_to_response("admin_tools/list_passages.html", {"passages": ps,
        "title":"Passages modifiés"})

def deleted(request):
    ps = Passage.objects.filter(deleted=True)
    return render_to_response("admin_tools/list_passages.html", {"passages": ps,
        "title": "Passages supprimés"})

def disqualified(request):
    ts = Team.objects.filter(disqualified=True)
    return render_to_response("admin_tools/disqualified.html", {"teams": ts,
        "title": "Équipes disqualifiées"})

def errors(request):
    errors = Error.objects.all()
    return render_to_response("admin_tools/errors.html",  {"errors": errors,
        "title": "Erreurs"})

def jobs(request):
    """ Refresh some jobs and see the status of the job queue"""
    global_queue_copy = list(async.global_queue)
    queue_len = len(global_queue_copy)
    return render_to_response("admin_tools/jobs.html", {"last_updates": list(async.last_updates),
        "global_queue": global_queue_copy[:15],
        "queue_len": queue_len,
        "title": "État de la file d'attente"})

class TeamForm(forms.Form):
    nb = forms.IntegerField("N° d'équipe")
    category = forms.ModelChoiceField(queryset=Category.objects.all(),
        label="Catégorie")
    sub_cats = forms.ModelMultipleChoiceField(queryset=SubCategory.objects.all(),
        label="Sous-catégorie", required=False)
    path = forms.ModelChoiceField(queryset=Path.objects.all(),
        label="Parcours", required=False)
    member0 = forms.CharField(label="Équipier", required=False)
    member1 = forms.CharField(label="Équipier", required=False)
    member2 = forms.CharField(label="Équipier", required=False)
    member3 = forms.CharField(label="Équipier", required=False)
    member4 = forms.CharField(label="Équipier", required=False)

    def clean_nb(self):
        nb = self.cleaned_data["nb"]
        if Team.objects.filter(nb=self.cleaned_data["nb"]).count():
            raise forms.ValidationError("Numéro déjà attribué")
        return nb

class PassagesForm(forms.Form):
    category = forms.ModelChoiceField(queryset=Category.objects.all(),
        label="Catégorie")
    sub_cat = forms.ModelChoiceField(queryset=SubCategory.objects.all(),
        label="Sous-catégorie", required=False, empty_label="Toutes")
    path = forms.ModelChoiceField(queryset=Path.objects.all(),
        label="Parcours", required=False, empty_label="Toutes")
    team_from = forms.IntegerField(label="Numéro d'équipe supérieur ou égal",
         required=False)
    team_to = forms.IntegerField(label="Numéro d'équipe inférieur ou égal",
         required=False)
    station = forms.ModelChoiceField(queryset=Station.objects.all(),
        label="Poste")
    time = forms.SplitDateTimeField(widget=widgets.AdminSplitDateTime,
        label="Heure")


@form_view(TeamForm, "actions/form.html", "/",
        {"title": "Ajouter une équipe"})
def add_team(request, form):
    nb = form.cleaned_data["nb"]
    cat = form.cleaned_data["category"].name
    sub_cats = form.cleaned_data["sub_cats"]
    sub_cats = [sc.name for sc in sub_cats]
    path = form.cleaned_data["path"].name
    members = []
    for i in range(5):
        members.append(form.cleaned_data["member%i"%(i,)])
    do_add_team(cat, nb, path, members, sub_cats)


@login_required
@form_view(PassagesForm, "actions/form.html", "/admin_tools/",
        {"title": "Ajouter des passages"})
def add_passages(request, form):
    with BATCH_MODE, CONN_LOCK, transaction.commit_on_success():
        station = form.cleaned_data["station"]
        cat = form.cleaned_data["category"]
        sub_cat = form.cleaned_data["sub_cat"]
        path = form.cleaned_data["path"]
        time = form.cleaned_data["time"]
        team_nb_from = form.cleaned_data["team_from"]
        team_nb_to = form.cleaned_data["team_to"]
        qs = Team.objects.filter(category=cat)
        if team_nb_from:
            qs = qs.filter(nb__gte=team_nb_from)
        if team_nb_to:
            qs = qs.filter(nb__lte=team_nb_to)
        if sub_cat:
            qs = qs.filter(subcategories=sub_cat)
        if path:
            qs = qs.filter(path=path)
        for t in qs:
            t.passage_set.create(
                    station=station,
                    time=time)

@login_required
def delete_passages(request):
    if request.method == "POST":
        if request.POST["confirm"] == "true":
            with BATCH_MODE, CONN_LOCK, transaction.commit_on_success():
                Passage.objects.all().delete()
        return HttpResponseRedirect("/admin_tools/")
    else:
        return render_to_response("actions/confirm.html")

@login_required
def refresh_all(request):
    async.refresh_all()
    return HttpResponseRedirect("/admin_tools/jobs/")

@login_required
def refresh_errors(request):
    check_all()
    return HttpResponseRedirect("/admin_tools/errors/")

@login_required
def align_all(request):
    for t in Team.objects.all():
        align_laps(t)
    return HttpResponseRedirect("/admin_tools/jobs/")

@login_required
def create_all(request):
    async.create_all()
    return HttpResponseRedirect("/admin_tools/")

@login_required
def delete_all(request):
    if request.method == "POST":
        if request.POST["confirm"] == "true":
            with BATCH_MODE, CONN_LOCK, transaction.commit_on_success():
                for model in ALL_MODELS:
                    LOG.info("deleting all objects in %s"% model)
                    model.objects.all().delete()
        return HttpResponseRedirect("/admin_tools/")
    else:
        return render_to_response("actions/confirm.html")

class UploadPassagesForm(forms.Form):
    file  = forms.FileField(label="Fichier")
class UploadSaveForm(forms.Form):
    file  = forms.FileField(label="Fichier")
    models = forms.MultipleChoiceField(
            label="Composants",
            choices=[(m.__name__, m.__name__) for m in ALL_MODELS],
            widget=forms.SelectMultiple(attrs={"size":str(len(ALL_MODELS))}),
            )

context = {"action": "/admin_tools/open/", "title": "Charger une sauvegarde", "dbversion": DBVERSION}
@login_required
@form_view(UploadSaveForm, "save/upload.html", "/admin_tools/success/", context)
def open(request, form):
        f = request.FILES["file"]
        models = form.cleaned_data["models"]
        LOG.debug("selected models: %s"%models)
        errors = do_open(f, models)
        async.refresh_all()

        if errors:
            return render_to_response('save/error.html',
                    {"errors": errors})
        else:
            return render_to_response('admin_tools/jobs.html')

def do_open(f, models):
        errors = []
        with BATCH_MODE, CONN_LOCK, transaction.commit_on_success():
            z = ZipFile(f, "r")
            try:
                v = z.open("DBVERSION")
                version = v.read().strip()
            except (KeyError, ValueError), e:
                errors.append("Fichier mal formé (%s)"%e)
            else:
                if version != DBVERSION:
                    errors.append(
                        "Ce fichier est basé sur la version %s de la base de"
                        " donnée. La version actuelle est %s"%(version, DBVERSION)
                        )

            for m in models:
                name = m
                try:
                    LOG.debug( "loading %s"%name)
                    m = z.open(name)
                except KeyError:
                    continue
                try:
                    for obj in serializers.deserialize("json", m.read()):
                        try:
                            if name == "Passage":
                                object = obj.object
                                try:
                                    p = Passage.objects.get(uuid=object.uuid)
                                except Passage.DoesNotExist:
                                    object.id = None #create
                                else:
                                    object.id = p.id #modify
                            obj.save()
                        except Exception, e:
                            import traceback
                            traceback.print_exc()
                            errors.append("%s: %s"%(obj,e))
                except Exception, e:
                    errors.append("%s: %s"%(name,e))
                m.close()
            z.close()
            return errors


context = {"action": "/admin_tools/open_passages/", "title": "Charger une liste de passages"}
@login_required
@form_view(UploadPassagesForm, "save/upload.html", "/admin_tools/success/", context)
def open_passages(request, form):
    f = request.FILES["file"]

    errors = []
    passages = {}
    with BATCH_MODE, transaction.commit_on_success():
        for line in f:
            d = simplejson.loads(line)
            try:
                dispatch(d)
            except Exception, e:
                errors.append("%s (original error: %s)"%(e, d["reason"]))

    if errors:
        return render_to_response('save/error.html', {"errors": errors})


def save(request, models, filename='webtriathlon'):
    response = HttpResponse(mimetype="application/zip")
    response["Content-Disposition"] = "attachment;filename=%s.%s.save"%(time.strftime("%Y%m%d_%H%M"), DBVERSION)

    z = ZipFile(response, "w", compression=ZIP_STORED)
    z.writestr("DBVERSION", DBVERSION)
    for m in models:
        LOG.debug("saving %s" % m)
        all_objects = m.objects.all()
        data = serializers.serialize("json", all_objects)
        z.writestr(m.__name__, data)
    z.close()

    return response



## Printable version of ranking and laps
ranking_template = loader.get_template("printable/ranking.html")

@dtime
def printable_ranking(request):
    with BATCH_MODE:
        categories = []
        for c in Category.objects.all():
            subcats = list(
                    SubCategory.objects.filter(team__in=c.team_set.all()).distinct())
            if len(subcats) > 1:
                subcats = [None] + subcats
            for sc in subcats:
                team_set = c.team_set.all()
                if sc:
                    team_set = team_set.filter(subcategories=sc)
                if not team_set.count():
                    continue
                g_ranking = get_ranking_fast(team_set)

                rank_by_stage = defaultdict(dict)
                for s in c.stages:
                    for r, t in get_stage_ranking_fast(ref_stage=s, team_set=team_set):
                        rank_by_stage[t][s] = r
                teams = []
                for r, t in g_ranking:
                    stages = []
                    for ref_stage in c.stages:
                        rank = rank_by_stage[t][ref_stage]
                        stage = t.get_stage(ref_stage)
                        laps = t.lap_set.filter(stage=stage)
                        first = first_or_none(laps)
                        last = last_or_none(laps)
                        if first and last:
                            begin = first.begin
                            end = last.end
                            delta = end.time - begin.time
                            tot_time = format_time(delta)
                        else:
                            begin=None
                            end=None
                            tot_time = ""
                        stages.append((rank, stage, laps, begin, end, tot_time))
                    laps = t.lap_set.all()
                    teams.append((r, t, laps, stages, len(stages)+1))
                categories.append(((c, sc), teams))
                teams = []

        html = ranking_template.render(Context({"categories": categories}))
        return HttpResponse(html)

@dtime
def printable_teams(request):
    with BATCH_MODE:
        categories = []
        for c in Category.objects.all():
            ts = c.team_set.all()
            categories.append((c, get_ranking_fast(ts)))

        return dtime(render_to_response)("printable/teams.html", {"categories":
            categories, })

@dtime
def printable_stats(request):
    categories = []
    for c in itertools.chain([None], Category.objects.all()):
        stats = []
        for lt in LapType.objects.all():
            s = {}
            laps = Lap.objects.exclude(jonction_before=True).filter(stage__lap_type=lt).order_by("-speed")
            if c:
                laps = laps.filter(team__category=c)
            s["median_lap"] = laps[laps.count()//2] if laps else None
            s["best_lap"] = first_or_none(laps)
            s["worst_lap"] = last_or_none(laps)
            stats.append((lt, s))
        categories.append((c, stats))

    return render_to_response("printable/stats.html", {"stats":categories})


