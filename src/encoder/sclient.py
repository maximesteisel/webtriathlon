# coding: utf-8
import time

from urllib2 import urlopen, Request as uRequest
from urlparse import urljoin

from client import Client
from client import display_message

from twisted.internet import defer
from twisted.web.client import getPage
from twisted.web.error import Error as HTTPError
from twisted.internet.error import ConnectError


S_SERVER_ERROR = u"ERREUR DU SERVEUR"
S_SENT = u"ENVOYÉ"
MAX_DELTA_SYNC = 60
S_CONNECT_ERROR = u"DÉCONNECTÉ"

DEFAULT_REQUEST_TIMEOUT = 30

class ConnectionError(IOError):
    pass

class Request(uRequest):
    """Convenient subclass of urllib2.Request"""
    def __init__(self, *args, **kwargs):
        self._http_request_method = kwargs.pop("method", "GET")
        uRequest.__init__(self, *args, **kwargs)
        self.add_header("content-type", "application/json")

    def get_method(self):
        return self._http_request_method

class SClient(Client):
    """Synchronus client"""
    def __init__(self, host="127.0.0.1", port=8000, timeout=DEFAULT_REQUEST_TIMEOUT):
        Client.__init__(self)
        self.set_host(host, port)
        self.set_timeout(timeout)

# Request callback
    def request_success(self, response, url, method, body):
        if body:
            display_message(body)
	#display_message(response)
        return self.decode(response)

# Request errback
    def request_failure(self, failure, url, method, body):
        full_msg = None
        msg = str(failure.value)
        if failure.type is HTTPError:
            full_msg = failure.value.response
            if failure.value.status == "500":
                msg = S_SERVER_ERROR
            elif failure.value.status == "404":
                msg = full_msg.splitlines()[0]
                msg = msg.replace("matching query ", "")
            else:
                msg = full_msg
        elif failure.type is ConnectError:
            msg = S_CONNECT_ERROR
        if msg:
            msg = msg.splitlines()[0]
        print "failed", method, url
        if body:
            display_message(body)
        print "response:"
        if full_msg:
            display_message(full_msg)
        else:
            display_message(msg)
        failure.msg = msg
        return failure


# Methods specific to SClient
    def set_host(self, host="127.0.0.1", port=8000):
        self.host = host
        self.port = port

    def set_timeout(self, timeout):
        self.async_timeout = timeout
        self.sync_timeout = timeout / 5.

    def get_url(self, path):
        return urljoin("http://" + self.host + ":" + str(self.port), path)

    def verify_connection(self):
        """
        Return a defered that errback if connection is broken or if server is desynchronised. In that case, failure.msg contain a user-friendly explaination of the exact problem."""
        def request_success(res):
            serv_time = res["timestamp"]
            delta = serv_time - time.time()
            if abs(delta) > abs(MAX_DELTA_SYNC):
                raise ConnectionError("Erreur de synchronisation des horloges (%s)"%delta)
        d = self.send_request("GET", "/api/")
        d.addCallback(request_success)
        return d


    def get_object_list(self, model, **params):
        return self.send_request("GET", path="/api/%s/"%model)

# Methods shared with dclient
    def get_passage(self, id, cache=True):
        p = super(SClient, self).get_passage(id, cache)
        if p is None:
            d = self.send_request("GET",
                "/api/passage/%s/"%(str(id),))
            return d
        else:
            return defer.succeed(p)

    def send_function(self, data):
        def process_result(result):
            return (S_SENT, None), result["result"]
        d = self.send_request(method="POST", path="/api/execute/", body=data)
        d.addCallback(process_result)
        return d

    def send_sync_request(self, method="GET", path="/api/", body=None):
        if body is not None:
            body = self.encode(body)
        url = self.get_url(path)
        req = Request(url, body, method=method)
        resp = urlopen(req, timeout=self.sync_timeout)
        msg = resp.read()
        return self.decode(msg)

    def send_request(self, method="GET", path="/api/", body=None):
        if body is not None:
            body = self.encode(body)
        url = self.get_url(path)
        headers = {
            'User-Agent': 'Twisted/webtriathlon',
            "Content-Type": "application/json",
            }
        d = getPage(
                url=url,
                method=method,
                postdata=body,
                headers=headers,
                timeout=self.async_timeout,
                )
        d.addCallback(self.request_success, url, method, body)
        d.addErrback(self.request_failure, url, method, body)
        return d

