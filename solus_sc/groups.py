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

from gi.repository import Gtk
from .components import ScComponentsView
from .available_view import ScAvailableView
from .details import PackageDetailsView


class ScGroupButton(Gtk.Button):
    """ Manage the monotony of a Group """

    group = None

    def __init__(self, db, group):
        Gtk.Button.__init__(self)

        self.group = group

        icon_theme = self.get_settings().get_property("gtk-icon-theme-name")
        icon_theme = icon_theme.lower().replace("-", "")
        # Sneaky, I know.
        if icon_theme == "arcicons" or icon_theme == "arc":
            devIcon = "text-x-changelog"
        else:
            devIcon = "gnome-dev-computer"

        replacements = {
            "text-editor": "x-office-calendar",
            "redhat-programming": devIcon,
            "security-high": "preferences-system-privacy",
            "network": "preferences-system-network",
        }

        # Pretty things up with a Icon|Label setup
        icon = str(group.icon)
        if icon in replacements:
            icon = replacements[icon]

        gDesc = str(group.localName)
        image = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.DIALOG)
        image.set_halign(Gtk.Align.START)
        image.set_pixel_size(64)

        label_box = Gtk.Box(Gtk.Orientation.VERTICAL, 0)
        label_box.set_valign(Gtk.Align.CENTER)

        box = Gtk.Box(Gtk.Orientation.HORIZONTAL, 0)
        box.pack_start(image, False, False, 0)
        image.set_property("margin-right", 10)
        label = Gtk.Label(gDesc)
        label.get_style_context().add_class("title")
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.START)
        label_box.pack_start(label, True, True, 0)
        box.pack_start(label_box, True, True, 0)
        self.add(box)

        # count the components
        kids = db.get_group_components(group.name)
        # "5 categories" - the number of categories within each group
        info_label = Gtk.Label(_("{} categories").format(len(kids)))
        info_label.set_halign(Gtk.Align.START)
        info_label.get_style_context().add_class("info-label")
        info_label.get_style_context().add_class("dim-label")
        label_box.pack_start(info_label, False, False, 0)

        self.get_style_context().add_class("group-button")


class ScGroupsView(Gtk.EventBox):
    """ Main group view, i.e. "System", "Development", etc. """

    flowbox = None
    groupdb = None
    group_names = None
    scroll = None
    stack = None
    owner = None

    group_map = dict()

    # Main component view
    comp_view = None

    # Available packagees
    avail_view = None

    # Details of selection
    details_view = None

    breadcrumbs = None

    def handle_back(self):
        """ Go back to the group selection view for now """
        w = self.breadcrumbs.pop()
        self.stack.set_visible_child_name(w)
        self.owner.set_can_back(len(self.breadcrumbs) > 0)

    def can_back(self):
        """ Whether we can go back """
        return len(self.breadcrumbs) > 0

    def __init__(self, owner):
        Gtk.EventBox.__init__(self)
        self.owner = owner

        self.breadcrumbs = []

        self.stack = Gtk.Stack()
        t = Gtk.StackTransitionType.SLIDE_LEFT_RIGHT
        self.stack.set_transition_type(t)
        self.add(self.stack)

        self.scroll = Gtk.ScrolledWindow(None, None)
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll.set_shadow_type(Gtk.ShadowType.ETCHED_IN)

        self.stack.add_named(self.scroll, "groups")

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_property("margin", 20)
        self.flowbox.set_column_spacing(15)
        self.flowbox.set_row_spacing(15)
        self.flowbox.set_orientation(Gtk.Orientation.HORIZONTAL)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flowbox.set_valign(Gtk.Align.START)
        self.scroll.add(self.flowbox)

        st = self.get_style_context()
        st.add_class(Gtk.STYLE_CLASS_VIEW)
        st.add_class("content")

        self.comp_view = ScComponentsView(self, self.owner)
        self.stack.add_named(self.comp_view, "components")

        # Available view
        self.avail_view = ScAvailableView(self, self.owner)
        self.stack.add_named(self.avail_view, "available")

        # Details view
        self.details_view = PackageDetailsView(self.owner.appsystem,
                                               self.owner.basket)
        self.stack.add_named(self.details_view, "details")
        self.init_view()

    def on_group_clicked(self, btn, data=None):
        groupdb = self.owner.basket.groupdb
        self.stack.set_visible_child_name("components")
        self.breadcrumbs.append("groups")
        components = groupdb.get_group_components(btn.group.name)
        self.comp_view.set_components(components)
        self.owner.set_can_back(True)

    def init_view(self):
        """ Set up the groups and push them into the view """
        for widget in self.flowbox.get_children():
            widget.destroy()

        groupdb = self.owner.basket.groupdb
        self.group_names = sorted(groupdb.list_groups())
        self.group_map = dict()

        # set up the group widgets
        for name in self.group_names:
            group = groupdb.get_group(name)
            self.group_map[name] = group

            button = ScGroupButton(groupdb, group)
            button.connect("clicked", self.on_group_clicked)
            button.show_all()
            self.flowbox.add(button)

    def select_component(self, component):
        self.breadcrumbs.append("components")
        self.stack.set_visible_child_name("available")
        self.avail_view.set_component(component)
        self.owner.set_can_back(True)

    def select_details(self, package):
        if self.owner.basket.installdb.has_package(package.name):
            self.details_view.is_install_page = False
        else:
            self.details_view.is_install_page = True
        self.details_view.update_from_package(package)
        self.breadcrumbs.append("available")
        self.stack.set_visible_child_name("details")
        self.owner.set_can_back(True)
