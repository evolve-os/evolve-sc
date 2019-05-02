#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
#  This file is part of solus-sc
#
#  Copyright © 2013-2018 Ikey Doherty <ikey@solus-project.com>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or
#  (at your option) any later version.
#

from gi.repository import Gio, GObject, Notify, GLib

import comar
import pisi.db
import pisi.api
from operator import attrgetter
import time
import hashlib
import subprocess

SC_UPDATE_APP_ID = "com.solus_project.UpdateChecker"


class ScUpdateObject(GObject.Object):
    """ Keep glib happy and allow us to store references in a liststore """

    old_pkg = None
    new_pkg = None

    # Simple, really.
    has_security_update = False

    __gtype_name__ = "ScUpdateObject"

    def __init__(self, old_pkg, new_pkg):
        GObject.Object.__init__(self)
        self.old_pkg = old_pkg
        self.new_pkg = new_pkg

        if not self.old_pkg:
            return
        oldRelease = int(self.old_pkg.release)
        histories = self.get_history_between(oldRelease, self.new_pkg)

        # Initial security update detection
        securities = [x for x in histories if x.type == "security"]
        if len(securities) < 1:
            return
        self.has_security_update = True

    def is_security_update(self):
        """ Determine if the update introduces security fixes """
        return self.has_security_update

    def get_history_between(self, old_release, new):
        """ Get the history items between the old release and new pkg """
        ret = list()

        for i in new.history:
            if int(i.release) <= int(old_release):
                continue
            ret.append(i)
        return sorted(ret, key=attrgetter('release'), reverse=True)


# Correspond with gschema update types
UPDATE_TYPE_ALL = 1
UPDATE_TYPE_SECURITY = 2
UPDATE_TYPE_MANDATORY = 4

# Correspond with gschema update types
UPDATE_FREQ_HOURLY = 1
UPDATE_FREQ_DAILY = 2
UPDATE_FREQ_WEEKLY = 4

# absolute maximum permitted by Budgie
UPDATE_NOTIF_TIMEOUT = 20000

# Precomputed "next check" times
UPDATE_DELTA_HOUR = 60 * 60
UPDATE_DELTA_DAILY = UPDATE_DELTA_HOUR * 24
UPDATE_DELTA_WEEKLY = UPDATE_DELTA_DAILY * 7

# How many secs must elapse before checking if an update is due
PONG_FREQUENCY = 120


class ScUpdateApp(Gio.Application):

    pmanager = None
    link = None
    had_init = False
    net_mon = None
    notification = None
    first_update = False

    # our gsettings
    settings = None

    # Whether we can check for updates on a metered connection
    update_on_metered = True

    # Corresponds to gsettings key
    check_updates = True

    update_type = UPDATE_TYPE_ALL
    update_freq = UPDATE_FREQ_HOURLY

    # Last unix timestamp
    last_checked = 0

    is_updating = False

    # Track the packages we notified about
    last_state_hash = None

    def __init__(self):
        Gio.Application.__init__(self,
                                 application_id=SC_UPDATE_APP_ID,
                                 flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.connect("activate", self.on_activate)

    def on_activate(self, app):
        """ Initial app activation """
        if self.had_init:
            return
        self.settings = Gio.Settings.new("com.solus-project.software-center")
        self.had_init = True
        Notify.init("Solus Update Service")

        self.settings.connect("changed", self.on_settings_changed)
        self.on_settings_changed("update-type")
        self.on_settings_changed("update-frequency")
        self.on_settings_changed("update-on-metered")
        self.on_settings_changed("last-checked")

        self.net_mon = Gio.NetworkMonitor.get_default()
        self.net_mon.connect("network-changed", self.on_net_changed)
        self.load_comar()

        # if we have networking, begin first check
        if self.is_update_check_required():
            self.first_update = True
            self.begin_background_checks()
        else:
            # No network, show cached results
            self.build_available_updates()

        # Now run a background timer to see if we need to do updates
        GLib.timeout_add_seconds(PONG_FREQUENCY, self.check_update_status)
        # Keep running forever
        self.hold()

    def check_update_status(self):
        # Run us again later
        if self.is_updating:
            return True
        # Check again at a later date
        if not self.is_update_check_required():
            return True

        # Go and check for updates
        self.begin_background_checks()
        return True

    def on_settings_changed(self, key, udata=None):
        """ Settings changed, we may have to "turn ourselves off"""
        if key == "check-updates":
            self.check_updates = self.settings.get_boolean(key)
            self.on_net_changed(self.net_mon)
        elif key == "update-type":
            self.update_type = self.settings.get_enum(key)
        elif key == "update-frequency":
            self.update_freq = self.settings.get_enum(key)
        elif key == "update-on-metered":
            self.update_on_metered = self.settings.get_boolean(key)
        elif key == "last-checked":
            self.last_checked = self.settings.get_value(key).get_int64()

    def on_net_changed(self, mon, udata=None):
        """ Network connection status changed """
        if self.is_update_check_required():
            # Try to do our first refresh now
            if not self.first_update:
                self.first_update = True
                self.begin_background_checks()

    def action_show_updates(self, notification, action, user_data):
        """ Open the updates view """
        command = ["solus-sc", "--update-view"]
        try:
            subprocess.Popen(command)
        except Exception:
            pass
        notification.close()

    def begin_background_checks(self):
        """ Initialise the actual background checks and initial update """
        self.reload_repos()
        pass

    def load_comar(self):
        """ Load the d-bus comar link """
        self.link = comar.Link()
        self.pmanager = self.link.System.Manager['pisi']
        self.link.listenSignals("System.Manager", self.pisi_callback)

    def invalidate_all(self):
        # Forcibly reload the repos if we got this far
        pisi.db.invalidate_caches()
        self.is_updating = False

    def pisi_callback(self, package, signal, args):
        """ Just let us know that things are done """
        if signal == 'finished' or signal is None:
            self.invalidate_all()
            self.build_available_updates()
        elif str(signal).startswith("tr.org.pardus.comar.Comar.PolicyKit") or signal == 'error':
            self.invalidate_all()

    def reload_repos(self):
        """ Actually refresh the repos.. """
        self.is_updating = True
        self.pmanager.updateAllRepositories()

    def can_update(self):
        """ Determine if policy/connection allows checking for updates """
        # No network so we can't do anything anyway
        if not self.check_updates:
            return False
        if not self.net_mon.get_network_available():
            return False
        # Not allowed to update on metered connection ?
        if not self.update_on_metered:
            if self.net_mon.get_network_metered():
                return False
        return True

    def build_available_updates(self):
        """ Check the actual update availability - post refresh """
        self.is_updating = False
        upds = None
        try:
            upds = pisi.api.list_upgradable()
        except:
            return

        self.store_update_time()

        if not upds or len(upds) < 1:
            return

        idb = pisi.db.installdb.InstallDB()
        pdb = pisi.db.packagedb.PackageDB()

        security_ups = []
        mandatory_ups = []

        pkg_hash = hashlib.sha256()
        ssz = ""

        for up in upds:
            # Might be obsolete, skip it
            if not pdb.has_package(up):
                continue
            candidate = pdb.get_package(up)
            old_pkg = None
            ssz += str(candidate.packageHash)
            if idb.has_package(up):
                old_pkg = idb.get_package(up)
            sc = ScUpdateObject(old_pkg, candidate)
            if sc.is_security_update():
                security_ups.append(sc)
            if candidate.partOf == "system.base":
                mandatory_ups.append(sc)

        pkg_hash.update(ssz)
        hx = pkg_hash.hexdigest()

        # If this packageset is identical to the last package set that we
        # notified the user about, don't keep spamming them every single time!
        if hx is not None and hx == self.last_state_hash:
            return

        self.last_state_hash = hx

        # If its security only...
        if self.update_type == UPDATE_TYPE_SECURITY:
            if len(security_ups) < 1:
                return
        elif self.update_type == UPDATE_TYPE_MANDATORY:
            if len(security_ups) < 1 and len(mandatory_ups) < 1:
                return

        # All update types

        if len(security_ups) > 0:
            title = _("Security updates available")
            body = _("Update at your earliest convenience to ensure continued "
                     "security of your device")
            icon_name = "software-update-urgent-symbolic"
        else:
            title = _("Software updates available")
            body = _("New software updates are available for your device")
            icon_name = "software-update-available-symbolic"

        self.notification = Notify.Notification.new(title, body, icon_name)
        self.notification.set_timeout(UPDATE_NOTIF_TIMEOUT)
        self.notification.add_action("open-sc", _("Open Software Center"),
                                     self.action_show_updates, None)
        self.notification.show()

    def store_update_time(self):
        # Store the actual update time
        timestamp = time.time()
        variant = GLib.Variant.new_int64(timestamp)
        self.settings.set_value("last-checked", variant)
        self.last_checked = timestamp

    def is_update_check_required(self):
        """ Determine if an update is required at all"""
        delta = None
        if not self.can_update():
            return False
        if self.update_freq == UPDATE_FREQ_HOURLY:
            delta = UPDATE_DELTA_HOUR
        elif self.update_freq == UPDATE_FREQ_DAILY:
            delta = UPDATE_DELTA_DAILY
        else:
            delta = UPDATE_DELTA_WEEKLY
        next_time = self.last_checked + delta
        cur_time = time.time()
        if next_time < cur_time:
            return True
        return False
