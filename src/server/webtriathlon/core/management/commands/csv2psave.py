import time
import sys
import json
from optparse import make_option
import csv
import uuid

def randid():
    return str(uuid.uuid1())

from django.core.management.base import BaseCommand

def get_multiple(d, *names):
    return [d.get(n) for n in names]

class Command(BaseCommand):
    help = """convert a csv file to a psave format
    The first row (title row) must match the fields below:
        * TYPE # values may be TEAM, PERSON or PASSAGE

# Fields used for TEAM objects:
        * CATEGORY
        * TEAM: number of the team

# Fields used for PERSON objects:
# only FIRSTNAME is obligatory
        * TEAM
        * FIRSTNAME
        * LASTNAME
        * AGE
        * ADDRESS
        * PHONE
        * MAIL
        * GENDER: either M of F

# Fields used for PASSAGE objects:
        * TEAM
        * SECONDS: number of seconds from an arbitrary start point (which may be specified by the -t option)
        * STATION

        """
    args = "[infile] [outfile]"
    option_list = BaseCommand.option_list + (
        make_option('-t', '--ref-time',
                    type='int', dest='time',
                    action='store', default=0,
                    help='Reference time as a unix timestamp (by default it is the current time)',
                   ),
    )
    requires_model_validation = False
    can_import_settings = False

    def handle(self, infile="-", outfile="-", **option):
        if infile == "-":
            f = sys.stdin
        else:
            f = open(infile, "rb")

        if outfile == "-":
            outfile = sys.stdout
        else:
            outfile = open(outfile, "w")

        now = option["time"]
        if not now:
            now = time.time()
        for r in csv.DictReader(f):
            print >> sys.stderr, r
            type_ = r.get("TYPE", "").strip()
            if type_ == "PASSAGE":
                try:
                    team, nbsec, station = r["TEAM"], r["SECONDS"], r["STATION"]
                except ValueError: #Too many|few values to unpack
                    print >> sys.stderr, "%s: bad format"%(record,)
                    continue
                nbsec = int(nbsec)
                team = int(team)
                timestamp = now + nbsec
                entry = {
                    "function": "add_passage",
                    "reason": "csv2psave",
                    "kwargs": {
                        "timestamp": timestamp,
                        "station": station,
                        "team": team,
                        "uuid": randid(),
                    }
                }
            elif type_ == "TEAM":
                try:
                    cat, team = r["CATEGORY"], r["TEAM"]
                except ValueError:
                    print >> sys.stderr, "Bad format"
                    continue
                team = int(team)
                entry = {
                    "function": "add_team",
                    "reason": "csv2psave",
                    "kwargs": {
                        "category": cat,
                        "nb": team,
                    }
                }
            elif type_ == "PERSON":
                try:
                    first = r["FIRSTNAME"]
                except ValueError:
                    print >> sys.stderr, "Bad format"
                    continue
                last, gender, age, team = get_multiple(r, "LASTNAME", "GENDER", "AGE", "TEAM")
                address, phone, mail = get_multiple(r, "ADDRESS", "PHONE", "MAIL")

                if age:
                    age = int(age)
                else:
                    age = None

                entry = {
                    "function": "add_person",
                    "reason": "csv2psave",
                    "kwargs": {
                        "first_name": first,
                        "last_name": last,
                        "genre": gender,
                        "team": int(team),
                        "age": age,
                        "address": address,
                        "phone": phone,
                        "email": mail,
                    }
                }

            else:
                sys.stderr.write("Invalid type: '%s'\n"%type_)

            outfile.write(json.dumps(entry)+"\n")

