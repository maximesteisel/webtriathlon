import os, sys
import logging
import signal
import random
import time
from collections import deque
from threading import RLock, Event

from django.db import transaction


from twisted.internet import reactor, task
from twisted.internet.threads import deferToThread

from webtriathlon import LOG, BATCH_MODE
from webtriathlon.debug import dtime

from webtriathlon.dynamic.models import AutoRefreshModel, pick_one_in_queue
from webtriathlon.dynamic.models import global_queue, dynamic_models, PRI_UKN_ERROR
from webtriathlon.dynamic.errors import check_all

# When we need to update a line in the database, it is added in
# the global queue. refresh_one take it from there and refresh it
# Ihis allow for some asynchronity and avoid slowing down
# the server when there is a higth activity

# Jobs are executed asynchronously, using a reactor.callLater
# if reactor is running, and executing some jobs at each request

# The least recently refreshed obj in some models is
# refreshed once in a while, as a fallback if an object that should
# be marked for refresh is ommited somehow

MIN_DELAY = 0.1
MAX_DELAY = 5
GLOBAL_DELAY = 10
REFRESH_LOCK = RLock()
NB_WORKERS = 1
WORKERS = []

last_updates = deque(maxlen=15)

def compute_delay():
    """Compute delay by taking in account len(global_queue)
    to avoid accumulations of jobs"""
    if BATCH_MODE:
        return MAX_DELAY
    elif global_queue:
        return MIN_DELAY
    else:
        return GLOBAL_DELAY

def refresh_one_in_queue():
    obj = None
    if not global_queue:
        return
    try:
        obj = pick_one_in_queue()
        refresh_one(obj)
    except KeyError:
        pass
    except Exception:
        LOG.exception("Caught an error while poping queue")

def refresh_one_random():
    obj = None
    if not global_queue:
        obj = AutoRefreshModel.pick_one_instance()
        return refresh_one(obj)

def refresh_one(obj):
    if obj is None:
        LOG.debug("None object to refresh")
    else:
        try:
            LOG.debug("refreshing %s (last_updated: %s)"%(obj, obj.updated))
            obj.refresh_now()
            LOG.debug("%s refreshed"%(obj,))
            last_updates.appendleft(obj)
        except Exception, e:
#If there is a problem, we put the obj back on the queue
#We assign it a low priority because it may raise again the next time
#and we don't want it to prevent the refresh of other obj
            LOG.exception("Caugth an exception while refreshing %s:"%obj)
            obj.refresh(PRI_UKN_ERROR)
            return True

class Worker(object):
    def __init__(self, normal_delay, function):
        self.function = function
        self.normal_delay = normal_delay
        self.stopping = False
        self.lock = RLock()
        self.stopped_event = Event()
        reactor.callLater(0.2*random.random(), self.start)

    def _schedule(self):
        if not self.stopping:
            reactor.callLater(self.normal_delay, self.run)

    def start(self):
        LOG.debug("Worker started")
        with self.lock:
            self.stopping = False
            self.stopped_event.clear()
            self._schedule()

    def stop(self):
        with self.lock:
            LOG.debug("Worker stopping")
            self.stopping = True

    pause = stop
    resume = start

    def wait(self):
        self.stop()
        self.stopped_event.wait()

    def done_cb(self, result):
        with self.lock:
            if global_queue:
                LOG.debug("done, %s objects in queue"%len(global_queue))
            if not self.stopping:
                self._schedule()
                return
            self.stopped_event.set()
            LOG.debug("Worker stopped")


    def run(self):
        with self.lock:
            if self.stopping:
                LOG.debug("Worker stopping")
            elif BATCH_MODE:
                LOG.debug("Batch mode is set, waiting %s sec"%MAX_DELAY)
                reactor.callLater(MAX_DELAY, self.run)
                return
            elif reactor.running:
                d = task.deferLater(reactor, 0.01, self.function)
                d.addBoth(self.done_cb)
                return
            self.stopped_event.set()
            LOG.debug("Worker stopped")


def start_workers():
    LOG.debug("starting workers")
    global WORKERS
    for i in range(NB_WORKERS):
        WORKERS.append(Worker(MIN_DELAY, refresh_one_in_queue))
    WORKERS.append(Worker(GLOBAL_DELAY, refresh_one_random))
    return WORKERS

def stop_workers():
    global WORKERS
    for w in WORKERS:
        w.stop()

@dtime
def create_all_now():
    LOG.info("creating all models")
    with transaction.commit_on_success():
        for m in dynamic_models:
            m.create_all()

@dtime
def refresh_all_now():
    with BATCH_MODE:
        create_all_now()
        for m in dynamic_models:
            if reactor.running:
                m.refresh_all()
    assert not BATCH_MODE

def refresh_all():
    reactor.callLater(MIN_DELAY, refresh_all_now)

def create_all():
    reactor.callLater(MIN_DELAY, create_all_now)

