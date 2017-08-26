# coding: utf-8
import time, datetime

from django.http import *
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.db import transaction

from piston.handler import BaseHandler
from piston.utils import rc
from piston.resource import Resource

from webtriathlon import LOG
from webtriathlon.core.models import *
from functions import dispatch, FunctionDoesNotExist


class ModelHandler(BaseHandler):
    allowed_methods = ("GET",)


class StageHandler(ModelHandler):
    model = Stage


class StationHandler(ModelHandler):
    model = Station


class CategoryHandler(ModelHandler):
    model = Category

class PathHandler(ModelHandler):
    model = Path

class PersonHandler(ModelHandler):
    model = Person

class TeamHandler(ModelHandler):
    model = Team
    fields = ["nb", "members", "category", "subcategories", "path"]


class PassageHandler(ModelHandler):
    model = Passage
    fields = ("team_nb", "category_name", "path_name", "stage_name",
            "timestamp", "uuid", "station_name", "lap_nb", "nb_laps",
            "deleted", "duplicate_uuid", "errors", "team_errors")

    @classmethod
    def duplicate_uuid(self, p):
        return p.duplicate and p.duplicate.uuid

    @classmethod
    def team_nb(self, p):
        return p.team.nb

    @classmethod
    def category_name(self, p):
        return p.team.category.name

    @classmethod
    def path_name(self, p):
        return p.team.path.name

    @classmethod
    def stage_name(self, p):
        if p.stage is None:
            return u"Départ"
        return p.stage.lap_type.name

    @classmethod
    def timestamp(self, p):
        return time.mktime(p.time.timetuple())

    @classmethod
    def station_name(self, p):
        return p.station.name

    @classmethod
    def lap_nb(self, p):
        if p.duplicate:
            p = p.duplicate
        try:
            return p.get_lap_before().nb
        except ObjectDoesNotExist:
            if p.stage is None:
                return None
            return (p.team.passages.filter(time__lt=p.time, stage=p.stage).count() + (not bool(p.stage.before)))

    @classmethod
    def nb_laps(self, p):
        stage = p.stage or p.team.path.first_stage
        if stage:
            return stage.nb_laps + bool(stage.after)
        return 0

    @classmethod
    def errors(self, p):
        return [e.message for e in p.error_set.all()]

    @classmethod
    def team_errors(self, p):
        return [e.message for e in p.team.error_set.all()]

class FunctionHandler(BaseHandler):
    allowed_methods = ("POST",)

    #@transaction.autocommit()
    def create(self, request):
        from webtriathlon.dynamic.signals import register_all
        register_all()
        try:
            result = dispatch(request.data)
        except FunctionDoesNotExist, e:
            return rc.BAD_REQUEST
        except (ValueError, TypeError), e:
            import traceback
            traceback.print_exc()
            return rc.BAD_REQUEST
        except ObjectDoesNotExist, e:
            import traceback
            traceback.print_exc()
            return HttpResponseNotFound(str(e))
        except Exception, e:
            import traceback
            traceback.print_exc()
            msg = traceback.format_exc()
            return HttpResponseServerError(msg)
        return {"result": result}

class ExpectedTeamsHandler(BaseHandler):
    allowed_methods=("GET",)

    def read(self, request):
        nb = request.GET.get("nb", 10)
        station = request.GET.get("station", None)
        if station:
            try:
                station = Station.objects.get(name=station)
            except Station.DoesNotExist:
                LOG.warning("The station %s does not exist"%station)
                return []

        return list(Team.expected(station=station)[:nb])

class ServerInfoHandler(BaseHandler):
    allowed_methods=("GET",)
    def read(self, request):
        import time
        d = {
                "timestamp": int(time.time()), #verify sycronity
                "debug": settings.DEBUG,
                }
        return d



