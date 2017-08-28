# coding: utf-8
from collections import defaultdict
from threading import RLock, Lock
from Queue import PriorityQueue, Empty
from datetime import datetime, timedelta
from contextlib import nested, contextmanager

from django.db import models, IntegrityError, transaction, DatabaseError
from django.db.models import Sum, StdDev
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from twisted.internet import reactor

from webtriathlon import LOG, BATCH_MODE
from webtriathlon.misc import *
from webtriathlon.core.models import *
from webtriathlon.dynamic.path import next_stage, find_current_stage, create_lap, find_stage
        
class RLock2:
    def __init__(self, *args, **kwargs):
        self._underlying = Lock()
        self._internal_lock = Lock()
        self._counter = 0

    def acquire(self, blocking=True):
        locked = self._underlying.acquire(blocking)
        with self._internal_lock:
            self._counter += 1
        return locked

    def release(self):
        with self._internal_lock:
            self._counter -=1
            if self._counter == 0:
                self._underlying.release()

    def __enter__(self):
        #traceback.print_stack()
        self.acquire()

    def __exit__(self, *args):
        self.release()


PRI_UKN_ERROR = 1000
PRI_TMP_ERROR = 10
PRI_LOW = 200
LOCKS = defaultdict(RLock2)
ERROR = "error"
WARNING = "warning"


@contextmanager
def non_blocking(lock):
    try:
        lock.acquire(blocking=False)
        yield lock
    finally:
        lock.release()

class PrioritySet(object):
    def __init__(self):
        self.lock = RLock()
        self.set_ = set()
        self.queue = PriorityQueue()

    def __len__(self):
        with self.lock:
            return min(self.queue.qsize(), len(self.set_))

    def __iter__(self):
        with self.lock:
            return iter(list(self.set_))

    def add(self, priority, obj):
        item = (obj.__class__, obj.pk)
        LOG.debug('%s objects in queue'%len(self))
        with self.lock:
            if item not in self.set_:
                self.queue.put((priority, item))
                self.set_.add(item)
                return True

    def pop(self):
        LOG.debug("Trying to pop from queue")
        while 1:
            try:
                with self.lock:
                    priority, item = self.queue.get_nowait()
                    self.set_.remove(item)
            except Empty:
                LOG.debug("queue is empty")
                raise KeyError("pop from an empty set")

            except KeyError:
                LOG.error("item not in self.set_")
                continue
            except:
                LOG.exception("An error occured while getting an item in queue")
            else:
                klass, pk = item
                try:
                    return klass.objects.get(pk=pk)
                except klass.DoesNotExist:
                    LOG.warn("%s don't exist anymore"%((priority, item),))
                    if priority < 100:
                        with self.lock:
                            self.queue.put((priority+10, item))
                            self.set_.add(item)
                    continue


global_queue = PrioritySet()

def pick_one_in_queue(queue=global_queue):
    """Pick an instance in the refresh queue"""
    obj = queue.pop()
    return obj


class Dynamic(models.Model):
    """Base class of dynamic models"""

    class Meta:
        abstract = True

    # Keep track of the time of last save
    updated = models.DateTimeField(auto_now=True)

    priority = 10 #lowest first
    auto_refresh_interval = 20

    # By default hash is generated from id(self) but
# two object with different id() can be
# generated from the same row in db
    def __hash__(self):
        return hash((self.__class__, self.pk))

    def __eq__(self, other):
        if self.__class__ == other.__class__:
            return self.pk == other.pk
        return NotImplemented

    @classmethod
    def ts_get_create(cls, *args, **kwargs):
        obj, created =  cls.ts_get_or_create(*args, **kwargs)
        if created:
             try:
                 obj.clean()
             except ValidationError:
                 obj.delete()
                 raise
        return obj

    @classmethod
    def ts_get_or_create(cls, *args, **kwargs):
        """Get or create instance in a thread-safe manner"""
        LOG.debug("get or create %s(%s,%s)"%(cls, args, kwargs))
        try:
            return cls.objects.get_or_create(*args, **kwargs)
        except cls.MultipleObjectsReturned:
            LOG.warning("Multiple objects returned by %s %s %s"%(cls, args, kwargs))
            objects = cls.objects.filter(*args, **kwargs)
            objects.delete()
            return cls.objects.get_or_create(*args, **kwargs)

    @classmethod
    def create_all(cls):
        pass

    def affect(self):
        """Return a list of dynamic objects to update after this instance"""
        return []

    @dtime
    def refresh_now(self):
# We can only start refresh when all obj that affect us has been refreshed
        with LOCKS[self]:
            affected = self.affect()
# We acquire all lock of affect models so they wait for us
            with nested(*(non_blocking(LOCKS[a]) for a in affected)):
# We start a transaction after the locking to be sure we have the freshest data
                try:
                    with transaction.commit_on_success():
                        self.compute()
                        self.clean()
                        try:
                            self.save()
                        except IntegrityError:
                            self.delete()
                        for a in affected:
                            a.refresh()
                except DatabaseError:
                    LOG.exception("Caugth an temporary error while refreshing %s:"%self)
                    self.refresh(PRI_TMP_ERROR)



    # Required methods for subclasses:
    #   * create_all (classmethod)
    #   * refresh_now and/or refresh_all

    def refresh(self, priority_malus=0):
        """Mark the object to be refreshed"""
        priority = self.priority
        if self.updated:
            td = datetime.now() - self.updated
            if td.total_seconds < 60:
                LOG.warning("%s was updated less than 1min ago"%self)
                priority += PRI_TMP_ERROR
        priority += priority_malus
        if BATCH_MODE:
            global_queue.add(priority, self)
#We don't add it immediatly to be sure the db has the time to register the change that triggered the refresh
# When we are in batch mode, there is only one thread so the problem should not arise
        else:
            reactor.callLater(1, global_queue.add, priority, self)
        LOG.debug("%s has been tagged as needing an update"%self)
        LOG.debug("%s objects in queue"%len(global_queue))

    @classmethod
    def refresh_all(cls):
        print "refresh_all", cls
        for obj in cls.objects.all():
            obj.refresh()

    @classmethod
    def create_or_refresh(cls, *args, **kwargs):
        LOG.debug(" create_or_refresh %s(%s,%s)"%(cls, args, kwargs))
        try:
            created, obj = cls.objects.get_or_create(*args, **kwargs)
        except cls.MultipleObjectsReturned:
            LOG.warning("Multiple objects returned by %s %s %s"%(cls, args, kwargs))
            cls.objects.filter(*args, **kwargs).delete()
            created, obj = cls.objects.get_or_create(*args, **kwargs)
        if not created:
            obj.refresh()




class AutoRefreshModel(Dynamic):
    auto_refresh = True

    class Meta:
        abstract = False # We need a single table of all auto_refresh_model
                         # so we can pick the least recently updated

    @classmethod
    def pick_one_instance(cls):
        """Take the least recently updated instance"""
        try:
            instance = cls.objects.all().order_by("updated")[0]
        except IndexError:
            return
# XXX: dirty hack
# cls.objects.all() return instance of AutoRefreshModel but we want subclasses
# Django cannot downcast automatically so we have to do it ourself
# For each subclasses, django add a OneToOneField pointing to the downcasted
# instance of this subclasse, we use that to find subclasses and downcast instances
# see http://jeffelmore.org/2010/11/11/automatic-downcasting-of-inherited-models-in-django/
        from django.db.models.fields.related import SingleRelatedObjectDescriptor
        subclasses = [o for o in dir(cls) if
                      isinstance(getattr(cls, o), SingleRelatedObjectDescriptor) # o refer to something
                      and getattr(cls,o).related.model != cls # o refer to another class
                      and issubclass(getattr(cls,o).related.model, cls) # o refer to a subclass
                      ]
        for s in subclasses:
            try:
                instance = getattr(instance, s)
                return instance
            except ObjectDoesNotExist:
                continue
        LOG.warn("AutoRefresh instance (id %s) without subclass, deleting"%instance.pk)
# instance sometimes refuse to be deleted, so we save it before to put it
# back in the queue anyway
        instance.save()
        instance.delete()
        return cls.pick_one_instance()

class DynamicModel(Dynamic):
    auto_refresh = False

    class Meta:
        abstract = True


class Lap(DynamicModel):
    team = models.ForeignKey(Team)
    nb = models.IntegerField("Numero")
    stage = models.ForeignKey(Stage)
    begin = models.OneToOneField(Passage, related_name="begins")
    time = models.IntegerField("Durée", help_text="en secondes", default=0)
    speed = models.FloatField("Vitesse moyenne", help_text="en m/s", default=0)
    length = models.IntegerField("Longueur", help_text="en m", default=0)
    passage = models.OneToOneField(Passage, related_name="ends")
    jonction_before = models.BooleanField(default=False)
    jonction_after = models.BooleanField(default=False)

    has_error = models.NullBooleanField(null=True, default=None)

    #objects = CachingManager()

    @property
    def _checked(self):
        return self.passage._checked

    @_checked.setter
    def _checked(self, value):
        self.passage._checked = value
        self.passage.save()

    @property
    def error_msg(self):
        error = first_or_none(self.error_set.all())
        if error:
            return error.message
        return ""

    @dtime
    def compute(self):
        self.jonction_before = self.get_jonction_before()
        self.jonction_after = self.get_jonction_after()
        self.time = self.get_time()
        self.length = self.get_length()
        self.speed = self.get_speed()
        from webtriathlon.dynamic.errors import check_lap
        self.has_error = bool(check_lap(self))
# Refresh error laps regulary when there is nothing else to do
        if self.has_error:
            reactor.callLater(60, self.refresh, PRI_LOW)

    def affect(self):
        return [
                State.ts_get_create(team=self.team),
                TeamStage.ts_get_create(team=self.team, stage=self.stage),
                ]


    @classmethod
    def refresh_all(cls):
        #Laps.refresh_all() is faster and cover more changes
        pass

    class Meta:
        verbose_name = u"Tour"
        unique_together = ["team", "begin", "passage"]
        ordering = ["stage", "nb"]

    def __unicode__(self):
        return u"Tour de %s n°%s par %s "%(
                self.stage.lap_type,
                self.nb, self.team)

    def get_absolute_url(self):
        return self.team.get_absolute_url() + "#lap-%s" % (self.id)

    def get_jonction_before(self):
        return bool(self.stage.before and self.begin.station == self.stage.before.station)

    def get_jonction_after(self):
        return bool(self.stage.after and self.end.station == self.stage.after.station)

    @property
    def is_jonction(self):
        return bool(self.jonction_before or self.jonction_after)

    @property
    def type(self):
        return self.stage.lap_type

    def get_stage(self):
        return self.stage

    @property
    def end(self):
        return self.passage

    def get_time(self):
        if not self.end: return 0
        delta = self.end.time - self.begin.time
        return delta.days * 24 * 60 * 60 + delta.seconds

    def get_length(self):
        if self.jonction_before:
            if not self.stage.before:
                return self.stage.lap_length
            return self.stage.before.length
        elif self.jonction_after:
            if not self.stage.after:
                return self.stage.lap_length
            return self.stage.after.length
        return self.stage.lap_length

    def get_speed(self):
        if not self.time: return 0
        return self.length / float(self.time)


#Formatted values
    @property
    def ftime(self):
        if not self.end: return "0"
        delta = (self.end.time-self.begin.time)
        return format_time(delta)

    @property
    def fspeed(self):
        return "%s km/h"%(round(ms_kmh(self.speed), 1),)

class Laps(DynamicModel):
    team = models.ForeignKey(Team, related_name="_laps_updater_set")
    align = models.BooleanField(default=False)
    priority = 0

    ##objects = CachingManager()

    class Meta:
        unique_together = ["team", "align"]

    def __unicode__(self):
        return u"Tous les tours de %s (aligner: %s)"%(self.team, self.align)

    def affect(self):
        affected =  [
                State.ts_get_create(team=self.team),
                ]
        for s in self.team.path.stage_set.all():
            affected.append(TeamStage.ts_get_create(team=self.team, stage=s))
        return affected

    @classmethod
    @dtime
    def create_all(cls):
        for t in Team.objects.all():
            cls.ts_get_create(team=t, align=False)

    @classmethod
    def refresh_all(cls):
        for l in cls.objects.filter(align=False):
            l.refresh()

    @dtime
    def compute(self):
        LOG.debug(u"refresh laps " + unicode(self.team))
        self.team.lap_set.all().delete()
        nb_per_stage = defaultdict(int)
        p = None
        old_stage = None
        path = self.team.path
        longuest_stage = path.longuest_stage
        extra_passages = len(self.team.passages) - path.nb_passages
        for last_p, p in shift(self.team.passages):
            if self.align:
                if last_p.duplicate != p:                
                    td = p.time - last_p.time
                    if td.total_seconds() < MIN_DELTA:
                        p.duplicate = (last_p.duplicate or last_p) 
                        continue
                new_stage = old_stage
                if old_stage is None or nb_per_stage[old_stage] >= old_stage.nb_laps:
                    if old_stage==longuest_stage and extra_passages > 0:
                        extra_passages-=1
                    else:
                        new_stage = next_stage(self.team, old_stage)
                if not p._checked:
                    if new_stage.main_station == p.station:
                        p.stage = new_stage
                    else:
                        p.stage = find_stage(p)
                    p.save(raw=True)
                old_stage = p.stage
            create_lap(last_p, p, nb_per_stage)




class TeamStage(AutoRefreshModel):
    priority = 35
    stage = models.ForeignKey(Stage)
    team = models.ForeignKey(Team)
    total_time = models.IntegerField(default=0)
    total_length = models.IntegerField(default=0)
    real_speed = models.FloatField(default=0)
    stage_global_speed = models.FloatField(default=0)
    ranking_speed = models.FloatField(default=0)
    rank = models.IntegerField(default=0)
    MIN_LAPS_FOR_MEAN = 5

    #objects = CachingManager()

    def __unicode__(self):
        if self.team:
            return u"Vitesse moyenne de l'équipe %s dans l'étape %s"%(self.team, self.stage)
        else:
            return u"Vitesse moyenne pour l'étape %s"%(self.stage)

    def affect(self):
        if self.team:
            return [
                    self.team.state
                    ]
        return []

    @classmethod
    @dtime
    def create_all(cls):
        for t in Team.objects.all():
            for s in t.path.stage_set.all():
                cls.ts_get_create(stage=s, team=t)

    def compute(self):
        # If there is not enought lap in a stage
# we get the db mean speed. For a team mean speed
# we always use the real speed.
        team_laps = self.team.lap_set.filter(stage=self.stage)
        stage_laps = self.stage.lap_set.exclude(has_error=True,
                jonction_before=True, jonction_after=True)

        def get_mean(laps):
            agg = laps.aggregate(
                    Sum("time"),
                    Sum("length"),
                    )
            time = agg["time__sum"]
            length = agg["length__sum"]
            if laps in team_laps:
                print("team_laps")
                self.total_time = time
                self.total_length = length
            speed = time and length/float(time) or 0
            return speed
                    
        self.real_speed = get_mean(team_laps)
        self.stage_speed = get_mean(stage_laps)
        self.ranking_speed = self.real_speed if team_laps else self.stage_speed


class Ranking(AutoRefreshModel):
    category = models.OneToOneField(Category)
    auto_refresh_interval = 25
    priority = 50

    #objects = CachingManager()

    def __unicode__(self):
        return u"Le classement de %s"%self.category

    @classmethod
    @dtime
    def create_all(cls):
        for c in Category.objects.all():
            cls.ts_get_create(category=c)

    @dtime
    def compute(self):
        from webtriathlon.dynamic.ranking import get_ranking_fast
        LOG.debug("Refreshing ranking")
        teams = self.category.team_set.filter(disqualified=False)
        for r, t in get_ranking_fast(teams):
            st = t.state
            if st.rank != r:
                st.rank = r
                st.save()

class RankingByStage(AutoRefreshModel):
    category = models.OneToOneField(Category)
    auto_refresh_interval = 25
    priority = 55

    #objects = CachingManager()

    def __unicode__(self):
        return u"Classement par étape de %s"%(self.category)

    @classmethod
    @dtime
    def create_all(cls):
        for c in Category.objects.all():
            cls.ts_get_create(category=c)

    @dtime
    def compute(self):
        from webtriathlon.dynamic.ranking import get_stage_ranking_fast
        teams = self.category.team_set.filter(disqualified=False)
        for s in self.category.stages:
            for r, t in get_stage_ranking_fast(teams, ref_stage=s):
                t_s = TeamStage.ts_get_create(team=t, stage=s)
                if t_s.rank != r:
                    t_s.rank = r
                    t_s.save()

class Error(DynamicModel):
    target_type = models.CharField(max_length=50,
            choices=[("lap","lap"), ("team", "team"), ("passage", "passage")])
    team = models.ForeignKey(Team)
    lap = models.ForeignKey(Lap, null=True)
    passage = models.ForeignKey(Passage, null=True)
    message = models.CharField(max_length=50)
    severity = models.CharField(max_length=50,
            default="error",
            choices=[(ERROR, "error"), (WARNING, "warning")]
            )
    fix_function = models.CharField(max_length=50, null=True)

    class Meta:
        ordering = ["team", "lap", "passage"]

    def affect(self):
        res = [self.team.state]
        if self.lap:
           res.append(self.lap)
        if self.passage:
           res.append(self.passage)
        return res

    def save(self, *args, **kwargs):
        self.clean()
        super(Error, self).save(*args, **kwargs)

    def clean(self):
        if self.target_type=="lap" and self.lap is None:
            raise ValidationError("target cannot be null")

    def refresh_all(self):
        from webtriathlon.dynamic.errors import check_all
        check_all()

    @property
    def target(self):
## FIXME: Ugly hack. Sometimes lap is None, could not find out why.
        if(self.target_type=="passage"): return self.passage or self.lap or self.team
        elif(self.target_type=="lap"): return self.lap or self.team
        else: return self.team

    @property
    def fixable(self):
        return bool(self.fix_function)

    @property
    def fix_f(self):
        from webtriathlon.dynamic import errors
        return getattr(errors, self.fix_function)

    def get_url(self):
        if self.fixable:
            return "details/errors/fix/%s/%s/%s/%s"%(self.team.nb, self.target_type, self.target.pk, self.pk)
        return ""

    def get_ignore_url(self):
        return "details/errors/ignore/%s/%s/%s/%s"%(self.team.nb, self.target_type, self.target.pk, self.pk)

    def get_fix_description(self):
        try:
            return self.fix_f.short_description
        except AttributeError:
            return "Réparer"

    def __unicode__(self):
        return u"%s: %s"%(self.target, self.message)


class State(AutoRefreshModel):
    team = models.OneToOneField(Team, unique=True, related_name="real_state")

    current_stage = models.ForeignKey(Stage, null=True)
    lap_done = models.IntegerField(default=0)
    passages_done = models.IntegerField(default=0)
    lap_left = models.IntegerField(default=0)
    current_lap = models.IntegerField(default=0)
    current_lap_left = models.IntegerField(default=0)
    passages_left = models.IntegerField(default=0)
    have_finished = models.BooleanField(default=False)

    first_passage = models.ForeignKey(Passage, null=True, related_name="team_first")
    last_passage = models.ForeignKey(Passage, null=True, related_name="team_last")

    #first_lap = models.ForeignKey(Lap, null=True, related_name="team_first")
    #last_lap = models.ForeignKey(Lap, null=True, related_name="team_last")

    total_time = models.FloatField(default=0)
    total_ftime = models.CharField(max_length=50)
    ranking_delta = models.FloatField(default=0)
    ranking_fdelta = models.CharField(max_length=50)
    proj_time = models.FloatField(default=0)
    proj_ftime = models.CharField(max_length=50)
    proj_next_passage = models.DateTimeField(default=None, null=True)

    has_error = models.NullBooleanField(null=True, default=None)
    error_msg = models.CharField(max_length=150, null=True)
    rank = models.IntegerField(default=0)

    # refresh protocol
    auto_refresh_interval = 2
    priority = 40

    #objects = CachingManager()
    def __unicode__(self):
        return u"L'état actuel de %s"%self.team

    def affect(self):
        return [
                Ranking.ts_get_create(category=self.team.category),
                RankingByStage.ts_get_create(category=self.team.category),
                ]
    @dtime
    def compute(self):
        from webtriathlon.dynamic.ranking import projected_time_total
        from webtriathlon.dynamic.errors import check_team
        LOG.debug("Refreshing %s"%self)
        t = self.team
        def first_last(qs):
            if len(qs) >= 1:
                return qs[0], qs.reverse()[0]
            return None, None

        ps = t.passages.all()
        self.first_passage, self.last_passage = first_last(ps)
        laps = t.lap_set.all()
        self.first_lap, self.last_lap = first_last(laps)
# XXX This shouldn't happen, but sometimes the last passage doesn't show up in team.passage_set.all()
# probably due to a bug in Django or MySQL, or maybe because a thread bug somewhere
        if self.last_lap and self.last_passage:
            if self.last_lap.passage.time > self.last_passage.time:
                LOG.warning("bug in team.state: last_lap.passage is after last_passage")
                self.last_passage = self.last_lap.passage

        self.proj_time = projected_time_total(self.team)
        if self.first_passage:
            td = self.last_passage.time - self.first_passage.time
            self.total_time = timedelta_to_int(td)
        else:
            self.total_time = 0
        self.total_ftime = format_time(self.total_time)
        self.ranking_delta = self.proj_time - self.total_time
# With rounding error, we can have a team without correction,
# but with a slight difference between total_time and proj_time.
# That is why we consider delta between -15 and +15 to be negligeable
        if self.ranking_delta < -15:
            self.ranking_fdelta = "-" + format_time(abs(self.ranking_delta))
            self.proj_ftime = format_time(self.proj_time)
        elif self.ranking_delta > 15:
            self.ranking_fdelta = "+" + format_time(self.ranking_delta)
            self.proj_ftime = format_time(self.proj_time)
        else:
            self.ranking_fdelta = "="
            self.proj_time = self.total_time
            self.proj_ftime = self.total_ftime
        self.current_stage = find_current_stage(t)
        stage = self.current_stage
        self.have_finished = t._have_finished
        if stage is None:
            self.passages_done = self.lap_done = 0
            self.passages_left = self.lap_left = 0
            self.proj_next_passage = None
        else:
            self.passages_done = ps.filter(stage=stage, deleted=False).count()
            self.passages_left = max(0, stage.nb_passages-self.passages_done)
            if self.current_stage.is_first:
                self.passages_done += 1
            self.lap_done = laps.filter(stage=stage, jonction_before=False).count()
            if not self.lap_done and stage.before:
                self.current_lap = 0
            else:
                self.current_lap = self.lap_done + 1
            self.lap_left = max(0, stage.nb_laps-self.lap_done)
            self.current_lap_left = max(0, stage.nb_laps - self.current_lap)
            if stage.is_last and self.passages_left == 0:
                self.have_finished=True

            try:
                expected_lap_time = self.last_passage.ends.time
                self.proj_next_passage = self.last_passage.time + timedelta(seconds=expected_lap_time) 
            except Lap.DoesNotExist:
                pass

        errors = check_team(self.team, self.have_finished)
        self.has_error = bool(errors)
        if errors:
            e = errors[0]
            if e.lap:
                self.error_msg=u"%s: %s"%(e.lap, e.message)
            else:
                self.error_msg=e.message
        else:
            self.error_msg=u""


    @classmethod
    @dtime
    def create_all(self):
        for t in Team.objects.all():
            State.ts_get_create(team=t)


def get_mean_speeds(team, stage):
    return TeamStage.ts_get_create(team=team, stage=stage)

pre_init = [Lap, TeamStage]
post_init = [Ranking, RankingByStage, State]
dynamic_models = pre_init + post_init + [Laps,]

from signals import register_all
register_all(pre_init, post_init)
