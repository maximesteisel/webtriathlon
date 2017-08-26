import time
from collections import namedtuple, defaultdict

from twisted.internet import reactor

from django.utils.datastructures import SortedDict
from django.db import IntegrityError

from webtriathlon import LOG, BATCH_MODE
from webtriathlon.misc import last, shift, next_, first_or_none
from webtriathlon.debug import dtime

START = None

@dtime
def align_laps(team):
    """ Recompute the stage of each laps. Equivalent to resending
    all passages to the computer, except if some passages are flagged as checked"""
    from webtriathlon.dynamic.models import Lap, Laps
    Laps.ts_get_create(team=team, align=True).refresh()

@dtime
def refresh_laps(team):
    """Clear and then recompute the list of laps from the list of passages"""
    from webtriathlon.dynamic.models import Lap, Laps
    Laps.ts_get_create(team=team, align=False).refresh()

def get_default_path(category):
    """Find the default path (wich is also the reference path) for a category"""
    try:
        return category.path_set.all()[0]
    except IndexError:
        raise ValueError("%s doesn't have a default path"%category)

@dtime
def find_current_stage(team):
    """Find the stage in which a team is by looking at his passages and path"""
    previous_passages = team.passages
    try:
        last_p = last(previous_passages)
    except IndexError:
        return None
    stage = last_p.stage
    if stage is None:
        try:
            return list(team.path)[0]
        except IndexError:
            return None

    done = previous_passages.filter(stage=stage).count()
    if done >= stage.nb_passages:
        try:
            return next_stage(team, stage)
        except IndexError:
            return stage
    else:
        return stage

def next_stage(team, stage):
    if stage is None:
        return first_or_none(team.path.stage_set.all())
    else:
        try:
            return team.path.stage_set.get(index=stage.index+1)
        except stage.DoesNotExist:
            return stage
@dtime
def find_stage(passage):
    """Return the probable stage of the passage based on the stations and the previous passages"""
    station = passage.station
    team = passage.team
    previous_passages = team.passages.filter(
        station = station, team=team,
        time__lt=passage.time)
    try:
        previous = last(previous_passages)
    except IndexError: #no passages before
        return first_encoded(passage.station, team)

    stage = previous.stage
    done = previous_passages.filter(stage=stage).count()

    if stage is None:
        stage = next_encoded(station, team, START)
    else:
        if done >= stage.nb_passages:
            stage = next_encoded(station, team, stage)
    return stage

def match(junction, station):
    "Junction exist and is encoded in station"""
    return junction and junction.station == station

def add_passage(station, nb, time, stage=None, uuid=None, duplicate=None):
    """Helper function to add a passage from pure-python arguments"""
    from webtriathlon.core.models import Station, Team, Stage, Passage
    st = Station.objects.get(name=station)
    try:
        t = Team.objects.get(nb=nb)
    except Team.DoesNotExist:
        raise Team.DoesNotExist("Team %s does not exist"%nb)
    stage = None
    if stage:
        try:
            stage = t.path.stage_set.get(lap_type__name=stage)
        except Stage.DoesNotExist:
            pass
    if duplicate:
        duplicate = Passage.objects.get(uuid=duplicate)

    p = t.passage_set.create(
            station=st,
            time=time,
            stage=stage,
            uuid=uuid,
            duplicate=duplicate,
            )
    LOG.debug(u"new passage: %s"%unicode(p))
    return p

def add_passage_to_path(station, pname, time):
    from webtriathlon.core.models import Path, Station
    st = Station.objects.get(name=station)
    path = Path.objects.get(name=pname)
    ps = []
    for t in path.team_set.all():
        p =  t.passage_set.create(
                station=st,
                time=time)
        ps.append(p)
    return ps


def create_lap(last_p, p, nb_per_stage=None):
    """ create a lap with last_p and p.
    nb_per_stage must be a mapping stage -> last_lap.nb
    It will be updated after the lap is created.
    If not given, last_lap.nb will
    be fetched in the db wich is a bit slower """
    from webtriathlon.dynamic.models import Lap
    i=0
# Skip passages without stage, they are probably erroneus
    if p.stage is None:
        return

    team = p.team
    assert team == last_p.team
    s = p.stage
    l_s = last_p.stage

# if nb_per_stage is not given we use the last lap
    if nb_per_stage is None:
        nb_per_stage = {}
        laps = team.lap_set.filter(stage=s).order_by("-nb")
        try:
            last_lap = laps[0]
        except IndexError:
            nb_per_stage[s] = 0
        else:
            nb_per_stage[s] = last_lap.nb

    if last_p.station != p.station and not match(s.before, last_p.station):
# A stage was skipped so there is a gap and we can't create a lap (yet)
        return

# This lap is a jonction before a stage, so we don't increment nb_per_stage
    if match(s.before, last_p.station) and l_s != s:
        nb = nb_per_stage[s]
# This is a normal lap, increase nb for this stage
    else:
        nb = nb_per_stage[s] + 1

# If there is already a lap with these passages
# delete them so we don't get integrity errors
    Lap.objects.filter(begin=last_p).delete()
    Lap.objects.filter(passage=p).delete()

# create the lap
    try:
        l = Lap(team=team, begin=last_p, passage=p,
                nb=nb, stage=s)
        l.save()
        return l
    except IntegrityError, e:
        LOG.exception("Got an integrity error (%s) while trying to create a lap"
                " between %s and %s (stage=%s, nb=%s)"%(e, last_p, p, s, nb))
        return
    finally:
        # update nb_per_stage
        nb_per_stage[s] = nb


def encoded_stages(station, team):
    def g():
        last=START
        for s in team.path:
            if last is START: # first stage
                if s.before:
                    if s.before.station == station:
                        yield START
                elif s.main_station == station:
                    yield START
                    yield s
            elif match(s.after, station):
                yield s
            elif match(s.before, station):
                yield last
            elif s.main_station == station:
                yield s
            last=s

    return list(g())

def first_encoded(station, team):
    try:
        return encoded_stages(station, team)[0]
    except IndexError: #no stage to encode
        LOG.error(u"No stage encoded in %s for team %s"%(station, team))
        return None

def next_encoded(station, team, previous):
    stage_set = encoded_stages(station, team)
    LOG.debug(u"finding stage after %s"%previous)
    try:
        n = next_(stage_set, previous)
        LOG.debug( u"next is %s"%(n,) )
        return n
    except ValueError:
        LOG.error( "Error: %s was not encoded at %s (only %s are)"%(previous,
                station, stage_set ))
        return first_encoded(station, team)
    except IndexError:
        LOG.warning( u"No next stage, returning the last (%s)"%(previous,)
                )
        return previous

