import time
import sys
import zipfile
import json

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = """Convert a save file in a psave format"""
    args = "infile [outfile]"
    can_import_settings = False
    requires_model_validation = False

    def handle(self, infile=None, outfile="-", **option):
        if infile is None:
            sys.exit("You need to provide a filename")
        outfile = open(outfile, "w") if outfile != '-' else sys.stdout
        savefile = zipfile.ZipFile(infile)
        categoriesfile = savefile.open("Category")
        categorieslist = json.load(categoriesfile)
        categories = {}
        subcategoriesfile = savefile.open("SubCategory")
        subcategorieslist = json.load(subcategoriesfile)
        subcategories = {}
        stagesfile = savefile.open("Stage")
        stageslist = json.load(stagesfile)
        stages = {}
        stationsfile = savefile.open("Station")
        stationslist = json.load(stationsfile)
        stations = {}
        personsfile = savefile.open("Person")
        personslist = json.load(personsfile)
        persons = {}
        pathsfile = savefile.open("Path")
        pathslist = json.load(pathsfile)
        paths = {}
        laptypesfile = savefile.open("LapType")
        laptypeslist = json.load(laptypesfile)
        laptypes = {}

        teamsfile = savefile.open("Team")
        teams = json.load(teamsfile)
        passagesfile = savefile.open("Passage")
        passages = json.load(passagesfile)

        for s in stationslist:
            stations[s["pk"]] = s["fields"]["name"]
        for c in categorieslist:
            categories[c["pk"]] = c["fields"]["name"]
        for sc in subcategorieslist:
            subcategories[sc["pk"]] = sc["fields"]["name"]
        for p in personslist:
            persons[p["pk"]] = p["fields"]["first_name"] + " " + p["fields"]["last_name"]
        for p in pathslist:
            paths[p["pk"]] = p["fields"]["name"]
        for l in laptypeslist:
            laptypes[l["pk"]] = l["fields"]["name"]
        for s in stageslist:
            stages[s["pk"]] = laptypes[s["fields"]["lap_type"]]

        for t in teams:
            team = t["pk"]
            f = t["fields"]
            cat = categories[f["category"]]
            members = []
            path = ""
            sub_cats = []
            try:
                members = [persons[pk] for pk in f["members"]]
                path = paths[f["path"]]
                sub_cats = [subcategories[pk] for pk in f["subcategories"]]
            except KeyError, IndexError:
                pass
            entry = {
                        "function": "add_team",
                        "reason": "savepsave",
                        "kwargs": {
                            "category": cat,
                            "nb": team,
                            "members": members,
                            "path": path,
                            "sub_cats": sub_cats,
                        }
                    }
            outfile.write(json.dumps(entry)+"\n")

        tformat = "%Y-%m-%d %H:%M:%S"
        for p in passages:
            f = p["fields"]
            uuid = None
            stage = None
            try:
                if f["deleted"]:
                    continue
                uuid = f["uuid"]
                stage = stages[f["stage"]]
            except KeyError:
                pass

            timestamp = time.mktime(time.strptime(f["time"], tformat))
            team = f["team"]
            station = stations[f["station"]]

            entry = {
                "function": "add_passage",
                "reason": "save2psave",
                "kwargs": {
                    "timestamp": timestamp,
                    "station": station,
                    "team": team,
                    "uuid": uuid,
                    "stage": stage,
                }
            }
            outfile.write(json.dumps(entry)+"\n")
        outfile.close()
