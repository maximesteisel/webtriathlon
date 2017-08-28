# coding: utf-8

from datetime import datetime

from django.db import models
from django.contrib.auth.models import User

from webtriathlon import LOG, BATCH_MODE, DEBUG
from webtriathlon.dynamic.path import get_default_path, refresh_laps, align_laps, create_lap
from webtriathlon.misc import first_or_none, last_or_none

# Protection against double encoding.
# There should be a protection in the client
# But better be safe than sorry
if DEBUG:
    MIN_DELTA = 5
else:
    MIN_DELTA = 90


GENDER_CHOICES = [
    ("M", "Male"),
    ("F", "Female"),
]

class Person(models.Model):
    uuid = models.CharField(max_length=36, unique=True, editable=False)
    first_name = models.CharField("Prénom", max_length=30)
    last_name = models.CharField("Nom", max_length=30, blank=True)
    genre = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    age = models.IntegerField(blank=True, null=True)
    address = models.CharField("Adresse", max_length=150, blank=True)
    phone = models.CharField("Téléphone", max_length=100, blank=True)
    email = models.EmailField(blank=True)
    user = models.OneToOneField(User, blank=True, null=True)

    class Meta:
        verbose_name = u"Personne"
        ordering = ["first_name", "last_name"]
        unique_together = ["first_name", "last_name"]

    def __unicode__(self):
        # \u00A0: non breaking space
        return (u"%s\u00A0%s"%(self.first_name, self.last_name)).strip()

class Category(models.Model):
    name = models.CharField("Nom", max_length=40, unique=True)

    class Meta:
        verbose_name = u"Categorie"

    def get_absolute_url(self):
        return "/category/%s/"%(self.id,)

    def __unicode__(self):
        return self.name
    @property
    def stages(self):
        return get_default_path(self).stage_set.all()

# A subcategory is a way to (optionaly) filter the ranking
class SubCategory(models.Model):
    name = models.CharField("Nom", max_length=40, unique=True)
    class Meta:
        verbose_name = u"Sous categorie"

    def __unicode__(self):
        return self.name

# Golden rule: the speed of two lap with the same lap_type is comparable
class LapType(models.Model):
    name = models.CharField("Nom", max_length=40, unique=True)
    min_speed = models.FloatField("Vitesse minimale", default=0)
    mean_speed = models.FloatField("Vitesse moyenne", default=0)
    max_speed = models.FloatField("Vitesse maximale", null=True, blank=True)

    class Meta:
        verbose_name = u"Type de tours"
        verbose_name_plural = u"Types de tours"

    def __unicode__(self):
        return self.name


# A station is a place where passages are encoded
class Station(models.Model):
    name = models.CharField("Nom", max_length=40, unique=True)

    class Meta:
        verbose_name = u"Poste"

    def __unicode__(self):
        return self.name


class Junction(models.Model):
    station = models.ForeignKey(Station, verbose_name="Poste",
            help_text=u"Si la jonction est avant une étape, correspond au "
            u"poste qui encode le début de l'étape. Sinon, correspond à la "
            u"fin de l'étape")
    length = models.IntegerField(u"Longeur", help_text="en metres")

    def __unicode__(self):
        return u"%s (%s)"%(self.station, self.length)

    class Meta:
        verbose_name = u"Jonction"


class Stage(models.Model):
    path = models.ForeignKey("Path")
    lap_type = models.ForeignKey(LapType, verbose_name="Type de tour")
    lap_length = models.IntegerField("Longueur du tour")
    nb_laps = models.IntegerField("Nombre de tours")
    before = models.ForeignKey(Junction, blank=True, null=True,
            related_name="starts", verbose_name=u"Jonction avant")
    main_station = models.ForeignKey(Station, verbose_name="Poste")
    after = models.ForeignKey(Junction, blank=True, null=True,
            related_name="ends", verbose_name=u"Jonction apres" )
    index = models.IntegerField(editable=False, null=True)

    class Meta:
        verbose_name = u"Étape"
        ordering = ["path", "id"]

    def __unicode__(self):
        return u"%s.%s"%(self.path.name, self.lap_type.name)

    @property
    def before_length(self):
        return self.before.length if self.before else 0

    @property
    def after_length(self):
        return self.after.length if self.after else 0

    @property
    def nb_laps_total(self):
        """Nb of laps including junctions so corresponding to
        Lap.objects.filter(stage=stage).count() in a normal situation"""
        return self.nb_laps + bool(self.before) + bool(self.after)

    @property
    def nb_passages(self):
        """Return the number of passages expected in the main station of this
        stage so corresponding to
        Passage.objects.fiter(station=main_station).count() in a normal
        situation"""
        return self.nb_laps + bool(self.before)

    @property
    def length(self):
        return self.nb_laps * self.lap_length + self.before_length + self.after_length

    @property
    def previous(self):
        try:
            return self.path.stage_set.get(index=self.index-1)
        except self.DoesNotExist:
            return None

    @property
    def next(self):
        print "Depreciated"
        try:
            return self.path.stage_set.get(index=self.index+1)
        except self.DoesNotExist:
            return self

    @property
    def is_first(self):
        return self.index == 0

    @property
    def is_last(self):
        return self.index == len(self.path.stage_set.all())-1

    @property
    def all_stations(self):
        l = []
        if  self.before:
            l.append(self.before.station)
        if self.pk:
            l.append(self.main_station)
        if self.after:
            l.append(self.after.station)
        return l

class Path(models.Model):
    name = models.CharField("Nom", max_length=40)
    categories = models.ManyToManyField(Category,
        verbose_name="categories possibles")

    class Meta:
        verbose_name = "Parcours"
        verbose_name_plural = "Parcours"
        unique_together = ["name"]
        ordering = ["name"]

    def __unicode__(self):
        return self.name

    def __iter__(self):
        return iter(self.stage_set.all())

    @property
    def all_stations(self):
        stations = set()
        sorted_stations = []
        for v in self.stage_set.all():
            for s in v.all_stations():
                if s in stations:
                    continue
                stations.add(s)
                sorted_stations.append(s)
        return sorted_stations

    @property
    def depart(self):
        return self.stage_set.all()[0].all_stations()[0]

    @property
    def length(self):
        l = 0
        for s in self:
            l += s.length

    @property
    def first_stage(self):
        try:
            return self.stage_set.get(index=0)
        except Stage.DoesNotExist:
            return None
            
    @property
    def longuest_stage(self):
        stages = self.stage_set.all()
        def key(s):
            return s.nb_laps
        return max(stages, key=key)
        
    @property
    def nb_passages(self):
        return sum(s.nb_passages for s in self.stage_set.all()) + 1 #+1 for the depart


# XXX: the recommended usage for ForeignKey in another app is to use a string
# (like adressbook.Person, for example)
# but it doesn't work if twisted is serving (don't know why)

class Team(models.Model):
    nb = models.IntegerField("Numéro", primary_key=True, db_index=True)
    members = models.ManyToManyField(Person, blank=True,
            verbose_name="membres")
    category = models.ForeignKey(Category, verbose_name="categorie")
    subcategories = models.ManyToManyField(SubCategory,
            verbose_name="sous categories")
    path = models.ForeignKey(Path, blank=True, verbose_name="Parcours")
    disqualified = models.BooleanField("Disqualifié", default=False)

# This set manually. The place to check if the team has
# finished is in team.state.have_finished
    _have_finished = models.BooleanField("A terminé (forcer)", default=False)
    _checked = models.BooleanField("Vérifié, pas d'erreur d'encodage", default=False)
    _cached_state = None

    class Meta:
        ordering = ["nb"]
        verbose_name = u"Équipe"

    def get_absolute_url(self):
        return "/team/%i/"%(self.nb,)

    def get_stage(self, ref_stage):
        return self.path.stage_set.get(index=ref_stage.index)

    @classmethod
    def last_seen(cls):
        return cls.objects.all().order_by("-real_state__last_passage")

    @classmethod
    def expected(cls, station=None):
        teams = cls.objects.exclude(disqualified=True)
        teams = teams.exclude(real_state__have_finished=True)
        teams = teams.exclude(real_state__proj_next_passage=None)
        if station:
            teams = teams.filter(
                    real_state__current_stage__main_station=station)
        return teams.order_by("real_state__proj_next_passage")


    @property
    def have_finished(self):
        return self._have_finished or self.state.have_finished

    @property
    def state(self):
        if self._cached_state:
            return self._cached_state
        from webtriathlon.dynamic.models import State
        s = State.ts_get_or_create(team=self)[0]
        self._cached_state = s
        return s

    @property
    def passages(self):
        return self.passage_set.filter(duplicate=None, deleted=False)

    def __unicode__(self):
        return u"Équipe %s"%self.nb

class Passage(models.Model):
# The uuid is used to avoid clashes when opening a saved file but we
    # can't use it as a primary key directly because it confuse the admin app,
    # so we need to implement a custom mechanism
    uuid = models.CharField("ID", max_length=36, editable=False, unique=True, db_index=True)
    time = models.DateTimeField("Heure de passage", default=datetime.now, db_index=True)
    team = models.ForeignKey(Team, verbose_name="Équipe")
    stage = models.ForeignKey(Stage, null=True, blank=True,
        verbose_name="Étape")
    start = models.BooleanField("First passage", editable=False, default=False)
    station = models.ForeignKey(Station, verbose_name="Poste")
    deleted = models.BooleanField("Supprimé", default=False)
    duplicate = models.ForeignKey("self", verbose_name="Duplicata de", null=True,
                                  blank=True, related_name="duplicate_set")
# Time updated when Passage is modified
# Can be used to check the validity of a lap
    changed = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)
    _checked = models.BooleanField("Vérifié", default=False)

    def get_lap_before(self):
        if self.duplicate:
            return self.duplicate.ends
        return self.ends

    def get_lap_after(self):
        if self.duplicate:
            return self.duplicate.begins

    @property
    def nb(self):
        if self.duplicate:
            self = self.duplicate
        try:
            return self.get_lap_before().nb + bool(self.stage.before)
        except Exception:
            if self.stage is None:
                return None
            return self.team.passages.filter(time__lt=self.time, stage=self.stage).count() + 1

    def save(self, raw=False, *args, **kwargs):
        created = not self.pk

        super(Passage, self).save(*args, **kwargs)

        if raw:
            return

        #A deleted passage cannot have duplicate pointing to it
        #One of the (non-deleted duplicate must be promoted
        if self.deleted:
            qs = self.duplicate_set.filter(deleted=False)
            if qs:
                first = qs[0]
                rest = qs[1:]
                first.duplicate = None
                first.save(raw=True)
                for p in rest:
                    p.duplicate = first
                    p.save(raw=True)
                refresh_laps(self.team)


        from webtriathlon.dynamic.models import Lap


        other_ps = self.team.passages.exclude(uuid=self.uuid)
        last_p = last_or_none(other_ps)
        previous_p = last_or_none(other_ps.filter(time__lte=self.time))
        next_p = first_or_none(other_ps.filter(time__gte=self.time))

# First we chek if the passage is not too close of another, indicating a double encoding
        if previous_p is not None:
            delta = self.time - previous_p.time
            if delta.total_seconds() < MIN_DELTA:
                self.duplicate = last_p
                self.save(raw=True)
                return

        if next_p is not None:
            delta = next_p.time - self.time
            if delta.total_seconds() < MIN_DELTA:
                self.duplicate = next_p
                self.save(raw=True)
                return

        if self.duplicate and self.duplicate.deleted:
            self.duplicate = None

        if BATCH_MODE:
            LOG.info("batch mode is set, don't add a lap now")
            refresh_laps(self.team)
            return

# Optimize the common case (a passage is created after all others)
        if (created and last_p is not None and
                next_p is None):

            LOG.info("create lap for team %s (fast)"%(self.team,))
            l = create_lap(last_p, self)
            return

        if not created:
# If the passage changed, we must delete the lap corresponding
            l = Lap.objects.filter(passage=self)
            if l:
                l = l.get()
                LOG.info("passage changed, lap already exist")
                if l.team != self.team:
                    LOG.warning("WARNING: owner of %s changed"%(l,))
# If the owner of lap change, the number of lap per stage change, so
# we need to align laps of both teams
                    align_laps(l.team)
                    align_laps(self.team)
                    return
# If last_p is None, self is the only passage, so there is not lap to create, otherwise, we refresh the laps to include the new passage
            if last_p:
                refresh_laps(self.team)
            return

        elif last_p and self.time < last_p.time:
# If self was created before the last one, we need to align all laps
            align_laps(self.team)
            return

    def delete(self):
        self.deleted = True
        self.save(raw=True)
        align_laps(self.team)

    class Meta:
        ordering = ["time"]
        verbose_name = u"Passage"

    def __unicode__(self):
        # show only the time part of the DateTime
        return u"%s devant le poste %s à %s (%s)"%(self.team.nb,
                self.station, self.time.time(), self.stage) + (u" [D] " if self.deleted else u"")

    def get_absolute_url(self):
        return self.team.get_absolute_url() + "#passage-%s" % (self.id)

