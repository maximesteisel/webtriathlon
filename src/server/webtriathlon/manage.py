#!/usr/bin/env python

""" This module allow to run django commands (https://docs.djangoproject.com/en/dev/ref/django-admin/)

Some custom commands are provided:
    * By user_site:
        * simulate : Simulate a user_site and generate a psave (usefull for testing)
    * By save:
        * csv2psave : convert a csv file to a psave file (for compatibility with other systems
        * save2psave : convert a save file (database snapshot) to a psave file (to alow import of save file when the database format has changed)
        * dbversion : generate a opaque string that is automatically changed with each db format change.

For information on how to use one of these commands, run "python manage.py help command_name"

"""

import os, sys
import threading

os.environ["DJANGO_SETTINGS_MODULE"] = "settings"
# twisted may call manage.py, but it will set WT_TEST before
# so the following call only apply when manually runnig manage.py
os.environ.setdefault("WT_TEST", "1")

try:
    import settings # Assumed to be in the same directory.
except ImportError:
    sys.stderr.write("Error: Can't find the file 'settings.py' in the directory containing %r. It appears you've customized things.\nYou'll have to run django-admin.py, passing it your settings module.\n(If the file settings.py does indeed exist, it's causing an ImportError somehow.)\n" % __file__)
    sys.exit(1)

if __name__ == "__main__":
    import webtriathlon.monkeypatch
    from django.core.management import execute_manager
    execute_manager(settings)
