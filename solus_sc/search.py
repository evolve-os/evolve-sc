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

from gi.repository import Gtk, GLib
from .search_results import ScSearchResults
from .details import PackageDetailsView


class ScSearchView(Gtk.Box):
    """ Facilitate searching of the repo """

    flowbox = None
    owner = None
    search_box = None
    search_results = None
    search_button = None
    stack = None
    details_view = None

    def handle_back(self):
        """ Go back to the main view """
        self.stack.set_visible_child_name("search")
        self.owner.set_can_back(False)

    def can_back(self):
        """ Whether we can go back """
        return self.stack.get_visible_child_name() != "search"

    def handle_focus(self):
        if self.stack.get_visible_child_name() != "search":
            return
        GLib.idle_add(self.handle_focus_real)

    def handle_focus_real(self):
        self.search_box.grab_focus()
        return False

    def __init__(self, owner):
        Gtk.EventBox.__init__(self)
        self.owner = owner
        self.stack = Gtk.Stack()
        self.pack_start(self.stack, True, True, 0)
        t = Gtk.StackTransitionType.SLIDE_LEFT_RIGHT
        self.stack.set_transition_type(t)

        vbox = Gtk.Box(Gtk.Orientation.VERTICAL, 0)
        self.stack.add_named(vbox, "search")

        hbox = Gtk.Box(Gtk.Orientation.HORIZONTAL, 0)
        hbox.set_property("margin", 40)
        hbox.get_style_context().add_class("linked")
        vbox.pack_start(hbox, False, False, 0)
        self.search_box = Gtk.SearchEntry()
        self.search_box.grab_focus()
        self.search_box.connect("changed", self.on_changed)
        self.search_box.connect("activate", self.on_clicked)

        self.search_button = Gtk.Button("Search")
        self.search_button.set_can_focus(False)
        self.search_button.connect("clicked", self.on_clicked)
        hbox.pack_start(self.search_box, True, True, 0)
        hbox.pack_end(self.search_button, False, False, 0)
        self.search_button.set_sensitive(False)

        self.search_results = ScSearchResults(self, self.owner)
        vbox.pack_start(self.search_results, True, True, 0)

        self.details_view = PackageDetailsView(self.owner.appsystem,
                                               self.owner.basket)
        self.stack.add_named(self.details_view, "details")

    def on_clicked(self, btn, udata=None):
        txt = self.search_box.get_text().strip()
        self.search_results.set_search_term(txt)

    def on_changed(self, entry, udata=None):
        txt = self.search_box.get_text().strip()

        if txt == "":
            self.search_button.set_sensitive(False)
            self.search_results.clear_view()
        else:
            self.search_button.set_sensitive(True)

    def select_details(self, package):
        if self.owner.basket.installdb.has_package(package.name):
            self.details_view.is_install_page = False
        else:
            self.details_view.is_install_page = True
        self.details_view.update_from_package(package)
        self.stack.set_visible_child_name("details")
        self.owner.set_can_back(True)
