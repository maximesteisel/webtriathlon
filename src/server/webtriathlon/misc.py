#!/usr/bin/env python
# vim: set encoding=utf-8
import datetime
import itertools
import uuid
import threading
import sys, os
from functools import wraps
from subprocess import check_output
from StringIO import StringIO
from tempfile import NamedTemporaryFile


from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.management import call_command
from django.template import RequestContext


from webtriathlon.debug import dtime

@dtime
def last(manager):
    return manager.reverse()[0]

def next_(l, value):
    l = list(l)
    i = l.index(value)
    return l[i+1]

@dtime
def last_or_none(manager):
    try:
        return last(manager)
    except IndexError:
        return None

@dtime
def first_or_none(manager):
    try:
        return manager[0]
    except IndexError:
        return None

#speed converter
def ms_kmh(ms):
    return round(ms*3.6,3)

def kmh_ms(kmh):
    return kmh/3.6

@dtime
def mean_speed(laps):
    """Return the mean speed in m/s"""
    total_time = .0
    total_length = .0
    for l in laps:
        total_time += l.time
        total_length += l.length
    if total_time == 0:
        return 0
    return total_length / total_time

def all_models_in(*args):
    from django.db import models
    l = []
    for app in args:
        print app, dir(app)
        for i in app.models.__dict__.values():
            try:
                if issubclass(i, models.Model):
                    l.append(i)
            except TypeError:
                pass
    return l

@dtime
def shift(it, mark_first=False):
    """
    Similar to the "pairwise" recipes of itertools documentation
    mark_first==False: s -> (s0,s1), (s1,s2), (s2,s3), ...
    mark_first==True: s -> (s0,s1, True), (s1,s2, False), (s2,s3, False), ...
    """
    a, b = itertools.tee(it)
    next(b, None)
    if mark_first:
        c = itertools.chain([True], itertools.repeat(False))
        return itertools.izip(a, b, c)
    return itertools.izip(a, b)

def int_to_time(i):
    """
    Convert a duration in second to a tuple of hours, minutes, seconds
    """
    m, s = divmod(i, 60)
    h, m = divmod(m, 60)
    return int(h), int(m), int(s)

def timedelta_to_int(td):
    """
    Convert a time delta to a duration in seconds
    """
    i = td.days*24*60*60
    i += td.seconds
    return i

def timedelta_to_time(td):
    """
    Convert a timedelta to a tuple of hours, minutes, seconds
    """
    i = timedelta_to_int(td)
    return int_to_time(i)

def format_time(t):
    """
    Format a timedelta or a duration in seconds
    to a string with the format HH:MM:SS
    """
    if isinstance(t, float):
        t = int(t)
    if isinstance(t, int):
        h, m, s = int_to_time(t)
    elif isinstance(t, datetime.timedelta):
        h, m , s = timedelta_to_time(t)
    else:
        raise TypeError("Unsupported type %s"%type(t))
    if h:
        return "%02d:%02d'%02d''" % (h,m,s)
    else:
        return "%02d'%02d''" %(m,s)

def form_view(form, template, success_url, context={}):
    """
    Decorator that can be used to wrap form-backed view.

    Example:
        @form_view(user_form, "template.html", "/success/")
        def aview(request, form):
            #Get called only if form.is_valid()
            #process form data
            return None #equivalent to redirect_to(success_url)
            return Response() #or return a explicit response
    """
    def decorator(wrapped):
        @wraps(wrapped)
        def wrapper(request, *args, **kwargs):
            if request.method == "POST":
                f = form(request.POST, request.FILES)
                if f.is_valid():
                    return (wrapped(request, f, *args, **kwargs)
                            or HttpResponseRedirect(success_url))
            else:
                f = form()
            ctx = {"form":f, "request":request}
            ctx.update(context)
            return render(request, template, ctx)
        return wrapper
    return decorator


def get_all_models():
    from webtriathlon.core import models
    rules_models = [models.Category, models.SubCategory, models.LapType]
    orga_models = rules_models + [models.Station, models.Junction, models.Path, models.Stage]
    addressbook_models = [models.Person]
    teams_models = orga_models + addressbook_models + [models.Team]
    all_models = teams_models + [models.Passage]
    return all_models


def send_message(msg):
    return NotImplemented
    for u in User.objects.all():
        u.message_set.create(message=msg)


def randid():
    return str(uuid.uuid1())


def get_db_version():
    try:
        os.environ["DJANGO_COLORS"] = "nocolor"
        content = StringIO()
        call_command("sql", "core", stdout=content)
        content.seek(0)
        sql = content.read()
        # HACK: it seems that REFERENCES statement can be added
# after the first syncdb is run, so we delete them to always get
# the same db version
        lines = sql.split("\n")
        lines = [l.split('REFERENCES', 1)[0].strip(" ,;")
                for l in lines]
        lines = [l for l in lines if l]
        sql = frozenset(lines)
        tmp = NamedTemporaryFile(delete=False)
        tmp.write(str(sql))
        version = abs(hash(sql))
    except IOError:
        version = 0
    return "{0:0>8}".format(hex(version)[2:])

class _Batch_mode:
    """Use to protect a save-intensive code block"""
    def __init__(self):
        self.batch = False
        self.lock = threading.Lock()

    def __enter__(self):
        with self.lock:
            self.batch = True
        from webtriathlon.dynamic.async import WORKERS
        for w in WORKERS:
            w.pause()

    def __exit__(self, *args, **kwargs):
        with self.lock:
            self.batch = False
        from webtriathlon.dynamic.async import WORKERS
        for w in WORKERS:
            w.resume()

    def is_set(self):
        return self.batch

    __bool__ = __nonzero__ = is_set


