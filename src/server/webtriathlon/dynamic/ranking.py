#!/usr/bin/env python
# vim: set encoding=utf-8
from __future__ import division

import os, sys

import random
from collections import defaultdict
from operator import attrgetter

from django.db.models import Sum, Avg, StdDev


from webtriathlon import LOG
from webtriathlon.core.models import Category, Path, Stage
from webtriathlon.misc import mean_speed
from webtriathlon.dynamic.path import get_default_path
from webtriathlon.dynamic.models import *
from webtriathlon.cache import cache_func
from webtriathlon.debug import dtime

@dtime
def projected_time(team, stage, reference_stage):
# Team with no laps at all must be in the bottom of the ranking
    speed = get_mean_speeds(team, stage).ranking_speed
    return speed and reference_stage.length / speed

@dtime
def projected_time_total(team, reference_path=None):
    if reference_path is None:
        reference_path = get_default_path(team.category)
    return sum(projected_time(team, s, r_s) for s, r_s in zip(team.path, reference_path))


@dtime
def get_ranking_fast(team_set):
    return ((r+1, t) for r, t in enumerate(team_set.order_by("disqualified", "real_state__proj_time")))

@dtime
def get_stage_ranking_fast(team_set, ref_stage):
    team_stages = TeamStage.objects.filter(team__in=team_set, stage__index=ref_stage.index)
    return ((r+1, m.team) for r, m in enumerate(team_stages.order_by("-ranking_speed")))
