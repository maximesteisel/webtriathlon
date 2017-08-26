#coding: utf-8

#start the program like a zip file or directory

# This file will set several environement variable:
#   * WT_TEST: indicate if we should use the production or the test DB
#   * WT_ZIP: if started as a zip, it is the absolute path to the zip
#   * DJANGO_SETTINGS_MODULE: used by django to find the settings
#   * PYTHONPATH: used by python to find embeeded package in external/


import sys, os
import time, datetime
import signal
from os.path import abspath, isdir, join, expanduser
from zipfile import ZipFile
from subprocess import call, Popen, PIPE
from shutil import rmtree, copy, move
from tempfile import mkdtemp
from fnmatch import filter
import tempfile
import signal
import random
import __builtin__

# The program can be executed zipped
# WT_ZIP will be set to the absolute path to the zipfile
# DATA_DIR contain static data (css, images)
# When executing a zip, it is better to
# extract the data to avoid extracting them at each request
DATA_DIR = os.path.join(sys.argv[0], "data")
temp_dir = None
try:
    zf = ZipFile(sys.argv[0])
except IOError, e:
    pass
else:
    temp_dir = mkdtemp()
    data_files = filter(zf.namelist(), "data/*")
    zf.extractall(temp_dir, data_files)
    DATA_DIR = os.path.join(temp_dir, "data")
    os.environ["WT_ZIP"] = abspath(sys.argv[0])
    zf.close()

# The tac file is a python file setting up the Twisted server
# and allowing Django to work with Twisted
tacfile = join(DATA_DIR, "server.tac")
# Django need the name of the module containing the server settings
os.environ["DJANGO_SETTINGS_MODULE"] = "webtriathlon.settings"
os.environ["WT_DATA_DIR"] = DATA_DIR
external_dir = os.path.join(sys.argv[0], "external")
sys.path.insert(0, external_dir )
# PYTHONPATH contain a list of path to prepend to sys.path
# It need to contain the path to the zipfile (sys.argv) and the path
# to the dir containing embeeded external module
os.environ["PYTHONPATH"] = external_dir + os.pathsep + sys.argv[0]
os.environ.setdefault("WT_TEST", "")

def trap(sig, frame):
    # Trap only once
    signal.signal(sig, signal.SIG_DFL)

def get_db_name(testing=False):
    from webtriathlon import settings
    os.environ["WT_TEST"] = "1" if testing else ""
    reload(settings)
    return settings.DATABASES["default"]["NAME"]

def drop_database(db_name):
    try:
         os.unlink(db_name)
    except OSError:
         pass

def rename_database(old, new):
    copy(old,new)

def start_server(*args):
    # Ignore SIGINT that will be handled by the sub-process python
    signal.signal(signal.SIGINT, trap)
    return Popen((sys.executable, "-m", "twistd", "-ny", tacfile ) + args)

def run_django_command(*args):
    process = Popen((sys.executable, "-m","webtriathlon.manage") + args)

    def trap(sig, frame):
       stop_process(process)

    # Ignore SIGINT that will be handled by the sub-process python
    signal.signal(signal.SIGINT, trap)
    process.wait()
    signal.signal(signal.SIGINT, signal.default_int_handler)

def stop_process(popenobj):
    i=0
    while popenobj.poll() is None:
        if i>=3:
            print "killing server"
            server_process.send_signal(signal.SIGKILL)
        if i>10:
            print "could not kill server"
            break
        time.sleep(0.2)
        i+=1

    call((sys.executable, "-m","webtriathlon.manage") + args)

def add_100_passages():
    os.environ["WT_TEST"] = "1"

    t=time.time()
    from webtriathlon.core import path
    for i in range(100):
        t+=5
        path.add_passage("Leenberg", 1, datetime.datetime.fromtimestamp(t))


server_process = None
try:
    while 1:
        menu=u"""
        Que voulez-vous faire?
    1. Démarrer le serveur
    2. Démarrer le serveur de test
    3. Supprimer la base de données
    4. Supprimer la base de données test
    5. Copier la base de donnée (prod -> test)
    6. Copier la base de donnée (test -> prod)
    7. Exécuter une commande Django (essayez la commande 'help')
    8. Exécuter une commande Django sur la base de donnée test
    9. Exécuter une commande SQL
    10. Exécuter une commande SQL sur la base de donnée test
    11. Quitter
    Entrez un numéro: """

        # Bypass the menu by using the command argument
        if len(sys.argv) > 1:
            if sys.argv[1] == "server":
                val = 1
            elif sys.argv[1] == "testserver":
                val = 2
            elif sys.argv[1] == "profile":
                import cProfile
                cProfile.run("add_100_passages()", "passage_profile")
                break
            else:
                run_django_command(*sys.argv[1:])
                break
        else:
            # Encode the menu to avoid UnicodeErrors in Windows
            val = raw_input(menu.encode(sys.stdout.encoding, "replace")).strip()
        try:
            val = int(val)
        except ValueError:
            continue
        else:
            if not (1 <= val <= 11):
                continue

        prod_db_name = get_db_name(testing=False)
        testing_db_name = get_db_name(testing=True)
        if val%2:
            os.environ["WT_TEST"] = ""
            testing = False
            db_name = prod_db_name
        else:
            os.environ["WT_TEST"] = "1"
            testing = True
            val = val-1
            db_name = testing_db_name


        if val==1:
            run_django_command("syncdb")
            server_process = start_server()
            break
        elif val==3:
            drop_database(db_name)
        elif val==5:
            if testing:
                rename_database(testing_db_name, prod_db_name)
            else:
                rename_database(prod_db_name, testing_db_name)
        elif val==7:
            commande = raw_input("Entrez une commande: ")
            cs = commande.split()
            run_django_command(*cs)
        elif val==9:
            run_django_command("dbshell")
        elif val==11:
            break

    if server_process:
        server_process.wait()

except KeyboardInterrupt:
    print "Keyboard Interrupt, killing server"
    if server_process:
        server_process.kill()

finally:
    if server_process and server_process.poll() is None:
        print "waiting for the server process to stop"
        stop_process(server_process)
    if temp_dir:
        rmtree(temp_dir)
        assert not os.path.exists(temp_dir)
