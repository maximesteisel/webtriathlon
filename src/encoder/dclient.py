# coding: utf-8
from client import Client
from client import S_DUP, S_DELETED
from client import MIN_DELTA_PASS

from twisted.internet import defer

S_SAVED = u"SAUVÉ"

class DClient(Client):
    """defered client"""
    def __init__(self):
        self.file = None
        self.nb_passages = 0
        self.error_msg = ""
        Client.__init__(self)

# Methods specifics to DClient
    def create_file(self):
        if self.station:
            self.file = open("%s.psave"%(self.station,), "a")
        else:
            self.file = open("station.psave", "a")


    def flush(self):
        if self.file:
            self.file.flush()

    def close(self):
        if self.file:
            self.file.close()
            self.file = None

# Methods subclassed

    def send_function(self, data):
        data["reason"] = self.error_msg
        data = self.encode(data, pprint=False)
        if self.file is None:
            self.create_file()
        print "writing to", self.file.name
        print data
        self.nb_passages += 1
        self.file.write(data + "\n")
        self.flush()
        return defer.succeed(((S_SAVED, self.error_msg), []))


