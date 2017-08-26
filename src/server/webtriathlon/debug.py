import time
import logging
from functools import wraps

from django.conf import settings

LOG = logging.getLogger("webtriathlon")

def dtime(func):
    @wraps(func)
    def _func(*args, **kwargs):
        begin = time.time()
        ret = func(*args, **kwargs)
        end = time.time()
        delta = end-begin
        msg=""
        if delta > 1:
            if delta > 10:
                msg += " VERY"
            msg+=" SLOW!"
        if delta > 0.010:
            LOG.debug("%s.%s: %s%s %s %s"%(func.__module__, func.__name__, delta, msg, str(args)[:200], str(kwargs)[:200]))
        return ret
    if settings.DEBUG:
        return _func
    else:
        return func

