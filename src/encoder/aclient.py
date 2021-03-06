from urllib import urlencode
import time

from client import *
from sclient import SClient
from dclient import DClient
from traceback import print_exc
from twisted.internet.error import ConnectError
from twisted.internet import defer

def autoswitch(wrapped):
    """
    Decorator that tries to call the sclient method and
    fall-back automatically to dclient if it fail for any
    reason (connection lost, server error, etc.)
    """
    def _wrapper(self, *args, **kwargs):
        def use_dclient(msg):
            self.dclient.error_msg = msg
            func = getattr(self.dclient, wrapped.__name__)
            return func(*args, **kwargs)

        def use_sclient():
            def request_failure(failure):
                if failure.type is ConnectError:
                    self.connected = False
                if hasattr(failure, "msg"):
                    return use_dclient(failure.msg)
                else:
                    return use_dclient(str(failure.value))

            func = getattr(self.sclient, wrapped.__name__)
            d = func(*args, **kwargs)
            d.addErrback(request_failure)
            return d

        if self.connected:
            return use_sclient()
        else:
            return use_dclient("Not connected")

    return _wrapper


class AClient(Client):
    """A client to the webtriathlon api that switch between sclient and dclient
    automatically.
    """
    def __init__(self, host="localhost", port=80):
        Client.__init__(self)
        self.host = host
        self.port = port
        self.connected = False
        self.sclient = SClient(host, port)
        self.dclient = DClient()
# Share cache
        self.sclient._cache = self.dclient._cache = self._cache
        self.sclient._last_cache = self.dclient._last_cache = self._last_cache

    def set_host(self, host, port):
        self.sclient.set_host(host, port)
        self.host=host
        self.port=port

    def connect(self):
        d = self.verify_connection()
        return d

    def verify_connection(self):
        def connection_success(res):
            self.connected = True
        def connection_failure(failure):
            self.connected = False
            print "Could not connect"
            return failure
        self.sclient.set_host(self.host, self.port)
        d = self.sclient.verify_connection()
        d.addCallback(connection_success)
        d.addErrback(connection_failure)

    @autoswitch
    def send_function(self):
        pass

    @autoswitch
    def add_passage(self):
        pass

    @autoswitch
    def get_passage(self):
        pass

    def get_object_list(self, obj):
        def process_result(result):
            return [ r["name"] for r in result]
        if not self.connected:
            return defer.succeed([])
        d = self.sclient.get_object_list(obj)
        d.addCallback(process_result)
        d.addErrback(lambda *args: [])
        return d

    def get_stations(self):
        return self.get_object_list("station")

    def get_paths(self):
        return self.get_object_list("path")

    def get_expected_teams(self):
        def process_result(result):
            return [ t["nb"] for t in result ][:10]
        if not self.connected:
            return defer.succeed([])

        path = '/api/expected-teams/'
        if self.station:
            path += '?' + urlencode({"station":self.station})
        d = self.sclient.send_request(path=path)
        d.addCallback(process_result)
        d.addErrback(lambda *args: [])
        return d

    def nb_saved(self):
        return self.dclient.nb_passages

    def get_filename(self):
        if self.dclient.file:
            return self.dclient.file.name
        return "Unknown"

    def send_saved(self):
        def all_sent(result):
            ret = []
            for success, value in result:
                if success:
                    ret.append(value)
                else:
                    print value.getErrorMessage()
            return ret
        if not self.dclient.nb_passages:
            return defer.succeed([])
        self.verify_connection()
        if not self.connected:
            return defer.succeed([])
# Read all commands saved
        fname = self.dclient.file.name
        def_list = []
        savefile = open(fname, "r")
# Erase savefile
        self.dclient.file.close()
        self.dclient.file=None
        os.unlink(fname)
# Reset dclient
        self.dclient.create_file()
        self.dclient._cache.clear()
        self.dclient._last_cache.clear()
# Send all commands
# If the connection is broken, commands will be re-saved
        for l in savefile:
            def_list.append(self.send_function(self.decode(l)))
        d = defer.DeferredList(def_list)
        d.addCallback(all_sent)
        return d
