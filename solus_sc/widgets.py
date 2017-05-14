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

from gi.repository import Gtk, GObject

GENERIC = "package-x-generic"
UPDATE_ICON = "package-upgrade"
REMOVE_ICON = "package-remove"
INSTALL_ICON = "package-install"

INSTALLED_ICON = "emblem-ok-symbolic"
OLD_ICON = "emblem-important-symbolic"
AVAILABLE_ICON = "list-add-symbolic"


def do_justif(label):
    label.set_alignment(0.0, 0.5)
    label.set_justify(Gtk.Justification.LEFT)


class PackageLabel(Gtk.Box):

    __gsignals__ = {
        'operation-selected': (GObject.SIGNAL_RUN_FIRST, None,
                               (str, object, object))
    }

    def make_valid(self, istr):
        ret = istr.replace("&", "&amp;").replace("\"", "&quot;")
        return ret

    def __init__(self, pkg, old_pkg, interactive=False):
        Gtk.Box.__init__(self, Gtk.Orientation.VERTICAL)

        self.set_border_width(4)
        self.header = Gtk.Box(Gtk.Orientation.HORIZONTAL)
        self.image = Gtk.Image()
        if pkg.icon is not None:
            self.image.set_from_icon_name(pkg.icon, Gtk.IconSize.DIALOG)
        else:
            self.image.set_from_icon_name(GENERIC, Gtk.IconSize.DIALOG)

        self.header.pack_start(self.image, False, False, 5)
        self.label_title = Gtk.Label(
            "<b>%s</b> - <small>%s</small>\n%s" %
            (pkg.name, pkg.version, self.make_valid(str(pkg.summary))))
        self.label_title.set_use_markup(True)
        do_justif(self.label_title)
        self.label_title.set_line_wrap(True)
        self.header.pack_start(self.label_title, False, False, 0)

        self.package_status = 'FORGET'
        self.image_status = Gtk.Image()
        if interactive:
            btn = Gtk.Button()
            btn.add(self.image_status)
            btn.set_relief(Gtk.ReliefStyle.NONE)
            btn.connect("clicked", self.interactive_handler)
            btn.set_valign(Gtk.Align.CENTER)
            self.header.pack_end(btn, False, False, 0)
        else:
            self.header.pack_end(self.image_status, False, False, 0)

        self.package = pkg
        self.old_package = old_pkg

        self.pack_start(self.header, True, True, 0)

    def interactive_handler(self, btn, data=None):
        status = self.package_status
        self.package_status = 'FORGET'
        self.mark_status(status)
        self.emit('operation-selected', status, self.package, self.old_package)

    def mark_status(self, status):
        if status == 'INSTALL':
            self.image_status.set_from_icon_name(
                INSTALL_ICON, Gtk.IconSize.SMALL_TOOLBAR)
        elif status == 'UNINSTALL':
            self.image_status.set_from_icon_name(
                REMOVE_ICON, Gtk.IconSize.SMALL_TOOLBAR)
        elif status == 'UPDATE':
            self.image_status.set_from_icon_name(
                UPDATE_ICON, Gtk.IconSize.SMALL_TOOLBAR)
        elif status is None or status == 'FORGET':
            self.reset_image()
        self.status = status

    def reset_image(self):
        if self.old_package is not None:
            new_version = int(self.package.release)
            old_version = int(self.old_package.release)

            if new_version > old_version:
                self.image_status.set_from_icon_name(
                    OLD_ICON, Gtk.IconSize.SMALL_TOOLBAR)
                self.package_status = 'UPDATE'
            else:
                self.image_status.set_from_icon_name(
                    INSTALLED_ICON, Gtk.IconSize.SMALL_TOOLBAR)
                self.package_status = 'UNINSTALL'
        else:
            self.image_status.set_from_icon_name(AVAILABLE_ICON,
                                                 Gtk.IconSize.SMALL_TOOLBAR)
            self.package_status = 'INSTALL'
