# coding: utf-8
import os, sys
import time
import datetime
import json
import uuid
from collections import defaultdict
from pprint import pprint
from twisted.internet import defer

def randid():
    """generate a uuid for a passage"""
    return str(uuid.uuid1())

if os.environ.get("WT_TEST", None):
    MIN_DELTA_PASS = 2
else:
    MIN_DELTA_PASS = 30

S_DELETED = u"SUPPRIMÉ"
S_MODIFIED = u"MODIFIÉ"
S_ERROR = u"ERREUR"
S_DUP = u"DUPLICATA"
MSG_MAX_SIZE = 500

def display_message(msg, filename="error.html"):
    print msg[:MSG_MAX_SIZE]
    if len(msg) > MSG_MAX_SIZE:
        print "[...]"
        if filename:
            print "printing the full message in", filename
            with open(filename, 'w') as f:
                f.write(msg)
    return msg

class Client(object):
    """Base class to all clients"""
    def __init__(self):
        self.host = ""
        self.station = ""
        self._last_cache = {}
        self._cache = {}

    def _get_last_timestamp(self, team):
        last = self._last_cache.get(team, None)
        if last and not (last["deleted"] or last["duplicate_uuid"]):
            return last["uuid"], last["timestamp"]
        else:
            self._last_cache.pop(team, None)
            return None, 0

    def _cache_set(self, id, p):
        self._cache[id] = p
        team = p["team_nb"]
        if not (p["duplicate_uuid"] or p["deleted"]):
            last_u, last_t = self._get_last_timestamp(team)
            if last_t <= p['timestamp']:
                self._last_cache[team] = p

    def _cache_get(self, id):
        return self._cache.get(id, None)

    def _cache_del(self, id):
        p = self._cache_get(id)
        if p:
            p["deleted"] = True
            self._cache_set(id, p)
        return p

    def decode(self, data):
        return json.loads(data)

    def encode(self, obj, pprint=True):
        if pprint:
            indent = 2
        else:
            indent = None
        return json.dumps(obj, indent=indent)

    def encode_model(self, model, fields):
        return self.encode({"model":model, "pk":fields.pop("pk", 1),
            "fields":fields})

    def create_model(self, id, station, team, timestamp, stage, duplicate_uuid=None):
        m = {
                "team_nb": team, "stage_name": stage or "",
                "path_name": "",
                "timestamp": timestamp, "uuid": id,
                "category_name": "", "station_name": station,
                "lap_nb": None, "nb_laps": None, "duplicate_uuid": duplicate_uuid,
                "deleted": False,
            }
        return m

    def execute(self, function, **kwargs):
        data = {
                "function": function,
                "kwargs": kwargs,
                }
        return self.send_function(data)

    def add_team(self, nb, category, path, members):
        def process_result(result):
            status, data = result
            return status
        d = self.execute(
            "add_team", nb=nb, category=category,
            path=path, members=members
        )
        d.addCallback(process_result)
        return d

    def add_passage(self, station, team, timestamp, stage=None):
        id = randid()
        self.station = station
        last_u, last_t = self._get_last_timestamp(team)
        delta = timestamp - last_t
        duplicate_uuid = None
        if delta < MIN_DELTA_PASS:
            duplicate_uuid = last_u

        def process_result(result, duplicate_uuid=duplicate_uuid):
            status, data = result
            if len(data) == 1:
                p=data[0]
                if not duplicate_uuid:
                    duplicate_uuid = p.get("duplicate_uuid", None)
                self._cache_set(id, p)
            else:
                p = self.create_model(id, station, team, timestamp, stage, duplicate_uuid)
                self._cache_set(id, p)

            return status, p

        d = self.execute(
                "add_passage", station=station, team=team,
                timestamp=timestamp, stage=stage, uuid=id,
                duplicate=duplicate_uuid,
                )
        d.addCallback(process_result)
        return d

    def add_passage_to_path(self, station, path, timestamp):
        def process_result(result):
            status, data = result
            time = datetime.datetime.fromtimestamp(timestamp)
            self.station = station
            for p in data:
                id = p["uuid"]
                self._cache_set(id, p)
            return status, data

        d = self.execute(
                "add_passage_to_path",
                station=station, path=path,
                timestamp=timestamp,
                )
        d.addCallback(process_result)
        return d

    def modify_passage(self, id, station, team, timestamp, stage):
        def process_result(result, id=id):
            status, data = result
            self.station = station
            if len(data)==1:
                p = data[0]
                id = p["uuid"]
                self._cache_set(id, p)
            elif id is None:
                return (S_ERROR, "Passage non existant"), None
            elif self._cache_get(id):
                p = self._cache_get(id)
                p["station_name"] = station
                p["team_nb"] = team
                p["timestamp"] = timestamp
                p["stage_name"] = stage
            else:
                p = self.create_model(id, station, team, timestamp, stage)
                self._cache_set(id, p)
            return status, p
        d = self.execute("modify_passage", uuid=id, station=station, team=team,
                timestamp=timestamp, stage=stage, changed=time.time())
        d.addCallback(process_result)
        return d

    def delete_passage(self, id):
        def process_result(result):
            status, data = result
            stat, msg = status
            if msg:
                msg = "%s (%s)"%(stat, msg)
            else:
                msg = stat
            p = None
            if len(data)==1:
                p = data[0]
                self._cache_set(id, p)
            elif self._cache_get(id):
                p = self._cache_del(id)
            return (S_DELETED, msg), p
        if id is None:
            raise ValueError()
        d = self.execute(
                "delete_passage",
                uuid=id,
                )
        d.addCallback(process_result)
        return d

    def get_passage(self, id, cache=True):
        if cache:
            return defer.succeed(self._cache_get(id))

    def get_stage(self, id):
        d = self.get_passage(id)
        d.addCallback(lambda p: p and p["stage_name"] or "")


