""" This module redefine several functions in other modules
to adapt their behaviour """

from webtriathlon import LOG
LOG.debug("Monkey patching")


## Accept empty emails in createsuperuser
from django.contrib.auth.management.commands import createsuperuser

_valid = createsuperuser.is_valid_email

def valid(value):
    if value.strip():
        return _valid(value)
    else: #empty email
        return True

createsuperuser.is_valid_email = valid

##

## If running server.py as a zip file;
# redirect calls to listdir and open to the equivalents Zipfile methods
# and change the way django find the management package of app
# To find it, django
# use pkgutil to avoid directly importing app.management, which could have
# side-effects. Unfortunatly, pkgutil does'nt work in a zip,
# but we can import app.management
# since we know that in this program it doesn't have side-effects.
import os, sys
from os.path import join, abspath, dirname
import zipfile
from django.core import management

# replace find_management_module only if we are in a zip file (set by __main__)
zip_path = os.environ.get("WT_ZIP", "")
if zip_path:
    def find_management_module(app):
        __import__(app)
        m = sys.modules[app]
        return join(dirname(m.__file__), "management")
    management.find_management_module = find_management_module
    import __builtin__
    real_open = __builtin__.open
    zf = zipfile.ZipFile(zip_path)

    def extract_zipname(name):
        absname = abspath(name)
        is_zip = absname.startswith(zip_path)
        zip_name = is_zip and absname[len(zip_path)+1:] or absname
        return (is_zip, zip_name)

    def open_zipfile(name, mode='r', *args, **kwargs):
        is_zip, name = extract_zipname(name)
        if name != zip_path and is_zip:
            mode = mode.replace("b", "")
            try:
                return zf.open(name, mode=mode, *args, **kwargs)
            except KeyError:
                import errno
                raise IOError((errno.ENOENT, "File Not Found"))
        return real_open(name, mode=mode, *args, **kwargs)
    __builtin__.open=open_zipfile

    real_listdir = os.listdir
    def listdir_zipfile(path):
        is_zip, path = extract_zipname(path)
        if is_zip:
            path_parts = path.split(os.path.sep)
            level = len(path_parts)
            namelist = [f.split("/") for f in zf.namelist()]
            return [ps[-1] for ps in namelist if len(ps) == level+1 and ps[:-1]==path_parts and ps[-1]]
        return real_listdir(path)
    os.listdir = listdir_zipfile


