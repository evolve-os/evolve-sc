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

from gi.repository import Gtk, GLib, GObject, Pango, GdkPixbuf, Gdk
from .util import sc_format_size_local
from . import join_resource_path
from operator import attrgetter
import threading

import pisi.api
import re


PACKAGE_ICON_SECURITY = "security-high-symbolic"
PACKAGE_ICON_NORMAL = "software-update-available-symbolic"
PACKAGE_ICON_MANDATORY = "software-update-urgent-symbolic"

# Helpful for determing CVE matches.
CVE_HIT = re.compile(r".*(CVE\-[0-9]+\-[0-9]+).*")
CVE_URI = "https://cve.mitre.org/cgi-bin/cvename.cgi?name={}"


class ScChangelogEntry(Gtk.EventBox):

    def markup_le_cves(self, text):
        ret = ""

        # Stop multiline run-ins
        for r in text.split("\n"):
            r = r.strip()
            for i in r.split(" "):
                if not CVE_HIT.match(i.upper()):
                    ret += i + " "
                    continue
                i = i.upper()
                href = "<a href=\"{}\">{}</a>".format(CVE_URI.format(i), i)
                ret += href + " "
            ret += "\n"
        return ret.strip()

    def __init__(self, obj, history):
        Gtk.EventBox.__init__(self)

        hbox = Gtk.Box(Gtk.Orientation.VERTICAL, 0)
        self.add(hbox)

        # format name to correlate with git entry.
        nom = "%s-%s-%s" % (str(obj.name),
                            str(history.version),
                            str(history.release))

        text = GLib.markup_escape_text(str(history.comment))

        iname = PACKAGE_ICON_NORMAL
        up_type = str(history.type).lower()
        if up_type == "security":
            iname = PACKAGE_ICON_SECURITY
        image = Gtk.Image.new_from_icon_name(iname, Gtk.IconSize.LARGE_TOOLBAR)
        image.set_valign(Gtk.Align.START)

        hbox.pack_start(image, False, False, 0)
        image.set_property("margin", 4)

        main_lab = Gtk.Label("<b>%s</b>" % nom)
        main_lab.set_use_markup(True)

        vbox = Gtk.Box(Gtk.Orientation.VERTICAL, 0)
        vbox.set_valign(Gtk.Align.START)
        hbox.pack_start(vbox, True, True, 0)

        main_lab.set_halign(Gtk.Align.START)
        main_lab.set_valign(Gtk.Align.START)
        main_lab.set_property("xalign", 0.0)
        main_lab.set_property("margin", 4)

        vbox.pack_start(main_lab, False, False, 0)

        # Add the summary, etc.
        sum_lab = Gtk.Label(self.markup_le_cves(text))
        sum_lab.set_halign(Gtk.Align.START)
        sum_lab.set_valign(Gtk.Align.START)
        sum_lab.set_property("margin-start", 4)
        sum_lab.set_property("margin-end", 4)
        sum_lab.set_property("margin-bottom", 4)
        sum_lab.set_use_markup(True)
        sum_lab.set_line_wrap_mode(Pango.WrapMode.WORD)
        sum_lab.set_line_wrap(True)
        sum_lab.set_property("xalign", 0.0)
        sum_lab.set_max_width_chars(85)
        sum_lab.set_width_chars(80)
        vbox.pack_start(sum_lab, True, True, 0)

        # Timestamp is kinda useful.
        tstamp = Gtk.Label(str(history.date))
        tstamp.set_valign(Gtk.Align.START)
        hbox.pack_end(tstamp, False, False, 0)
        tstamp.set_property("margin", 4)
        tstamp.get_style_context().add_class("dim-label")

        self.show_all()


class ScChangelogViewer(Gtk.Dialog):
    """ Show an overview of changes for a given update """

    def __init__(self, parent, obj):
        Gtk.Dialog.__init__(self, use_header_bar=1)
        self.set_default_size(550, 450)
        self.set_transient_for(parent)
        # Title of dialog displaying the details of a given update
        self.set_title(_("Update Details"))

        builder = Gtk.Builder()
        our_file = join_resource_path("update_dialog.ui")
        builder.add_from_file(our_file)

        main_ui = builder.get_object("grid1")
        main_ui.get_parent().remove(main_ui)
        self.get_content_area().add(main_ui)

        # Display name
        pkgName = str(obj.new_pkg.name)
        builder.get_object("label_name").set_text(pkgName)

        iVersion = "<i>{}</i>".format(_("Not installed"))
        if obj.old_pkg:
            iVersion = "%s-%s" % (str(obj.old_pkg.version),
                                  str(obj.old_pkg.release))
        builder.get_object("label_iversion").set_markup(iVersion)
        aVersion = "%s-%s" % (str(obj.new_pkg.version),
                              str(obj.new_pkg.release))
        builder.get_object("label_aversion").set_markup(aVersion)

        isize = sc_format_size_local(obj.get_update_size(), True)
        builder.get_object("label_upsize").set_text(isize)

        # Handle the changelog
        oldRelease = int(obj.new_pkg.release) - 1
        if obj.old_pkg:
            oldRelease = int(obj.old_pkg.release)

        changes = obj.get_history_between(oldRelease, obj.new_pkg)

        for change in changes:
            item = ScChangelogEntry(obj.new_pkg, change)
            builder.get_object("listbox_changes").add(item)
            item.get_parent().set_property("margin", 5)


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

    def get_update_size(self):
        """ Determine the update size for a given package """
        # FIXME: Check pisi config
        deltasEnabled = True

        pkgSize = self.new_pkg.packageSize
        if not deltasEnabled:
            return pkgSize
        if not self.old_pkg:
            return pkgSize
        delt = self.new_pkg.get_delta(int(self.old_pkg.release))
        """ No delta available. """
        if not delt:
            return pkgSize
        return delt.packageSize

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
        # "Witty" loading message. Refreshing update list
        self.label = Gtk.Label(u"<big>{}…</big>".format(
            _("Discombobulating update matrix")))
        self.label.set_use_markup(True)

        self.pack_start(self.spinner, True, True, 0)
        self.pack_start(self.label, False, False, 0)
        self.label.set_property("margin", 20)


class UpdatingPage(Gtk.Box):
    """ Simple loading page, nothing fancy. """

    spinner = None

    def __init__(self):
        Gtk.Box.__init__(self, Gtk.Orientation.VERTICAL)

        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(-1, 64)
        self.spinner.start()
        # Currently applying updates
        self.label = Gtk.Label("<big>{}…</big>".format(
            _("Please check back later, updates are now applying")))
        self.label.set_use_markup(True)

        self.pack_start(self.spinner, True, True, 0)
        self.pack_start(self.label, False, False, 0)
        self.label.set_property("margin", 20)


class ScUpdatesView(Gtk.Box):

    installdb = None
    packagedb = None
    tview = None

    toolbar = None
    selection_label = None
    view_details = None
    update_btn = None

    selected_object = None

    stack = None
    load_page = None
    basket = None
    appsystem = None
    updating_page = None
    is_updating = False

    def perform_refresh(self, btn, wdata=None):
        self.perform_refresh_internal()

    def external_refresh(self):
        self.perform_refresh_internal()
        return False

    def perform_refresh_internal(self):
        self.view_details.set_sensitive(False)
        self.load_page.spinner.start()
        self.stack.set_visible_child_name("loading")

        t = threading.Thread(target=self.refresh_repos)
        t.daemon = True
        t.start()
        return False

    def refresh_repos(self):
        self.basket.update_repo(cb=lambda: self.load_updates())
        return False

    def load_updates(self):
        self.basket.invalidate_all()
        GObject.idle_add(self.init_view)

    def __init__(self, basket, appsystem):
        Gtk.Box.__init__(self, Gtk.Orientation.VERTICAL, 0)
        self.basket = basket
        self.appsystem = appsystem
        self.basket.connect("basket-changed", self.on_basket_changed)

        self.stack = Gtk.Stack()
        t = Gtk.StackTransitionType.CROSSFADE
        self.stack.set_transition_type(t)
        self.pack_start(self.stack, True, True, 0)

        self.load_page = LoadingPage()
        self.stack.add_named(self.load_page, "loading")

        main_box = Gtk.Box(Gtk.Orientation.VERTICAL, 0)
        self.stack.add_named(main_box, "updates")

        # Our update checkerer
        update_box = Gtk.Box(Gtk.Orientation.VERTICAL, 0)
        # Main toolbar
        toolbar = Gtk.Toolbar()
        sep = Gtk.SeparatorToolItem()
        sep.set_draw(False)
        sep.set_expand(True)
        toolbar.add(sep)
        toolbar.get_style_context().add_class("inline-toolbar")
        toolbar.set_icon_size(Gtk.IconSize.SMALL_TOOLBAR)
        update_box.pack_start(toolbar, False, False, 0)

        refresh_button = Gtk.ToolButton(None, _("Check for updates"))
        refresh_button.set_is_important(True)
        refresh_button.set_label(_("Check for updates"))
        refresh_button.connect("clicked", self.perform_refresh)
        toolbar.add(refresh_button)

        self.stack.add_named(update_box, "check")
        updatec = Gtk.Box(Gtk.Orientation.VERTICAL, 0)
        update_box.pack_start(updatec, True, True, 0)
        updatec.set_halign(Gtk.Align.CENTER)
        updatec.set_valign(Gtk.Align.CENTER)
        img = Gtk.Image.new_from_icon_name("emblem-ok-symbolic",
                                           Gtk.IconSize.DIALOG)
        img.set_pixel_size(96)
        updatec.pack_start(img, False, False, 0)
        lab = Gtk.Label("<big>{}</big>".format(_("Software is up to date")))
        lab.set_use_markup(True)
        updatec.pack_start(lab, False, False, 0)
        lab.set_property("margin", 20)

        self.scroll = Gtk.ScrolledWindow(None, None)
        self.scroll.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        self.scroll.set_overlay_scrolling(False)
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_property("kinetic-scrolling", True)
        self.scroll.get_style_context().add_class("updates-view")

        self.tview = Gtk.TreeView()
        self.tview.get_selection().set_mode(Gtk.SelectionMode.SINGLE)
        self.scroll.add(self.tview)
        self.tview.set_property("enable-grid-lines", False)
        self.tview.set_property("headers-visible", False)
        self.tview.set_activate_on_single_click(True)
        self.tview.connect_after('row-activated', self.on_row_activated)

        # Can toggle?
        ren = Gtk.CellRendererToggle()
        ren.set_activatable(True)
        ren.connect('toggled', self.on_toggled)
        ren.set_padding(5, 5)
        ren.set_property("xalign", 1.0)
        column = Gtk.TreeViewColumn("Install?", ren, active=0,
                                    activatable=1, sensitive=5)
        self.tview.append_column(column)

        ren = Gtk.CellRendererPixbuf()
        ren.set_padding(5, 5)
        column = Gtk.TreeViewColumn("Type", ren, pixbuf=4, sensitive=5)
        self.tview.append_column(column)
        ren.set_property("stock-size", Gtk.IconSize.DIALOG)

        # Label of top row
        text_ren = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Label", text_ren, markup=2, sensitive=5)
        text_ren.set_padding(5, 5)
        self.tview.append_column(column)

        # Update size
        text_ren = Gtk.CellRendererText()
        text_ren.set_property("xalign", 1.0)
        column = Gtk.TreeViewColumn("Size", text_ren, text=3, sensitive=5)
        self.tview.append_column(column)

        # Main toolbar
        self.toolbar = Gtk.Toolbar()
        self.toolbar.set_icon_size(Gtk.IconSize.SMALL_TOOLBAR)
        st = self.toolbar.get_style_context()
        # st.add_class(Gtk.STYLE_CLASS_INLINE_TOOLBAR)
        st.add_class("update-toolbar")

        # Pack widgets
        main_box.pack_start(self.toolbar, False, False, 0)
        main_box.pack_start(self.scroll, True, True, 0)
        # Junctions
        st = self.scroll.get_style_context()
        st.set_junction_sides(Gtk.JunctionSides.TOP)
        st = self.toolbar.get_style_context()
        st.set_junction_sides(Gtk.JunctionSides.BOTTOM)

        # Selection label
        # No updates currently selected for installation
        self.selection_label = Gtk.Label(_("0 items selected"))
        titem = Gtk.ToolItem()
        titem.set_property("margin-start", 6)
        titem.add(self.selection_label)
        self.toolbar.add(titem)

        # Right align the toolbar
        sep = Gtk.SeparatorToolItem()
        sep.set_draw(False)
        sep.set_expand(True)
        self.toolbar.add(sep)

        refresh_button = Gtk.ToolButton(None, None)
        refresh_button.set_icon_name("view-refresh-symbolic")
        refresh_button.set_tooltip_text(_("Check new updates"))
        refresh_button.set_label(_("Check for updates"))
        refresh_button.connect("clicked", self.perform_refresh)
        self.toolbar.add(refresh_button)

        # View details, i.e. changelog
        self.view_details = Gtk.ToolButton(None, None)
        self.view_details.set_icon_name("dialog-information-symbolic")
        self.view_details.set_sensitive(False)
        self.view_details.set_tooltip_text(u"{}…".format(_("Details")))
        self.view_details.get_style_context().add_class("flat")
        self.view_details.connect("clicked", self.on_details)
        self.toolbar.add(self.view_details)

        # Apply the updates
        self.update_btn = Gtk.ToolButton(None, _("Update Selected"))
        self.update_btn.set_label(_("Update Selected"))
        self.update_btn.set_is_important(True)
        self.update_btn.connect("clicked", self.on_update)
        self.toolbar.add(self.update_btn)
        self.update_btn.set_sensitive(0)

        self.updating_page = UpdatingPage()
        self.stack.add_named(self.updating_page, "updating")

    def on_basket_changed(self, basket, udata=None):
        """ Just applied updates, so lets refresh repos and update list """
        if not self.is_updating:
            return
        if basket.is_busy():
            return
        self.is_updating = False
        self.updating_page.spinner.stop()
        GLib.idle_add(self.refresh_repos)

    def on_update(self, b, wdata=None):
        """ Actually go ahead and do the update """
        model = self.tview.get_model()
        # root row can be skipped in each instance
        for row in model:
            for sprog in row.iterchildren():
                checked = sprog[0]
                obj = sprog[-1]
                if not checked:
                    continue
                self.basket.update_package(obj.old_pkg, obj.new_pkg)
        # Move to the updating page
        self.stack.set_visible_child_name("updating")
        self.updating_page.spinner.start()
        self.is_updating = True
        self.queue_draw()
        self.basket.apply_operations()

    def on_details(self, b, wdata=None):
        lewin = self.get_toplevel()
        dialog = ScChangelogViewer(lewin, self.selected_object)
        dialog.run()
        dialog.destroy()

    def on_toggled(self, w, path):
        model = self.tview.get_model()
        model[path][0] = not model[path][0]

    def init_view(self):
        # Install? Modifiable? Display label | Size | Image | Sensitive | iSize
        # | UpdateObject
        model = Gtk.TreeStore(bool, bool, str, str, GdkPixbuf.Pixbuf,
                              bool, int, ScUpdateObject)
        self.selected_object = None

        # Mandatory updates
        m_label = "<big><b>Required Updates</b></big>\n" \
                  "These updates are mandatory and will be selected " \
                  "automatically."
        row_m = model.append(None, [True, False, m_label, None,
                                    self.appsystem.mandatory_pixbuf,
                                    True, 0, None])
        # Security row
        s_label = "<big><b>Security Updates</b></big>\n" \
                  "These updates are strongly recommended to support safe " \
                  "usage of your device."
        row_s = model.append(None, [False, True, s_label, None,
                                    self.appsystem.security_pixbuf,
                                    True, 0, None])
        # All other updates
        u_label = "<big><b>Other Updates</b></big>\n" \
                  "These updates may introduce new software versions and " \
                  "bug-fixes."
        row_u = model.append(None, [False, True, u_label, None,
                                    self.appsystem.other_pixbuf,
                                    True, 0, None])

        # Need a shared context for these guys
        self.installdb = self.basket.installdb
        self.packagedb = self.basket.packagedb

        # Expand with a plan operation to be up front about new deps
        upgrades = pisi.api.list_upgradable()
        n_updates = len(upgrades)

        obsol = pisi.api.list_obsoleted()
        replc = pisi.api.list_replaces()
        for item in sorted(upgrades):

            old_item = item
            if item in obsol:
                if item not in replc:
                    # No valid replacement, skip it
                    continue
                # Chose the replacement
                item = replc[item][0]

            new_pkg = self.packagedb.get_package(item)
            new_version = "%s-%s" % (str(new_pkg.version),
                                     str(new_pkg.release))
            pkg_name = str(new_pkg.name)
            old_pkg = None
            systemBase = False

            icon = PACKAGE_ICON_NORMAL
            if new_pkg.partOf == "system.base":
                systemBase = True
                parent_row = row_m
            else:
                parent_row = row_u

            if self.installdb.has_package(item):
                old_pkg = self.installdb.get_package(item)

            sc_obj = ScUpdateObject(old_pkg, new_pkg)

            if sc_obj.is_security_update() and parent_row != row_m:
                parent_row = row_s
                icon = PACKAGE_ICON_SECURITY

            summary = str(new_pkg.summary)
            if len(summary) > 76:
                summary = "%s…" % summary[0:76]

            # Finally, actual size, and readable size
            pkgSize = sc_obj.get_update_size()
            dlSize = sc_format_size_local(pkgSize)

            icon = self.appsystem.get_pixbuf_only(new_pkg)

            pkg_name = GLib.markup_escape_text(pkg_name)
            summary = GLib.markup_escape_text(summary)

            if old_item != item:
                pref = "%s (replaces %s)" % (pkg_name, old_item)
            else:
                pref = "%s" % (pkg_name)

            p_print = "%s - <small>%s</small>\n%s" % (pref,
                                                      new_version,
                                                      summary)

            model.append(parent_row, [systemBase, not systemBase,
                                      p_print, dlSize, icon, True, pkgSize,
                                      sc_obj])

        # Disable empty rows
        for item in [row_s, row_m, row_u]:
            if model.iter_n_children(item) == 0:
                model.set(item, 0, False)
                model.set(item, 1, False)
                model.set(item, 5, False)

        Gdk.threads_enter()
        self.tview.set_model(model)
        # Hook up events so we know what's going on (4 non blondes.)
        self.update_from_selection()
        model.connect_after('row-changed', self.on_model_row_changed)
        if n_updates < 1:
            self.stack.set_visible_child_name("check")
        else:
            self.stack.set_visible_child_name("updates")
        Gdk.threads_leave()
        return False

    should_ignore = False

    def on_model_row_changed(self, tmodel, path, titer):
        """ Handle selection changes """
        parent = tmodel.iter_parent(titer)

        if self.should_ignore:
            return

        self.should_ignore = True

        # Handle child set to parent
        if parent is not None:
            num_children = tmodel.iter_n_children(parent)
            inactive_children = []

            # Find all inactive checkboxes
            for i in xrange(0, num_children):
                child = tmodel.iter_nth_child(parent, i)
                child_path = tmodel.get_path(child)
                active = tmodel[child_path][0]
                if not active:
                    inactive_children.append(child_path)

            ppath = tmodel.get_path(parent)
            # One inactive means parent = FALSE, all active = TRUE
            if len(inactive_children) > 0:
                tmodel[ppath][0] = False
            else:
                tmodel[ppath][0] = True
        else:
            # Handle parent set children
            num_children = tmodel.iter_n_children(titer)
            active = tmodel[path][0]
            for i in xrange(0, num_children):
                child = tmodel.iter_nth_child(titer, i)
                child_path = tmodel.get_path(child)

                tmodel[child_path][0] = active

        self.should_ignore = False

        self.update_from_selection()

    def update_from_selection(self):
        """ Update selection, size, etc, from current view """
        model = self.tview.get_model()

        total_update = 0
        total_size = 0
        total_available = 0

        # enumerate root nodes
        for i in xrange(0, model.iter_n_children(None)):
            root_kid = model.iter_nth_child(None, i)

            # enumarate children in this root node
            for j in xrange(0, model.iter_n_children(root_kid)):
                child = model.iter_nth_child(root_kid, j)
                child_path = model.get_path(child)

                total_available += 1

                active = model[child_path][0]
                if not active:
                    continue
                total_update += 1
                total_size += model[child_path][6]
        # Skip it.
        if total_update == 0:
            self.selection_label.set_text("{} of {} updates selected".format(
                total_update, total_available))
            self.update_btn.set_sensitive(False)
            return
        dlSize = sc_format_size_local(total_size, True)
        newLabel = "{} of {} updates selected ({} to download)".format(
                   total_update, total_available, dlSize)
        self.update_btn.set_sensitive(True)
        self.selection_label.set_text(newLabel)

    def on_row_activated(self, tview, path, column, udata=None):
        """ Determine update info availablity """
        model = tview.get_model()
        titer = model.get_iter(path)

        # Root node, disable our guy
        parent = model.iter_parent(titer)
        if not parent:
            self.view_details.set_sensitive(False)
            self.selected_object = None
            return
        self.view_details.set_sensitive(True)
        self.selected_object = model[path][7]
