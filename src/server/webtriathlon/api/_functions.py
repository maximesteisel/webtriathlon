from webtriathlon.core import models as _core_models
from webtriathlon.dynamic import path as _path
from webtriathlon import debug as _debug
from webtriathlon import BATCH_MODE
import datetime as _datetime

@_debug.dtime
def add_passage(timestamp, station, team, stage=None, uuid=None, duplicate=None):
    if uuid:
        try:
            p = _core_models.Passage.objects.get(uuid=uuid)
        except _core_models.Passage.DoesNotExist:
            pass
        else:
            return [p]

    time = _datetime.datetime.fromtimestamp(timestamp)
    try:
        p = _core_models.Passage.objects.get(team=team, time=time)
    except _core_models.Passage.DoesNotExist:
        pass
    else:
        return [p]
    p = _path.add_passage(station, team, time, stage, uuid, duplicate)
    return [p]


@_debug.dtime
def add_team(category, nb, path="", members=[], sub_cats=[] ):
    c = _core_models.Category.objects.get(name=category)
    try:
        team = _core_models.Team.objects.get(nb=nb)
    except _core_models.Team.DoesNotExist:
        team = _core_models.Team(nb=nb)
    team.category = c
    if path:
        try:
            path = _core_models.Path.objects.get(
                name__icontains=path, categories=c)
            team.path = path
        except _core_models.Path.DoesNotExist:
            pass
    team.save()
    if members:
        team.members.clear()
        for m in members:
            m.strip()
            if not m:
                continue
            names = m.split(" ", 1)
            if len(names)==1:
                first, last = names[0], ""
            else:
                first, last = names
            m, created = _core_models.Person.objects.get_or_create(
                first_name=first, last_name=last)
            team.members.add(m)
    if sub_cats:
        team.subcategories.clear()
        for s in sub_cats:
            s, created = _core_models.SubCategory.objects.get_or_create(
                    name=s)
            team.subcategories.add(s)
    return [team]

def add_person(first_name, last_name=None, team=None, **kwargs):
    p = _core_models.Person.objects.get_or_create(first_name=first_name, last_name=last_name)[0]
    p.__dict__.update(**kwargs)
    p.save()
    _core_models.Team.objects.get(nb=team).members.add(p)
    return [p]

@_debug.dtime
def modify_passage(uuid, changed, timestamp=None, station=None, team=None, stage=None):
    try:
        passage = _core_models.Passage.objects.get(uuid=uuid)
    except _core_models.Passage.DoesNotExist:
        if timestamp and station:
            passage, = add_passage(timestamp, station, team, stage, uuid)
            uuid = passage.uuid
        else:
            raise
    changed = _datetime.datetime.fromtimestamp(changed)
    if changed < passage.changed:
        return [passage]

    passage.deleted=False
    if timestamp:
        time = _datetime.datetime.fromtimestamp(timestamp)
        passage.time = time
    if station:
        station = _core_models.Station.objects.get(name=station)
        passage.station = station
    if team:
        team = _core_models.Team.objects.get(nb=team)
        passage.team = team
    if stage:
        stage = passage.team.path.stage_set.get(lap_type__name=stage)
        passage.stage = stage
    passage.save()
    return [passage]

@_debug.dtime
def add_passage_to_path(timestamp, station, path):
    with BATCH_MODE:
        time = _datetime.datetime.fromtimestamp(timestamp)
        p = _path.add_passage_to_path(station, path, time)
        return p

@_debug.dtime
def delete_passage(uuid):
    with BATCH_MODE:
        p = _core_models.Passage.objects.get(uuid=uuid)
        p.deleted = True
        p.save()
        return [p]

