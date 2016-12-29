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

from gi.repository import Gtk, GObject, GLib

import comar
import pisi.db
import dbus
from pisi.operations.install import plan_install_pkg_names
from pisi.operations.remove import plan_remove
from pisi.operations.upgrade import plan_upgrade
from widgets import PackageLabel


class BasketView(Gtk.Revealer):

    __gsignals__ = {
        'basket-changed': (GObject.SIGNAL_RUN_FIRST, None, (object,)),
        'apply': (GObject.SIGNAL_RUN_FIRST, None,
                          (object,))
    }

    action_bar = None
    doing_things = False
    owner = None
    pulser = -1

    def is_busy(self):
        return self.doing_things

    def __init__(self, owner):
        Gtk.Revealer.__init__(self)
        self.owner = owner

        self.action_bar = Gtk.ActionBar()
        self.add(self.action_bar)
        self.progresslabel = Gtk.Label("")
        self.progresslabel.set_valign(Gtk.Align.CENTER)
        self.progresslabel.set_halign(Gtk.Align.START)
        self.progresslabel.set_property("yalign", 0.5)
        self.progresslabel.set_property("xalign", 0.0)
        self.progresslabel.set_margin_start(6)
        self.progresslabel.set_margin_end(8)
        self.progresslabel.set_margin_top(4)
        self.progresslabel.set_margin_bottom(4)
        self.action_bar.pack_start(self.progresslabel)
        self.progressbar = Gtk.ProgressBar()
        self.progressbar.set_fraction(0.6)
        self.progressbar.set_valign(Gtk.Align.CENTER)

        self.progressbar.set_margin_end(20)
        self.progressbar.set_margin_top(6)
        self.progressbar.set_margin_bottom(4)
        self.action_bar.pack_end(self.progressbar)

        self.progressbar.set_size_request(350, -1)

        self.invalidate_all()

        self.operations = dict()

        self.update_ui()

        self.cb = None
        self.link = comar.Link()
        self.pmanager = self.link.System.Manager['pisi']
        self.link.listenSignals("System.Manager", self.pisi_callback)

        self.current_operations = None

        self.downloaded = 0
        self.current_package = None

    def build_package(self, nom):
        """ Ugly ass shit needed to get third party packages working for now.
            Note to self: Find more elegant solution.. """
        bus = dbus.SystemBus()
        obj = bus.get_object("com.solus_project.eopkgassist",
                             "/com/solus_project/EopkgAssist")
        iface = dbus.Interface(obj, "com.solus_project.eopkgassist")
        iface.connect_to_signal("Progress", self.do_prog)
        self.doing_things = True
        self.operations['::third-party::'] = 'Install {}'.format(nom)
        self.update_ui()
        self.emit('basket-changed', None)
        self.pulser = GLib.timeout_add(1000.0 / 5.0, self.step_up)
        iface.BuildPackage(nom,
                           reply_handler=self.on_eopkg_repl,
                           error_handler=self.on_eopkg_err)

    def step_up(self):
        self.progressbar.pulse()
        return True

    def on_eopkg_repl(self, o):
        pass

    def on_eopkg_err(self, o):
        print("dbus error, shouldnt happen: {}".format(str(o)))
        self.invalidate_all()

    def do_prog(self, pct, message):
        if str(message).startswith("ERROR: "):
            content = message.split("ERROR: ")[1:]
            d = Gtk.MessageDialog(self.owner,
                                  Gtk.DialogFlags.DESTROY_WITH_PARENT |
                                  Gtk.DialogFlags.MODAL,
                                  Gtk.MessageType.ERROR, Gtk.ButtonsType.CLOSE,
                                  content)
            d.run()
            d.destroy()
            self.doing_things = False
            self.invalidate_all()
            self.update_ui()

        if pct == 0 and message == "DONE":
            self.doing_things = False
            self.invalidate_all()
            self.update_ui()

    def set_progress(self, fraction, label):
        if fraction is None:
            # Hide
            self.set_reveal_child(False)
            self.update_ui()
            return
        # print "%s %f" % (label, fraction)
        self.progresslabel.set_markup(label)
        self.set_reveal_child(True)
        self.progressbar.set_fraction(fraction)

    def update_ui(self):
        count = self.operation_count()
        if count == 0:
            self.set_reveal_child(False)
            return
        if count > 1:
            # The number (more than one) of package operations to be performed
            self.progresslabel.set_markup(_("{} operations pending").format(
                self.operation_count()))
        else:
            if '::third-party::' in self.operations:
                lab = " - This may take <b>some time!</b>"
                self.progresslabel.set_markup(
                    self.operations['::third-party::'] + lab)
            else:
                # Only one package operation to be performed
                self.progresslabel.set_markup(_("One operation pending"))
        self.set_reveal_child(True)

    def operation_for_package(self, package):
        if package.name in self.operations:
            return self.operations[package.name]
        return None

    def operation_count(self):
        return len(self.operations)

    def operation_count_type(self, type):
        return len([x for x in self.operations if self.operations[x] == type])

    def forget_package(self, package):
        if package.name in self.operations:
            self.operations.pop(package.name, None)
        self.update_ui()

    def remove_package(self, old_package):
        self.operations[old_package.name] = 'UNINSTALL'
        self.update_ui()

    def install_package(self, new_package):
        self.operations[new_package.name] = 'INSTALL'
        self.update_ui()

    def update_package(self, old_package, new_package):
        self.operations[new_package.name] = 'UPDATE'
        self.update_ui()

    def _get_prog(self, step):
        self.progress_current = step
        total = float(self.progress_total)
        current = float(self.progress_current)

        fract = float(current/total)
        return fract

    def pisi_callback(self, package, signal, args):
        if signal == 'status':
            cmd = args[0]
            what = args[1]
            if cmd == 'updatingrepo':
                # "Updating Solus repository" (named repo)
                self.set_progress(1.0, _("Updating %s repository") % what)
            elif cmd == 'extracting':
                prog = self._get_prog(self.progress_current + self.step_offset)
                # "Extracting 1 of 10: bash"
                msg = _("Extracting {} of {}: {}").format(
                    self.current_package, self.total_packages, what)
                self.set_progress(prog, msg)
            elif cmd == 'configuring':
                prog = self._get_prog(self.progress_current + self.step_offset)
                # "Configuring 1 of 10: bash"
                msg = _("Configuring {} of {}: {}").format(
                    self.current_package, self.total_packages, what)
                self.set_progress(prog, msg)
            elif cmd in ['removing', 'installing']:
                prog = self._get_prog(self.progress_current + self.step_offset)
                # "Installing 1 of 10: bash"
                lab = _("Installing {} of {}: {}")
                if cmd == 'removing':
                    # "Removing (1 of 10): bash"
                    lab = _("Removing {} of {}: {}")
                # "1 of 10"
                ffmt = lab.format(self.current_package, self.total_packages,
                                  what)
                self.set_progress(prog, ffmt)
            elif cmd in ['upgraded', 'installed', 'removed']:
                prog = self._get_prog(self.progress_current + self.step_offset)
                if cmd == 'upgraded':
                    # "Upgraded 1 of 10: bash"
                    lab = _("Upgraded {} of {}: {}")
                elif cmd == 'removed':
                    # "Removed 1 of 10: bash"
                    lab = _("Removed {} of {}: {}")
                elif cmd == 'installed':
                    # "Installed 1 of 10: bash"
                    lab = _("Removed {} of {}: {}")
                ffmt = lab.format(self.current_package, self.total_packages,
                                  what)
                self.set_progress(prog, ffmt)
                self.current_package += 1

        if signal == 'progress':
            cmd = args[0]
            if cmd == 'fetching':
                if self.current_operations is not None:
                    # Doing real operations now.
                    package = args[1]
                    # whatisthis = args[2]
                    speed_number = args[3]
                    speed_label = args[4]
                    downloaded = args[5]
                    download_size = args[6]
                    # down = downloaded
                    speed = "%d %s" % (speed_number, speed_label)

                    diff = downloaded - download_size
                    inc = self.total_size + diff
                    prog = self._get_prog(inc)

                    cd = self.current_dl_package
                    if cd == 0 and self.total_packages == 0:
                        self.set_progress(prog, "Downloading {} ({})".format(
                            package, speed))
                    else:
                        disp = "Downloading {} of {}: {} ({})"
                        self.set_progress(prog, disp.format(
                            self.current_dl_package,
                            self.total_packages, package, speed))

                    if downloaded >= download_size:
                        self.current_dl_package += 1
                else:
                    # print args
                    self.set_progress(1.0, "Downloading %s" % args[1])
        elif signal == 'finished' or signal is None:
            if self.cb is not None:
                self.cb()
            self.cb = None
            self.set_progress(None, None)
            self.update_ui()
            return
        elif str(signal).startswith("tr.org.pardus.comar.Comar.PolicyKit"):
            if self.cb is not None:
                self.cb()
            self.cb = None
            self.set_progress(None, None)
            self.update_ui()
            return

    def update_repo(self, cb=None):
        self.cb = cb
        self.pmanager.updateAllRepositories()

    def get_sizes(self, packages):
        totalSize = 0
        packages = [self.packagedb.get_package(pkg) for pkg in packages]
        for package in packages:
            totalSize += package.packageSize
        return totalSize

    def invalidate_all(self):
        # Handle operations that finished.
        if self.pulser >= 0:
            GLib.source_remove(self.pulser)
            self.pulser = -1
        self.operations = dict()
        pisi.db.invalidate_caches()
        self.installdb = pisi.db.installdb.InstallDB()
        self.packagedb = pisi.db.packagedb.PackageDB()
        self.componentdb = pisi.db.componentdb.ComponentDB()
        self.groupdb = pisi.db.groupdb.GroupDB()
        self.doing_things = False
        self.current_dl_package = 0
        self.total_packages = 0
        self.emit('basket-changed', None)

    def show_dialog(self, pkgs, remove=False, update=False, install=True):
        markup = "<big>{}</big>".format(
            _("The following dependencies need to be installed to continue"))

        flags = Gtk.DialogFlags.MODAL | Gtk.DialogFlags.USE_HEADER_BAR
        dlg = Gtk.MessageDialog(self.owner,
                                flags,
                                Gtk.MessageType.QUESTION,
                                Gtk.ButtonsType.OK_CANCEL)

        dlg = Gtk.Dialog(use_header_bar=1)
        dlg.set_transient_for(self.owner)
        dlg.set_title(_("Installation confirmation"))
        if remove:
            markup = "<big>{}</big>".format(
                _("The following dependencies need to be removed to continue"))
            dlg.set_title(_("Removal confirmation"))
        elif update:
            markup = "<big>{}</big>".format(
                _("The following dependencies need to be updated to continue"))
            dlg.set_title(_("Update confirmation"))

        lab = Gtk.Label(markup)
        lab.set_use_markup(True)
        box = Gtk.Box(Gtk.Orientation.HORIZONTAL, 0)
        box.set_property("margin", 5)
        box.pack_start(lab, True, True, 0)
        dlg.get_content_area().pack_start(box, False, False, 0)
        dlg.get_content_area().set_border_width(5)
        dlg.get_action_area().set_border_width(5)

        scroll = Gtk.ScrolledWindow(None, None)
        lbox = Gtk.ListBox()
        scroll.add(lbox)
        scroll.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        scroll.set_property("margin", 5)

        for pkg in pkgs:
            if remove:
                package = self.installdb.get_package(pkg)
            else:
                package = self.packagedb.get_package(pkg)
            panel = PackageLabel(package, None, interactive=False)
            lbox.add(panel)
        dlg.get_content_area().pack_start(scroll, True, True, 0)
        dlg.get_content_area().show_all()

        btn = dlg.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        if not remove:
            action = _("Install")
            if not install:
                action = _("Update")

            btn = dlg.add_button(action, Gtk.ResponseType.OK)
            btn.get_style_context().add_class("suggested-action")
        else:
            btn = dlg.add_button(_("Remove"), Gtk.ResponseType.OK)
            btn.get_style_context().add_class("destructive-action")
        dlg.set_default_size(250, 400)
        res = dlg.run()
        dlg.destroy()
        if res == Gtk.ResponseType.OK:
            return True
        return False

    def apply_operations(self):
        self.doing_things = True
        updates = [
            i for i in self.operations if self.operations[i] == 'UPDATE'
        ]
        installs = [
            i for i in self.operations if self.operations[i] == 'INSTALL'
        ]
        removals = [
            i for i in self.operations if self.operations[i] == 'UNINSTALL'
        ]

        # We monitor 4 post events
        STEPS = 4

        self.installdb = pisi.db.installdb.InstallDB()
        self.packagedb = pisi.db.packagedb.PackageDB()

        self.emit('basket-changed', None)
        # print "%d packages updated" % len(updates)
        # print "%d packages installed" % len(installs)
        # print "%d packages removed" % len(removals)

        setAct = False

        for packageset in [updates, installs, removals]:
            if len(packageset) == 0:
                continue

            self.current_package = 1
            self.current_dl_package = 1

            if packageset == installs:
                (pg, pkgs) = plan_install_pkg_names(packageset)
                if len(pkgs) > len(packageset):
                    p = [x for x in pkgs if x not in packageset]
                    if self.show_dialog(p):
                        installs = packageset = pkgs
                    else:
                        # print "Not installing"
                        continue
            elif packageset == removals:
                (pk, pkgs) = plan_remove(packageset)
                if len(pkgs) > len(packageset):
                    p = [x for x in pkgs if x not in packageset]
                    if self.show_dialog(p, remove=True):
                        removals = packageset = pkgs
                    else:
                        # print "Not removing"
                        continue
            elif packageset == updates:
                (pk, pkgs) = plan_upgrade(packageset)
                if len(pkgs) > len(packageset):
                    p = [x for x in pkgs if x not in packageset]
                    if self.show_dialog(p, update=True):
                        updates = packageset = pkgs
                    else:
                        # print Not continuing
                        continue
            self.total_packages = len(packageset)
            setAct = True

            if packageset != removals:
                self.total_size = self.get_sizes(packageset)
                # one tenth of progress is post install
                self.step_offset = self.total_size / 10
                self.progress_total = self.total_size + \
                    ((self.step_offset * self.total_packages) * STEPS)
            else:
                self.total_size = self.total_packages * (STEPS / 2)
                self.step_offset = 1
                self.progress_total = self.total_size
            self.progress_current = 0

            self.current_operations = packageset

            self.cb = self.invalidate_all
            if packageset == updates:
                self.pmanager.updatePackage(
                    ",".join(packageset), async=self.pisi_callback)
            elif packageset == installs:
                self.pmanager.installPackage(
                    ",".join(packageset), async=self.pisi_callback)
            elif packageset == removals:
                self.pmanager.removePackage(
                    ",".join(packageset), async=self.pisi_callback)
        if not setAct:
            self.invalidate_all()
            self.update_ui()
