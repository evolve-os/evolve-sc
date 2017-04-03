#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
#  This file is part of solus-sc
#
#  Copyright © 2013-2016 Ikey Doherty <ikey@solus-project.com>
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 2 of the License, or
#  (at your option) any later version.
#


import dbus
import dbus.service
import dbus.glib
from .polkit_helper import PolkitHelper

import pisi.api
import pisi.context
import pisi.config
import pisi.ui
import threading
import os
import os.path
import subprocess
import tempfile
import shutil

BASE_URI = "https://raw.githubusercontent.com/solus-project/3rd-party/master"

APPS = {
    "android-studio":
        "programming/android-studio/pspec.xml",
    "bitwig-studio":
        "multimedia/music/bitwig-studio/pspec.xml",
    "enpass":
        "security/enpass/pspec.xml",
    "flash-player-npapi":
        "multimedia/video/flash-player-npapi/pspec.xml",
    "flash-player-ppapi":
        "multimedia/video/flash-player-ppapi/pspec.xml",
    "gitkraken":
        "programming/gitkraken/pspec.xml",
    "google-chrome-stable":
        "network/web/browser/google-chrome-stable/pspec.xml",
    "google-chrome-beta":
        "network/web/browser/google-chrome-beta/pspec.xml",
    "google-chrome-unstable":
        "network/web/browser/google-chrome-unstable/pspec.xml",
    "google-earth":
        "network/web/google-earth/pspec.xml",
    "idea":
        "programming/idea/pspec.xml",
    "insync":
        "network/download/insync/pspec.xml",
    "mendeleydesktop":
        "office/mendeleydesktop/pspec.xml",
    "moneydance":
        "office/moneydance/pspec.xml",
    "google-talkplugin":
        "network/im/google-talkplugin/pspec.xml",
    "plexmediaserver":
        "multimedia/video/plexmediaserver/pspec.xml",
    "pycharm":
        "programming/pycharm/pspec.xml",
    "rubymine":
        "programming/rubymine/pspec.xml",
    "skype":
        "network/im/skype/pspec.xml",
    "slack-desktop":
        "network/im/slack-desktop/pspec.xml",
    "spotify":
        "multimedia/music/spotify/pspec.xml",
    "sublime-text-3":
        "programming/sublime-text-3/pspec.xml",
    "viber":
        "network/im/viber/pspec.xml",
    "webstorm":
        "programming/webstorm/pspec.xml",
    "wps-office":
        "office/wps-office/pspec.xml",
}


class EopkgUiMonitor(pisi.ui.UI):

    ok = None
    bad = None
    errors = False
    warnings = False
    last_error = None

    def __init__(self, ok, bad):
        self.ok = ok
        self.bad = bad

    def info(self, msg, verbose=False, noln=False):
        self.ok(msg)

    def debug(self, msg):
        self.ok(msg)

    def warning(self, msg):
        self.ok(msg)
        self.warnings = True

    def error(self, msg):
        self.ok(msg)
        self.last_error = msg
        self.errors = True

    def action(self, msg):
        self.ok(msg)

    def display_progress(self, **ka):
        self.ok(str(ka))

    def status(self, msg=None):
        "set status, if not given clear it"
        self.ok(msg)

    def notify(self, event, **keywords):
        "notify UI of a significant event"
        self.ok(event)
        self.ok(str(keywords))


class EopkgAssistService(dbus.service.Object):

    ACTION_BUILD = "com.solus_project.eopkgassist.build"

    def __init__(self, loop):
        bus_name = dbus.service.BusName(
            'com.solus_project.eopkgassist', bus=dbus.SystemBus())
        dbus.service.Object.__init__(self,
                                     bus_name,
                                     '/com/solus_project/EopkgAssist')

        self.dbus_info = None

        self.polkit = PolkitHelper()

        self.pid_map = dict()
        self.loop = loop

        # Weird as it may sound this is a dict of lists.
        self.action_pids = dict()

    ''' Return the process ID for the specified connection '''
    def get_pid_from_connection(self, conn, sender):
        if self.dbus_info is None:
            self.dbus_info = dbus.Interface(
                conn.get_object('org.freedesktop.DBus',
                                '/org/freedesktop/DBus/Bus', False),
                'org.freedesktop.DBus')
        pid = self.dbus_info.GetConnectionUnixProcessID(sender)

        return pid

    """ Register the connection with the associated polkit action """
    def register_connection_with_action(self, conn, sender, action_id):
        pid = self.get_pid_from_connection(conn, sender)

        if sender not in self.pid_map:
            print "Adding new sender: %s" % sender
            self.pid_map[sender] = pid

        if action_id not in self.action_pids:
            self.action_pids[action_id] = list()

        def cb(conn, sender):
            if conn == "":
                pid = None
                try:
                    pid = self.pid_map[sender]
                except:
                    # already removed, called twice.
                    return
                print "Disconnected process: %d" % pid

                self.pid_map.pop(sender)
                count = 0
                for i in self.action_pids[action_id]:
                    if i == pid:
                        self.action_pids[action_id].pop(count)
                        break
                    count += 1
                if len(self.pid_map) == 0:
                    self.ShutDown(None, None)
                del count
        conn.watch_name_owner(sender, lambda x: cb(x, sender))

    """ Check if authorized and cache it """
    def persist_authorized(self, sender, conn, action_id):
        self.register_connection_with_action(conn, sender, action_id)

        pid = self.pid_map[sender]

        if pid not in self.action_pids[action_id]:
            if self.polkit.check_authorization(pid, action_id):
                self.action_pids[action_id].append(pid)
                return True  # Authorized by PolKit!

            else:
                return False  # Unauthorized by PolKit!
        else:
            return True  # Already authorized by PolKit in this session

    def __build_package(self, pkgname2):
        def ok(msg):
            self.Progress(0, msg)

        pkgname = str(pkgname2)
        ui = EopkgUiMonitor(ok, ok)
        pisi.context.ui = ui
        pisi.context.config.values.general.ignore_safety = True
        pisi.context.config.values.build.compressionlevel = 1
        pisi.context.config.values.build.generateDebug = False
        options = pisi.config.Options()
        options.output_dir = tempfile.mkdtemp(suffix='sc')
        pisi.api.set_options(options)

        def dummy():
            pass

        def dummy2():
            return True

        def dummy3():
            return False
        pisi.context.disable_keyboard_interrupts = dummy
        pisi.context.enable_keyboard_interrupts = dummy
        pisi.context.keyboard_interrupt_disabled = dummy2
        pisi.context.keyboard_interrupt_pending = dummy3
        pkg = None

        if pkgname not in APPS:
            ok("ERROR: Unknown package")
            ok("DONE")
            self._do_purge(options.output_dir)
            return

        pkg = str(BASE_URI) + "/" + str(APPS[pkgname])

        # Ruthless I know.
        kids = os.listdir(options.output_dir)
        if len(kids) > 0:
            try:
                os.system("rm -f {}/*.eopkg".format(options.output_dir))
            except Exception as e:
                print(e)

        try:
            pisi.api.build(pkg)
        except Exception, e:
            print e
            ok("ERROR: %s" % e)
            ok("DONE")
            self._do_purge(options.output_dir)
            return
        try:
            cmd = "eopkg install --ignore-safety -y {}/*.eopkg".format(
                options.output_dir)
            subprocess.check_call(cmd, shell=True)
            cmd = "rm -f {}/*.eopkg".format(options.output_dir)
            subprocess.check_call(cmd, shell=True)
        except Exception:
            print e
            ok("ERROR: %s" % e)
            ok("DONE")
            self._do_purge(options.output_dir)
            return
        ok("DONE")
        self._do_purge(options.output_dir)

    def _do_purge(self, d):
        """ Final bit of cleanup.. """
        try:
            shutil.rmtree(d)
        except:
            pass

    ''' Request we build a package... '''
    @dbus.service.method('com.solus_project.eopkgassist',
                         sender_keyword='sender', connection_keyword='conn',
                         async_callbacks=('reply_handler', 'error_handler'),
                         in_signature='s', out_signature='s')
    def BuildPackage(self, pkgname, sender=None, conn=None, reply_handler=None,
                     error_handler=None):
        reply_handler("start")
        if not self.persist_authorized(sender, conn, self.ACTION_BUILD):
            error_handler("Not authorized")
            self.Progress(0, "DONE")
            return
        try:
            sane_name = str(str(pkgname).decode("latin1"))
        except:
            sane_name = str(pkgname)
        t = threading.Thread(target=self.__build_package, args=(sane_name,))
        t.start()

    ''' Shut down this service '''
    @dbus.service.method('com.solus_project.eopkgassist',
                         sender_keyword='sender', connection_keyword='conn')
    def ShutDown(self, sender=None, conn=None):
        print "Shutdown requested"

        # you can't just do a sys.exit(), this causes errors for clients
        self.loop.quit()

    ''' Update info back to client '''
    @dbus.service.signal('com.solus_project.eopkgassist')
    def Progress(self, percent, message):
        return False
