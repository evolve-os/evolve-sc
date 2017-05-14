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
from gi.repository import AppStreamGlib as As
import difflib


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
        # self.spinner.start()
        # "Witty" loading page, loading search results
        lab = _("Concentrating really hard") + u"…"
        self.label = Gtk.Label("<big>{}</big>".format(lab))
        self.label.set_use_markup(True)

        self.pack_start(self.spinner, True, True, 0)
        self.pack_start(self.label, False, False, 0)
        self.label.set_property("margin", 20)


class BlankPage(Gtk.Box):
    """ Simple placeholder page, nothing fancy. """

    label = None

    def __init__(self):
        Gtk.Box.__init__(self, Gtk.Orientation.VERTICAL)

        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        # Search page, prompt to begin searching
        self.label = Gtk.Label("<big>{}</big>".format(
                               _("Type a query to get started")))
        self.label.set_use_markup(True)

        self.pack_start(self.label, False, False, 0)
        self.label.set_property("margin", 20)


class NotFoundPage(Gtk.Box):
    """ Found no search results. """

    label = None

    def __init__(self):
        Gtk.Box.__init__(self, Gtk.Orientation.VERTICAL)

        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        # Unable to find any matching search results
        self.label = Gtk.Label("<big>{}</big>".format(
                               _("No results found")))
        self.label.set_use_markup(True)

        self.pack_start(self.label, False, False, 0)
        self.label.set_property("margin", 20)


class ScSearchResults(Gtk.Box):

    scroll = None
    tview = None
    appsystem = None
    basket = None
    stack = None
    load_page = None
    owner = None
    stack = None
    component = None
    empty_page = None
    notfound_page = None
    search_page = None

    def __init__(self, search_page, owner):
        Gtk.Box.__init__(self, Gtk.Orientation.VERTICAL, 0)
        self.basket = owner.basket
        self.appsystem = owner.appsystem
        self.owner = owner
        self.search_page = search_page

        self.stack = Gtk.Stack()
        t = Gtk.StackTransitionType.SLIDE_LEFT_RIGHT
        self.stack.set_transition_type(t)
        self.pack_start(self.stack, True, True, 0)

        # Not found/ search for somethin pls
        self.empty_page = BlankPage()
        self.stack.add_named(self.empty_page, "empty")

        # Loading results
        self.load_page = LoadingPage()
        self.stack.add_named(self.load_page, "loading")

        # not found
        self.notfound_page = NotFoundPage()
        self.stack.add_named(self.notfound_page, "not-found")

        self.scroll = Gtk.ScrolledWindow(None, None)
        self.scroll.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        self.scroll.set_overlay_scrolling(False)
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_property("kinetic-scrolling", True)
        self.scroll.get_style_context().add_class("search-results")
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

        self.stack.set_visible_child_name("empty")

    def on_row_activated(self, tview, path, column, udata=None):
        """ User clicked a row, now try to load the page """
        model = tview.get_model()
        row = model[path]

        pkg_name = row[INDEX_FIELD_NAME]

        if self.basket.packagedb.has_package(pkg_name):
            pkg = self.basket.packagedb.get_package(pkg_name)
        else:
            pkg = self.basket.installdb.get_package(pkg_name)
        self.search_page.select_details(pkg)

    def set_search_term(self, term):
        if term.strip() == "":
            return
        model = Gtk.ListStore(str, str, GdkPixbuf.Pixbuf, str)

        self.reset()

        try:
            s_packages = set(self.basket.packagedb.search_package([term]))
            s_packages.update(self.basket.installdb.search_package([term]))
        except Exception as e:
            # Invalid regex, basically, from someone smashing FIREFOX????
            print(e)
            self.stack.set_visible_child_name("not-found")
            self.load_page.spinner.stop()
            return

        leaders = difflib.get_close_matches(term.lower(),
                                            s_packages, cutoff=0.5)
        packages = leaders
        packages.extend(sorted([x for x in s_packages if x not in leaders]))
        for pkg_name in packages:
            if self.basket.packagedb.has_package(pkg_name):
                pkg = self.basket.packagedb.get_package(pkg_name)
            else:
                pkg = self.basket.installdb.get_package(pkg_name)

            summary = self.appsystem.get_summary(pkg)
            summary = self.render_plain(str(summary))

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

        if len(packages) == 0:
            self.stack.set_visible_child_name("not-found")
        else:
            self.stack.set_visible_child_name("available")

        self.tview.set_model(model)
        self.load_page.spinner.stop()

    def reset(self):
        self.tview.set_model(None)
        self.stack.set_visible_child_name("loading")
        self.load_page.spinner.start()
        self.queue_draw()

    def clear_view(self):
        self.tview.set_model(None)
        self.stack.set_visible_child_name("empty")
        self.queue_draw()

    def render_plain(self, input_string):
        """ Render a plain version of the description, no markdown """
        plain = As.markup_convert_simple(input_string)
        plain = plain.replace("&quot;", "\"").replace("&apos;", "'")
        return plain
