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

from gi.repository import Gtk, GLib, GdkPixbuf


""" enum for the model fields """
INDEX_FIELD_DISPLAY = 0
INDEX_FIELD_NAME = 1
INDEX_FIELD_ICON = 2
INDEX_FIELD_ARROW = 3


class LoadingPage(Gtk.Box):
    """ Simple loading page, nothing fancy. """

    spinner = None

    def __init__(self):
        Gtk.Box.__init__(self, Gtk.Orientation.VERTICAL)

        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(-1, 64)
        self.spinner.start()
        # Quirky loading message
        lab = _("Switching to the B-side of the cassette" + u"…")
        self.label = Gtk.Label("<big>{}</big>".format(lab))
        self.label.set_use_markup(True)

        self.pack_start(self.spinner, True, True, 0)
        self.pack_start(self.label, False, False, 0)
        self.label.set_property("margin", 20)


class ScAvailableView(Gtk.Box):

    scroll = None
    tview = None
    appsystem = None
    basket = None
    stack = None
    load_page = None
    owner = None
    groups_view = None
    stack = None
    component = None

    def __init__(self, groups_view, owner):
        Gtk.Box.__init__(self, Gtk.Orientation.VERTICAL, 0)
        self.basket = owner.basket
        self.appsystem = owner.appsystem
        self.owner = owner
        self.groups_view = groups_view

        self.stack = Gtk.Stack()
        t = Gtk.StackTransitionType.SLIDE_LEFT_RIGHT
        self.stack.set_transition_type(t)
        self.pack_start(self.stack, True, True, 0)

        self.load_page = LoadingPage()
        self.stack.add_named(self.load_page, "loading")

        self.scroll = Gtk.ScrolledWindow(None, None)
        self.scroll.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        self.scroll.set_overlay_scrolling(False)
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_property("kinetic-scrolling", True)
        self.stack.add_named(self.scroll, "available")

        # Main treeview where it's all happening. Single click activate
        self.tview = Gtk.TreeView()
        self.tview.get_selection().set_mode(Gtk.SelectionMode.SINGLE)
        self.tview.connect_after('row-activated', self.on_row_activated)
        self.tview.set_activate_on_single_click(True)

        # Defugly
        self.tview.set_property("enable-grid-lines", False)
        self.tview.set_property("headers-visible", False)
        self.scroll.add(self.tview)

        # img view
        ren = Gtk.CellRendererPixbuf()
        ren.set_property("stock-size", Gtk.IconSize.DIALOG)
        ren.set_padding(5, 2)
        column = Gtk.TreeViewColumn("Icon", ren, pixbuf=2)
        self.tview.append_column(column)

        # Set up display columns
        ren = Gtk.CellRendererText()
        ren.set_padding(5, 5)
        column = Gtk.TreeViewColumn("Name", ren, markup=0)
        self.tview.append_column(column)
        self.tview.set_search_column(1)

        # Details
        ren = Gtk.CellRendererPixbuf()
        ren.set_padding(5, 5)
        column = Gtk.TreeViewColumn("Details", ren, icon_name=3)
        self.tview.append_column(column)
        ren.set_property("xalign", 1.0)

    def on_row_activated(self, tview, path, column, udata=None):
        """ User clicked a row, now try to load the page """
        model = tview.get_model()
        row = model[path]

        pkg_name = row[INDEX_FIELD_NAME]

        pkg = self.basket.packagedb.get_package(pkg_name)
        self.groups_view.select_details(pkg)

    def set_component(self, component):
        if self.component and self.component == component:
            return
        self.component = component
        model = Gtk.ListStore(str, str, GdkPixbuf.Pixbuf, str)
        model.set_sort_column_id(1, Gtk.SortType.ASCENDING)

        packages = self.basket.componentdb.get_packages(component.name)

        # Take consideration
        if len(packages) >= 40:
            self.reset()

        for pkg_name in packages:
            pkg = self.basket.packagedb.get_package(pkg_name)

            summary = self.appsystem.get_summary(pkg)
            summary = str(summary)
            if len(summary) > 76:
                summary = "%s…" % summary[0:76]

            summary = GLib.markup_escape_text(summary)

            name = str(pkg.name)
            p_print = "<b>%s</b> - %s\n%s" % (name, str(pkg.version),
                                              summary)

            pbuf = self.appsystem.get_pixbuf_only(pkg)

            model.append([p_print, pkg_name, pbuf, "go-next-symbolic"])

            while (Gtk.events_pending()):
                Gtk.main_iteration()

        self.tview.set_model(model)
        self.stack.set_visible_child_name("available")
        self.load_page.spinner.stop()

    def reset(self):
        self.tview.set_model(None)
        self.stack.set_visible_child_name("loading")
        self.load_page.spinner.start()
        self.queue_draw()
