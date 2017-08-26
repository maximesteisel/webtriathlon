from webtriathlon import LOG
import _functions

class FunctionDoesNotExist(Exception):
    pass

def dispatch(data):
    funcname = data["function"]
    if funcname.startswith("_"):
        raise FunctionDoesNotExist("%s does not exist"%funcname)
    kwargs = data["kwargs"]
    LOG.debug("%s(**%s)"%(funcname, kwargs))
    kwargs = dict((k.encode("ascii"), v) for k,v in kwargs.items())
    try:
        func = getattr(_functions, funcname)
    except AttributeError:
        raise FunctionDoesNotExist('%s does not exist'%funcname)
    return func(**kwargs)


