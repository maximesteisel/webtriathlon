from django.core.cache import cache
from functools import wraps

def cache_func(time):
    def _decorator(wrapped):
        @wraps(wrapped)
        def _wrapper(*args, **kwargs):
            key = "f:%s:%s:%s"%(wrapped.__name__, args, kwargs)
            v = cache.get(key)
            if v is not None:
                return v
            v = wrapped(*args, **kwargs)
            cache.set(key, v, time)
            return v
        return _wrapper
    return _decorator


