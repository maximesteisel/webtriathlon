#!/usr/bin/env python
# coding: utf-8
import os, sys

#in pyw files, stdout and stderr are invalid descriptors
if ( sys.platform == 'win32' and sys.executable.split( '\\' )[-1] == 'pythonw.exe'):
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open('stderr.log', 'w')
    sys.stdin = open(os.devnull, 'r')

import zipfile
import time
import datetime
from optparse import OptionParser

import gtk
from twisted.internet import defer
from twisted.internet import gtk2reactor
gtk2reactor.install()
from twisted.internet import reactor


from aclient import AClient
from sclient import S_SENT
from client import S_DELETED, S_DUP, S_ERROR

def zip_open(zipname, fname):
    if os.path.isfile(zipname):
        zf = zipfile.ZipFile(zipname)
        return zf.open(fname)
    else:
        return open(os.path.join(zipname, fname), "r")

def gtk_update():
    while gtk.events_pending():
        gtk.main_iteration_do(False)

def parse_time(text):
    "Parse a text and return a timestamp"
    try:
        dtime = datetime.datetime.strptime(text, "%H:%M:%S").time()
    except ValueError:
        dtime = datetime.datetime.strptime(text, "%H:%M").time()
    dtime = datetime.datetime.combine(datetime.date.today(), dtime)
    timestamp = long(time.mktime(dtime.timetuple()))
    return timestamp


class Main:
## Python special methods
    def __init__(self, options):
        self.log = open(
            "wtencoder.log", "a")
        self.log.write("* New session %s *\n"%(datetime.datetime.now()))
        builder = gtk.Builder()
        self.builder = builder
        f = zip_open(sys.argv[0], "encoder.glade")
        self.builder.add_from_string(f.read())

        builder.connect_signals(self)

        self.client = AClient()

# settings
        self.settings = { "server_address": "localhost",
                "server_port": "8000",
                "station_name": "",
                }

# add command-line settings
        for key in self.settings:
            val = options.__dict__.get(key, None)
            if val is not None:
                self.settings[key] = val


#Widgets shortcut
        self.prefs_dialog = self.builder.get_object("config_dialog")
        self.add_team_dialog = self.builder.get_object("add_team_dialog")

        self.mainwindow = builder.get_object("main_window")
        self.mainwindow.present()
        self.passages_list = builder.get_object("list_passages")
        self.path_list = builder.get_object("path_list")
        self.station_list = builder.get_object("station_list")
        self.passages_view = builder.get_object("passages")
        self.time_label = builder.get_object("time_label")

        self.columns_def = [
# Label, internal_name, type, displayed, editable
                (None, "color", str, False, False),
                ("Équipe", "team", str, True, True),
                ("Catégorie", "category", str, True, False),
                ("Parcours", "path", str, True, False),
                ("Heure", "time", str, True, True),
                ("Étape", "stage", str, True, True),
                ("Station", "station", str, True, True),
                ("# Tour", "lap_nb", str, True, False),
                ("Restants", "nb_lap_left", str, True, False),
                ("Status", "status", str, True, False),
                ("Message", "msg", str, True, False),
                (None, "uuid", str, False, False),
                (None, "timestamp", long, False, True),
                (None, "editable", bool, False, False),
                ]

        self.team_n_list = [builder.get_object("team_%s"%i) for i in range(10)]
        self.teams = {}
        for i, t in enumerate(self.team_n_list, 1):
            self.teams[t] = i
            t.set_label(str(i))

        self.EXPECTED_UPDATE_INTERVAL=5000
        gtk.timeout_add(self.EXPECTED_UPDATE_INTERVAL, self.update_expected_teams_timeout)

        self.RECONNECTION_INTERVAL=10000
        gtk.timeout_add(self.RECONNECTION_INTERVAL, self.reconnect_timeout)

        self.UPDATETIME_INTERVAL=200
        gtk.timeout_add(self.UPDATETIME_INTERVAL, self.update_time_timeout)

        self.columns = {}
        self.columns_types = {}
        self.passages_list = gtk.ListStore(*(c[2] for c in self.columns_def))
        self.passages_list.connect("row-inserted", self.row_inserted_cb)
        self.passages_view.set_model(self.passages_list)

        for i, (label, name, type_, displayed, editable) in enumerate(self.columns_def):
            self.columns[name] = i
            self.columns_types[i] = type_
            if not displayed:
                continue
            text_render = gtk.CellRendererText()
            if editable:
                text_render.set_property("editable", True)
                text_render.set_property("font", "oblique")
                text_render.connect("edited", self.cell_edited_cb, i)
            column = gtk.TreeViewColumn(label, text_render,
                    text=i, foreground=self.columns["color"])
            column.set_resizable(True)
            column.set_expand(True)
            self.passages_view.append_column(column)
        self.passages_list.set_default_sort_func(self.cmp_passage)
        self.passages_list.set_sort_column_id(-1, gtk.SORT_ASCENDING)

        path_entry = builder.get_object("path_entry")
        path_entry.connect("activate",
                self.path_passage_clicked_cb)

        self.connected_icon = builder.get_object("connected")
        self.status_bar = builder.get_object("statusbar")
        self.main_context_id = self.status_bar.get_context_id("main")
        self.network_context_id = self.status_bar.get_context_id("network")
        self.status_bar.push(self.main_context_id,
                "Bienvenue")

### General methods
    def log_passage(self, id, timestamp, station, team, status):
        self.log.write("%s: %s [%s] %s %s %s\n"%(id, timestamp, datetime.datetime.now(),
            station, team, status))
        self.log.flush()

    def print_deferred(self, failure):
        failure.printTraceback()

    def do_and_callback(self, f, fargs=(), cb=None, cbargs=()):
        """Call the function, wrap the result in a deferred if necessary then
        add the callback"""

        def errback(failure):
            return S_ERROR, str(failure)

        def def_callback(result, *args):
            status, passage = result
            return self.update_passage(passage, *args, status=status)
        if cb==None:
            cb=def_callback
        d = defer.maybeDeferred(f, *fargs)
        d.addErrback(errback)
        d.addCallback(cb, *cbargs)

    def cmp_passage(self, treemodel, iter1, iter2, *args):
        columns = self.columns
        col = columns["timestamp"]
        time1 = self.passages_list.get_value(iter1, col)
        time2 = self.passages_list.get(iter2, col)
        return cmp(time1, time2)

    def get_entry_text(self, entry_name):
        return self.builder.get_object(entry_name).get_text()

### UI-related methods

    def run(self):
        self.update_prefs_dialog()
        self.update_settings()
        if not self.check_settings():
            self.show_prefs()
        reactor.run()

    def check_settings(self, settings=None):
        """Check that the settings are correct"""
        if settings is None:
            settings = self.settings
        return bool(settings["station_name"])

    def update_prefs_dialog(self):
        server_entry = self.builder.get_object("server_address")
        port_entry = self.builder.get_object("server_port")
        station_entry = self.builder.get_object("station_name_entry")
        server_entry.set_text(self.settings["server_address"])
        port_entry.set_text(str(self.settings["server_port"]))
        station_entry.set_text(self.settings["station_name"])

    def update_expected_teams(self, expected_teams):
        new_teams = set(expected_teams) - set(self.teams.values())
        for button, team in self.teams.items():
            if not new_teams:
                break
            if team not in expected_teams:
                new_team = new_teams.pop()
                self.teams[button]=new_team
                button.set_label(str(new_team))

    def reconnect_timeout(self):
        self.client.connect()
        return True

    def update_time_timeout(self):
        self.time_label.set_label(datetime.datetime.now().strftime("%H:%M:%S"))
        return True

    def update_expected_teams_timeout(self):
        self.do_and_callback(self.client.get_expected_teams, cb=self.update_expected_teams)
        return True #That mean the function must be called again in DELAY

    def update_settings(self):
        server_entry = self.builder.get_object("server_address")
        port_entry = self.builder.get_object("server_port")
        station_entry = self.builder.get_object("station_name_entry")
        self.settings["server_address"] = server_entry.get_text()
        self.settings["station_name"] = station_entry.get_text()
        try:
            self.settings["server_port"] = int(port_entry.get_text())
        except ValueError:
            self.settings["server_port"] = 8000
        print self.settings

        self.client.set_host(
                self.settings["server_address"],
                int(self.settings["server_port"]),
                )
        self.client.station = self.settings["station_name"]

        self.client.connect()

        self.status_bar.push(
            self.main_context_id, "%s: %s"%(self.settings["server_address"],
                self.settings["station_name"]))

        self.do_and_callback(self.client.get_stations, cb=self.update_choices, cbargs=(self.station_list,))
        self.do_and_callback(self.client.get_paths, cb=self.update_choices, cbargs=(self.path_list,))
        print self.client

    def update_choices(self, choices, lst):
        self.set_choices(lst, choices)

    def show_prefs(self):
        self.update_prefs_dialog()
        self.prefs_dialog.present()

    def config_response_cb(self, dialog, response, *args):
        print "got response for the config dialog", response
        if response == gtk.RESPONSE_APPLY:
            self.update_settings()
        elif response == gtk.RESPONSE_CANCEL:
            self.update_prefs_dialog()
        elif response == gtk.RESPONSE_CLOSE:
            if not self.check_settings():
                self.show_saved_passage_and_quit()
            else:
                dialog.hide()
        if self.check_settings():
            self.prefs_dialog.hide()

    def show_saved_passage_and_quit(self):
        def quit_cb(dlg, response):
            print "got response to passages dialog"
            self.quit()
        nb_saved = self.client.nb_saved()
        if nb_saved:
            dlg = self.show_dialog("%s requêtes ont été sauvegardées dans le"
                    " fichier %s . Ce fichier doit être envoyé au"
                    " serveur central."%(nb_saved, self.client.get_filename()))
            print dlg
            dlg.connect("response", quit_cb)
        else:
            self.quit()


    def show_dialog(self, text):
        def show_dialog_response_cb(dlg, response):
            dlg.hide()
        dlg = gtk.MessageDialog(flags=gtk.DIALOG_DESTROY_WITH_PARENT, buttons=gtk.BUTTONS_OK, message_format=text)
        dlg.connect("response", show_dialog_response_cb)
        dlg.present()
        return dlg

    def print_status(self, status):
        stat, msg = status
        message = "Status: %s"%stat
        if msg:
            message += " (%s)"%msg
        self.show_dialog(message)

    def get_and_update(self, id, *args):
        """Fetch a passage and update the displayed infos"""
        self.do_and_callback(f=self.client.get_passage, fargs=(id, False),
                cb=self.update_passage, cbargs=args)

    def update_passage(self, passage, iter, tries = 0, status=None):
        """Update the passage at iter with the new infos in passage"""
        if status:
            stat, msg = status
        else:
            stat, = self.passages_list.get(iter,
                self.columns["status"],
                )
            msg = None
        if not passage:
            self.passages_list.set(iter,
                self.columns["status"], stat,
                self.columns["msg"], msg,
                )
            return

        p = passage
        timestamp = p["timestamp"]
        localtime = time.localtime(timestamp)
        timefmt = time.strftime("%H:%M:%S", localtime)
        id = p["uuid"]
        team = p["team_nb"]
        stage = p["stage_name"]
        category = p["category_name"]
        path = p["path_name"]
        station = p["station_name"]
        nb = p.get("lap_nb", None)
        nb_laps = p.get("nb_laps", 0)
        deleted = p.get("deleted", None)
        duplicate = p.get("duplicate_uuid", None)
        errors = p.get("errors", [])
        team_errors = p.get("team_errors", [])

        if nb is not None:
            left = nb_laps - nb
            left = max(0, left)
            color = "#000" #Black
            if left == 1:
                color = "#7F7" #ligth green
                if msg is None:
                    msg = "ENCORE UN TOUR"
# nb == 0 if this is the first passage (the starting line)
            elif nb == nb_laps != 0:
                color = "#0F0" #green
                if msg is None:
                    msg = "FIN DE L'ETAPE"
            elif nb > nb_laps:
                color = "#F60" #orange
                if msg is None:
                    msg = "TOUR EN TROP"
        else:
            # The passage was send but the corresponding lap
            # is unknown, wait a bit longer and retry
            color = "#444" # Dark grey
            left = None
            if not errors and stat == S_SENT and tries < 10:
                tries += 1
                delay = 0.2 * 2**tries
                reactor.callLater(delay, self.get_and_update, id, iter, tries, (stat, None))

        if deleted:
            color = "#999" # light gray
            if stat != S_DELETED:
                msg = stat
                stat = S_DELETED
        elif duplicate:
            if msg is None:
                msg = S_DUP
        elif errors or team_errors:
            if nb:
                nb = "[%s]"%nb
            if left:
                left = "[%s]"%left
                msg = "TOURS RESTANTS PAS FIABLE"
            if errors:
                msg = errors[0]
                color = "#F60" # orange

        print "%s/%s => color: %s, stat:%s, msg: %s"%(nb, nb_laps, color, stat, msg)
        self.passages_list.set(iter,
                self.columns["uuid"], id,
                self.columns["team"], str(team),
                self.columns["category"], category,
                self.columns["path"], path,
                self.columns["time"], timefmt,
                self.columns["timestamp"], long(timestamp),
                self.columns["stage"], stage,
                self.columns["station"], station,
                self.columns["lap_nb"], str(nb),
                self.columns["nb_lap_left"], str(left),
                self.columns["color"], color,
                self.columns["status"], stat,
                self.columns["msg"], msg,
                self.columns["editable"], True,
                )
        self.log_passage(id, timestamp, station, team, status)

    def update_passages(self, result, iter):
        status, passages = result
        if not passages:
            self.passages_list.set(iter,
                    self.columns["status"], status[0],
                    self.columns["msg"], status[1],
                    self.columns["editable"], False,
                    )
        else:
            self.passages_list.remove(iter)
            gtk_update()
            for p in passages:
                i = self.passages_list.append()
                self.update_passage(p, i, status=status)
# Gtk crash sometimes if too many events are in the queue on Windows
                gtk_update()
                print("gtk updated")



### Server-related functions
    def add_team_response_cb(self, dlg, response):
        print dlg, response
        if response == gtk.RESPONSE_APPLY:
            try:
                team = int(self.get_entry_text("team_nb"))
            except ValueError:
                self.show_dialog(text="Numéro d'équipe non valide")
                return

            category = self.get_entry_text("category")
            path = self.get_entry_text("path")
            members = []
            for i in range(1, 4+1):
                m = self.get_entry_text("member%i"%i)
                if m:
                    members.append(m)

            self.do_and_callback(self.client.add_team, (team, category, path, members), self.print_status)
        elif response == gtk.RESPONSE_CLOSE:
            self.add_team_dialog.hide()
            return

    def add_team(self):
        self.add_team_dialog.show()

    def add_passage(self, team, timestamp=None):
        if not timestamp:
            timestamp=time.time()
        station = self.settings["station_name"]
        iter = self.passages_list.append()
        localtime = time.localtime(timestamp)
        timefmt = time.strftime("%H:%M:%S", localtime)
        self.passages_list.set(iter,
                self.columns["team"], str(team),
                self.columns["time"], timefmt,
                self.columns["station"], station,
                self.columns["status"], "En cours",
                self.columns["editable"], True,
                )
        self.do_and_callback(self.client.add_passage, (station, team, timestamp), cbargs=(iter,))
        self.update_expected_teams_timeout()
        return iter


    def add_passage_to_path(self, path, timestamp=None):
        if not timestamp:
            timestamp=time.time()
        station = self.settings["station_name"]
        iter = self.passages_list.append()
        localtime = time.localtime(timestamp)
        timefmt = time.strftime("%H:%M:%S", localtime)
        self.passages_list.set(iter,
                self.columns["team"], path,
                self.columns["time"], timefmt,
                self.columns["station"], station,
                self.columns["status"], u"En cours",
                )
        self.do_and_callback(self.client.add_passage_to_path, (station, path, timestamp), cb=self.update_passages, cbargs=(iter,))
        return iter

 ### GTK+ callbacks
    def send_team(self, button):
        self.add_team_dialog.response(gtk.RESPONSE_APPLY)

    def cancel_add_team(self, button):
        self.add_team_dialog.response(gtk.RESPONSE_CLOSE)

    def accept_prefs(self, button):
        self.prefs_dialog.response(gtk.RESPONSE_APPLY)

    def cancel_prefs(self, button):
        self.prefs_dialog.response(gtk.RESPONSE_CANCEL)

    def close_prefs(self, button):
        self.prefs_dialog.response(gtk.RESPONSE_CLOSE)

    def quit(self):
        gtk.main_quit()
        reactor.stop()
        os._exit(0)

    def gtk_main_quit(self, *args):
        print "gtk_main_quit"
        self.quit()

    def delete_main(self, *args):
        self.show_saved_passage_and_quit()
        return True #Don't delete yet, wait for the response to the dialog"

    def settings_clicked_cb(self, button):
        self.show_prefs()

    def add_team_clicked_cb(self, button):
        self.add_team()

    def send_saved_clicked_cb(self, button):
        def sent(result):
            iter=None
            for (status, ret) in result :
                print  status, ret
                for obj in ret:
                    print obj, type(obj)
                    if "uuid" in obj: #look like a passage
                        iter = self.passages_list.append()
                        self.update_passage(obj, iter, status=status)
            if iter: #scroll to the last updated item
                path = self.passages_list.get_string_from_iter(iter)
                self.passages_view.scroll_to_cell(path)
                team = self.builder.get_object("team_spin")
                team.grab_focus()
        self.do_and_callback(self.client.send_saved, cb=sent)

    def team_n_clicked_cb(self, button):
        print "team_n clicked"
        team_nb = self.teams[button]
        iter = self.add_passage(team_nb)
        path = self.passages_list.get_string_from_iter(iter)
        self.passages_view.scroll_to_cell(path)
        team = self.builder.get_object("team_spin")
        team.grab_focus()

    def row_inserted_cb(self, model, path, iter):
        print "row inserted", model, path, iter
        self.passages_view.scroll_to_cell(path)

    def team_passage_clicked_cb(self, button):
        print "passage clicked"
        team = self.builder.get_object("team_spin")
        team_nb = int(team.get_text())
        iter = self.add_passage(team_nb)
        path = self.passages_list.get_string_from_iter(iter)
        self.passages_view.scroll_to_cell(path)
        team.set_text("")
        team.grab_focus()

    def team_spin_changed(self, entry):
        text = entry.get_text()
        if(len(text)>2):
            gtk.gdk.beep()

    def path_passage_clicked_cb(self, button):
        print "category passage clicked"
        path = self.builder.get_object("path_entry")
        path_name = path.get_text()
        iter = self.add_passage_to_path(path_name)
        path = self.passages_list.get_string_from_iter(iter)
        self.passages_view.scroll_to_cell(path)
        team = self.builder.get_object("team_spin")
        team.grab_focus()

    def passages_key_press_event_cb(self, widget, event):
        team_spin = self.builder.get_object("team_spin")
        keyname = gtk.gdk.keyval_name(event.keyval)
        if keyname.startswith("KP_"):
            keyname = keyname[3:]
        control = event.state & gtk.gdk.CONTROL_MASK
        print event, keyname

        if keyname == "Delete":
            model, iter = self.passages_view.get_selection().get_selected()
            if iter:
                (id, team, time, station) = self.passages_list.get(iter, self.columns["uuid"],
                        self.columns["team"], self.columns["time"],
                        self.columns["station"])
                if id:
                    self.do_and_callback(self.client.delete_passage, (id,), cbargs= (iter,))

        elif keyname == "Return" or keyname == "Enter":
            team_spin.emit("activate")

        elif keyname.isdigit():
            team_spin.insert_text(keyname, -1)

        elif control and keyname == "r":
            model, iter = self.passages_view.get_selection().get_selected()
            (id,) = self.passages_list.get(iter,
                    self.columns["uuid"],
                    )
            self.get_and_update(id, iter)

        else:
            return False

        return True

    def cell_edited_cb(self, renderer, path, new_text, column):
        iter = self.passages_list.get_iter(path)
        old, = self.passages_list.get(iter, column)

        def restore():
            self.passages_list.set(iter, column, old)

        editable = self.passages_list.get(iter,
                self.columns["editable"],
                )

        if not editable: #passage was added to a category
            restore()
            return #not implemented

        if column == self.columns["time"]:
            timestamp = parse_time(new_text)
            self.passages_list.set(iter,
                    self.columns["timestamp"], long(timestamp),
                    )

        self.passages_list.set(iter,
                column, self.columns_types[column](new_text),
                self.columns["status"], "En cours",
                self.columns["msg"], None,
                self.columns["lap_nb"], None,
                self.columns["nb_lap_left"], None,
                )

        id, station, team, timestamp, stage = self.passages_list.get(iter,
            self.columns["uuid"],
            self.columns["station"],
            self.columns["team"],
            self.columns["timestamp"],
            self.columns["stage"],
            )

        self.do_and_callback(self.client.modify_passage, (id, station, int(team),
                    timestamp, stage), cbargs=(iter,))

    def set_choices(self, lst, elements):
        lst.clear()
        for e in elements:
            lst.append((e,))


def main():
    parser = OptionParser()
    parser.add_option("-a", "--server-address", dest="server_address",
            help="Main server ip address",)
    parser.add_option("-p", "--server-port", dest="server_port",
            help="Main server ip port",)
    parser.add_option("-s", "--station", dest="station_name",
            help="Name of this station as encoded in the main server")
    (options, args) = parser.parse_args()
    main = Main(options)
    main.run()

if __name__ == "__main__":
    main()

