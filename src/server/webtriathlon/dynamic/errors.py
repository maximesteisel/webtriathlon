# coding: utf-8

from django.conf.urls.defaults import patterns
from django.utils.safestring import SafeString
from django.http import HttpResponseRedirect
from django.db.models import Avg, Sum, StdDev


from webtriathlon import BATCH_MODE, LOG
from webtriathlon.core.models import *
from webtriathlon.dynamic.models import *
from webtriathlon.dynamic.path import align_laps, add_passage
from webtriathlon.misc import kmh_ms, ms_kmh, first_or_none
from webtriathlon.debug import dtime

def create_error(target, message, fix_f, severity="error"):
    assert target
    LOG.debug(u"creating an error: %s %s"%(target, message))
    if isinstance(target, Lap):
        e = Error.ts_get_create(
                target_type="lap",
                team=target.team,
                message=message,
                lap=target,
                passage=target.end,
                severity=severity,
                fix_function=fix_f.__name__,
                )
    elif isinstance(target, Passage):
        e = Error.ts_get_create(
                target_type="passage",
                team=target.team,
                message=message,
                passage=target,
                lap=None,
                severity=severity,
                fix_function=fix_f.__name__,
                )
    elif isinstance(target, Team):
        e = Error.ts_get_create(
                target_type="team",
                team=target,
                message=message,
                lap=None,
                passage=None,
                severity=severity,
                fix_function=fix_f.__name__,
                )
    else:
        e = None
        assert False
    return e


def fix_slow_lap(l):
    delta = l.end.time - l.begin.time
    new_time = l.begin.time + delta / 2
    add_passage(l.end.station, l.team.nb, new_time)
fix_slow_lap.short_description = u"Ajouter un passage au milieu du tour"

def fix_fast_lap(l):
    l.end.all().delete()
fix_fast_lap.short_description = u"Fusionner avec le tour suivant"

def delete_passage(p):
    p.delete()
delete_passage.short_description = u"Supprimer le passage"

def delete_lap(l):
    l.end.delete()
delete_lap.short_description = u"Supprimer le tour"

def fix_bad_station(l):
    l.end.station = l.stage.main_station
    l.end.save()
fix_bad_station.short_description = u"Changer le poste d'encodage"

def fix_bad_station_after(l):
    l.end.station = l.stage.after.station
    l.end.save()
fix_bad_station_after.short_description = u"Changer le poste d'encodage"

def fix_too_much_laps(t):
    align_laps(t)
fix_too_much_laps.short_description=u"Aligner les passages"
fix_too_much_laps.long_description=u"Si un passage a été détecté "
"dans une étape alors qu'en réalité, il est dans la suivante, aligner les passages corrigera le problème"

def fix_not_enougth_laps(t):
    t.disqualified=True
    t.save()
fix_not_enougth_laps.short_description=u"Disqualifier l'équipe"

def fix_add_passage(o):
    pass
fix_add_passage.redirect_to = "/admin/core/passage/add/"
fix_add_passage.short_description = u"Ajouter un passage"

@dtime
def check_passages():
    Error.objects.filter(target_type="passage").delete()
    errors = []
    passages = Passage.objects.filter(duplicate=False, deleted=False, _checked=False)
    for p in passages.filter(begins=None, ends=None):
        msg = u"Passage solitaire"
        errors.append(create_error(p, msg, delete_passage))
    for p in passages.filter(start=False, stage=None):
        msg = u"Étape inconnue"
        errors.append(create_error(p, msg, delete_passage))
    return errors

@dtime
def find_min_max(team, stage):
    lap_type = stage.lap_type
    print(lap_type)
    return (kmh_ms(lap_type.min_speed),
            kmh_ms(lap_type.mean_speed),
            kmh_ms(lap_type.max_speed))

@dtime
def check_lap(l, min_speed=None, avg_speed=None, max_speed=None):
    l.error_set.filter(target_type="lap").delete()
    p = l.end
    if p._checked:
        p.error_set.all().delete()
        return []

    errors = []
    speed = round(ms_kmh(l.speed), 2)

    if min_speed is None or max_speed is None:
        min_speed, avg_speed, max_speed = find_min_max(l.team, l.stage)

    if not l.is_jonction and l.nb > l.stage.nb_laps:
        errors.append(create_error(l, u"Tour en trop (tour %s/%s)"%(l.nb, l.stage.nb_laps), delete_lap, WARNING))

    if not l.is_jonction:
        if max_speed and l.speed > max_speed:
            msg = u"Tour anormalement rapide (%.1f km/h)"%ms_kmh(l.speed)
            errors.append(create_error(l, msg, fix_fast_lap))
        if min_speed and l.speed < min_speed:
            msg = u"Tour anormalement lent (%.1f km/h)"%ms_kmh(l.speed)
            errors.append(create_error(l, msg, fix_slow_lap, WARNING))

    if l.jonction_after:
        if p.station != l.stage.after.station:
            msg = u"Mauvais poste d'encodage (%s)"%p.station
            errors.append(create_error(l, msg, fix_bad_station_after))

    elif p.station != l.stage.main_station:
        msg = u"Mauvais poste d'encodage (%s)"%p.station
        errors.append(create_error(l, msg, fix_bad_station))
    if errors and l.has_error is not True:
        l.has_error = True
        l.save()
    if not errors and l.has_error is not False:
        l.has_error = False
        l.save()
    return errors

@dtime
def check_team(t, finished=True):
    t.error_set.filter(target_type="team").delete()
    if t.disqualified or t._checked:
        t.error_set.all().delete()
        return []

    errors = []
    laps = t.lap_set.all().order_by("passage__time")
    min_max = {}

    if finished:
        starts = first_or_none(t.passages.all())
        if not (starts and starts.stage is None):
            msg = u"Heure de départ manquante"
            errors.append(create_error(t, msg, fix_add_passage, severity=WARNING))

    for s in t.path:
        min_, avg, max_ = find_min_max(t, s)
        min_max[s] = (min_, avg, max_)
        if finished:
            s_laps = laps.filter(stage=s)
            lap_nb = s_laps.count()
            nb_total = s.nb_laps_total
            if lap_nb < nb_total:
                errors.append(create_error(t, u"Pas assez de tours de %s"%s.lap_type,
                    fix_not_enougth_laps))
            if lap_nb > nb_total:
                errors.append(create_error(t, u"Trop de tours de %s"%s.lap_type,
                    fix_too_much_laps, WARNING))

    last_l = None
    for l in laps.exclude(has_error=False):
        errors += check_lap(l, find_min_max(t, l.stage))
        if last_l is None:
            last_l = l
            continue
        if last_l.stage.id > l.stage.id:
            msg = u"%s.%s avant %s.%s"%(
                last_l.stage, last_l.nb,
                l.stage, l.nb)
            errors.append(create_error(t, msg, severity=WARNING))
        last_l = l
    return errors


@dtime
def check_all():
    Error.objects.all().delete()
    errors = []
    errors += check_passages()
    for t in Team.objects.filter(disqualified=False, _checked=False).exclude(real_state__has_error=False):
        errors += check_team(t)
    return errors
