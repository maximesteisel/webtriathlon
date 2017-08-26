# coding: utf-8
import time
import sys
import random
import json

from django.core.management.base import BaseCommand

def rel_gauss(mu, rsd=5./100):
    return random.gauss(mu, mu*rsd)

CALC_STEP=0.020 #s
START_STEP=5 #s
NAMES=["Gerard", "Etienne", "Zoé", "Jean", "Thomas", "Bjorn",
        "Olivier", "Marc", "Lily", "Laura", "Nathan", "Victor",
        "John", "David", "William", "Aazzi", "Abam", "Vinza",
        "Greg", "Susan", "Chrissie", "Harriet", "Sean"]

class Player:
    speed=20 #m/s
    accident_prob=.0001 # /s
    reparation_time=100 #s
    rsd=15./100 # relative std deviation
    name=None
    error_prob=0.02

    def __str__(self):
        return "%s (%s) speed:%s"%(self.name, self.team, self.speed)

    def __init__(self, team):
        self.speed=rel_gauss(self.speed, self.rsd)
        self.accident_prob=rel_gauss(self.accident_prob, self.rsd)
        self.speed=rel_gauss(self.speed, self.rsd)
        if self.name is None:
            self.name = random.choice(NAMES)
            NAMES.remove(self.name)

        self.team=team

        self.current_lap=1
        self.current_place=0
        self.reparation_left=0
        self.finished=False

class VIP(Player):
    rsd=5./100

class Denis(VIP):
    name="Denis"
    speed=22
    accident_prob=.00005 # /s
    reparation_time=60 #s

class Cedric(VIP):
    name="Cedric"
    speed=25
    accident_prob=.0002 # /s
    reparation_time=10 #s
    error_prob=0.0001

class Command(BaseCommand):
    help = """Convert a save file in a psave format"""
    args = "category station nb_laps lap_length [outfile]"
    can_import_settings = False
    requires_model_validation = False

    def handle(self, nb_laps, lap_length, realtime=False, make_psave=False, category=None, station=None, outfile="-", **option):
        nb_laps=int(nb_laps)
        lap_length=int(lap_length)
        players = [Denis(team=2), Cedric(team=1)]+[Player(team=5+i) for i in range(10)]
        random.shuffle(players)
        if make_psave:
            outfile = open(outfile, "w") if outfile != '-' else sys.stdout
            for p in players:
                entry = {
                    "function": "add_team",
                    "reason": "simulation",
                    "kwargs": {
                        "category": category,
                        "nb": p.team,
                        "members": [p.name],
                    }
                }
                print p
                outfile.write(json.dumps(entry)+"\n")
                p.current_place=random.uniform(0, lap_length)
        timestamp=time.time()
        start = timestamp
        while not all(p.finished for p in players):
            for p in players:
                if p.finished:
                    continue
                if p.reparation_left:
                    p.reparation_left-=CALC_STEP
                    if p.reparation_left<=0:
                        p.reparation_left=0
                        print("%s has recover from his accident."%(p.name))
                    continue
                if random.random()<=p.accident_prob:
                    print("Oh no! %s (%s) had an accident"%(p.name, p.team))
                    p.reparation_left=rel_gauss(p.reparation_time)
                    continue
                p.current_place+=rel_gauss(p.speed)*CALC_STEP
                if p.current_place>lap_length:
                    print("%s (%s) has just crossed the line."%(p.name, p.team))
                    print("He has done %s lap"%p.current_lap)
                    p.current_lap+=1
                    p.current_place%=lap_length
                    if p.current_lap == nb_laps:
                        if random.random() < p.error_prob:
                            print("He thinks he has finished. What a dumb!")
                            p.finished=True
                    if p.current_lap > nb_laps:
                        if random.random() < p.error_prob:
                            print("He is not tired enought apparently, he is doing an extra lap.")
                        else:
                            p.finished=True
                            print("He now has finished")
                            print(p)
                            print("Total time:%s"%(timestamp-start))
                            print("Real speed:%s"%((p.current_lap*lap_length)/(timestamp-start)))
                    if make_psave:
                        entry = {
                            "function": "add_passage",
                            "reason": "simulation",
                            "kwargs": {
                                "timestamp": timestamp,
                                "station": station,
                                "team": p.team,
                            }
                        }
                        outfile.write(json.dumps(entry)+"\n")
            timestamp+=CALC_STEP
            if realtime:
                time.sleep(CALC_STEP)





