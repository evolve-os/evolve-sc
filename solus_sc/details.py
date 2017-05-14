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
from gi.repository import Gio
from gi.repository import AppStreamGlib as As
from .util import sc_format_size_local


class PackageDetailsView(Gtk.Box):
    """ Show all the details of a given package to the user as well
        as supplying them with manipulation functions, i.e. for removal, etc
    """

    # The appsystem allows us to perform queries in icons and such
    appsystem = None

    # The main header icon, hopefully from appstream
    image_icon = None

    # Display name of the package, not necessarily the .eopkg name
    label_name = None

    # The currently selected package for rendering
    package = None

    # Description for this package. Currently stripped of markup..
    label_description = None

    # Installed size/download size
    label_size = None

    # Package license(s)
    label_license = None

    install_button = None
    remove_button = None
    website_button = None
    donate_button = None

    # Urls..
    url_website = None
    url_donate = None
    is_install_page = False
    basket = None

    def on_donate(self, btn, udata=None):
        """ Launch the donation site """
        try:
            Gtk.show_uri(None, self.url_donate, 0)
        except:
            pass

    def on_website(self, btn, udata=None):
        """ Launch the main website """
        try:
            Gtk.show_uri(None, self.url_website, 0)
        except:
            pass

    def on_install(self, btn, udata=None):
        """ Install a package """
        self.basket.install_package(self.package)
        self.basket.apply_operations()

    def on_remove(self, btn, udata=None):
        """ Install a package """
        self.basket.remove_package(self.package)
        self.basket.apply_operations()

    def on_basket_changed(self, basket, udata=None):
        """ Update view based on the currently selected package """
        sensitive = not self.basket.is_busy()

        self.install_button.set_sensitive(sensitive)
        self.remove_button.set_sensitive(sensitive)

        if self.basket.is_busy():
            return
        if not self.package:
            return

        if self.is_install_page:
            # Find out if this thing was actually installed ..
            if self.basket.installdb.has_package(self.package.name):
                pkg = self.basket.installdb.get_package(self.package.name)
                self.is_install_page = False
                self.update_from_package(pkg)
        else:
            # We're a remove package, see if we removed our thing
            if not self.basket.installdb.has_package(self.package.name):
                # Offer installing
                if not self.basket.packagedb.has_package(self.package.name):
                    print("Unknown local package .... ")
                    return
                pkg = self.basket.packagedb.get_package(self.package.name)
                self.is_install_page = True
                self.update_from_package(pkg)

    def __init__(self, appsystem, basket):
        Gtk.Box.__init__(self, Gtk.Orientation.VERTICAL)
        self.appsystem = appsystem
        self.basket = basket
        self.basket.connect("basket-changed", self.on_basket_changed)

        self.set_border_width(24)

        header = Gtk.Box(Gtk.Orientation.HORIZONTAL, 0)
        self.pack_start(header, False, False, 0)

        # Set up the icon
        self.image_icon = Gtk.Image.new()
        # Some padding between us and the display label..
        self.image_icon.set_margin_end(12)
        header.pack_start(self.image_icon, False, False, 0)

        # Set up the display label
        self.label_name = Gtk.Label("")
        self.label_name.set_max_width_chars(60)
        self.label_name.set_line_wrap(True)
        self.label_name.set_property("xalign", 0.0)
        header.pack_start(self.label_name, False, False, 0)
        self.label_name.set_halign(Gtk.Align.START)
        self.label_name.set_valign(Gtk.Align.START)
        self.label_name.set_margin_top(6)

        # Set up the action line
        action_line = Gtk.Box(Gtk.Orientation.HORIZONTAL, 0)
        action_line.set_valign(Gtk.Align.CENTER)
        action_line.set_halign(Gtk.Align.END)
        header.pack_end(action_line, False, False, 0)
        self.install_button = Gtk.Button(_("Install"))
        self.install_button.connect("clicked", self.on_install)
        self.install_button.set_can_focus(False)
        self.install_button.get_style_context().add_class("suggested-action")
        action_line.pack_end(self.install_button, False, False, 0)
        self.install_button.set_no_show_all(True)

        # Remove button
        self.remove_button = Gtk.Button(_("Remove"))
        self.remove_button.connect("clicked", self.on_remove)
        self.remove_button.set_can_focus(False)
        self.remove_button.get_style_context().add_class("destructive-action")
        action_line.pack_end(self.remove_button, False, False, 0)
        self.remove_button.set_no_show_all(True)

        header.set_property("margin-bottom", 24)

        self.scroll = Gtk.ScrolledWindow(None, None)
        self.scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        # Need the description down a bit and a fair bit padded
        self.label_description = Gtk.Label("")
        self.label_description.set_halign(Gtk.Align.START)
        self.label_description.set_valign(Gtk.Align.START)
        self.label_description.set_margin_top(20)
        # Deprecated but still needs using with linewrap
        self.label_description.set_property("xalign", 0.0)
        self.label_description.set_margin_start(8)
        self.label_description.set_max_width_chars(70)
        self.label_description.set_line_wrap(True)
        self.label_description.set_selectable(True)
        self.label_description.set_can_focus(False)
        self.scroll.add(self.label_description)
        self.pack_start(self.scroll, True, True, 0)

        # Begin the tail grid
        self.tail_grid = Gtk.Grid()
        self.tail_grid.set_margin_top(8)
        self.tail_grid.set_row_spacing(8)
        self.tail_grid.set_column_spacing(8)
        self.pack_end(self.tail_grid, False, False, 0)

        # Visit the website of the package
        self.website_button = Gtk.Button(_("Website"))
        self.website_button.set_no_show_all(True)
        self.website_button.connect("clicked", self.on_website)
        # self.tail_grid.attach(button_website, t, w, h)
        self.tail_grid.attach(self.website_button, 0, 1, 1, 1)

        # Donation button launches website to donate to authors
        self.donate_button = Gtk.Button(_("Donate"))
        self.donate_button.connect("clicked", self.on_donate)
        self.donate_button.set_no_show_all(True)
        self.tail_grid.attach(self.donate_button, 1, 1, 1, 1)

        # Size of the package when installed locally
        self.label_installed = Gtk.Label(_("Installed size"))
        self.label_installed.get_style_context().add_class("dim-label")
        self.tail_grid.attach(self.label_installed, 0, 0, 1, 1)

        self.label_size = Gtk.Label("")
        self.tail_grid.attach(self.label_size, 1, 0, 1, 1)

        # License field
        label_license_field = Gtk.Label(_("License"))
        label_license_field.get_style_context().add_class("dim-label")
        self.tail_grid.attach(label_license_field, 2, 0, 1, 1)

        self.label_license = Gtk.Label("")
        self.tail_grid.attach(self.label_license, 3, 0, 1, 1)

    def update_from_package(self, package):
        """ Update our view based on a given package """

        name = self.appsystem.get_name(package)
        comment = self.appsystem.get_summary(package)
        description = self.appsystem.get_description(package)
        self.package = package

        version = "{}-{}".format(str(package.version), str(package.release))
        # Update display now.
        title_format = "<span size='x-large'><b>{}</b> - {}</span>\n{}"
        self.label_name.set_markup(title_format.format(name,
                                                       version,
                                                       comment))
        licenses = u" | ".join([str(x) for x in package.license])
        self.label_license.set_text(licenses)

        # Sort out a nice icon
        pbuf = self.appsystem.get_pixbuf(package)
        if pbuf:
            # Handle icon theme names
            if isinstance(pbuf, Gio.ThemedIcon):
                self.image_icon.set_from_gicon(pbuf, Gtk.IconSize.DIALOG)
                self.image_icon.set_pixel_size(64)
            else:
                # Handle local files
                self.image_icon.set_from_pixbuf(pbuf)
        else:
            icon = self.appsystem.get_icon(package)
            self.image_icon.set_from_icon_name(icon, Gtk.IconSize.DIALOG)
            self.image_icon.set_pixel_size(64)

        # Update the description
        self.label_description.set_label(self.render_plain(description))

        # Take the appropriate action ..
        if self.is_install_page:
            self.remove_button.hide()
            self.install_button.show()
        else:
            sensitive = package.partOf != "system.base"
            self.install_button.hide()
            self.remove_button.show()
            if not sensitive:
                self.remove_button.set_tooltip_text(
                    _("Cannot remove core system software"))
            else:
                self.remove_button.set_tooltip_text(None)
            self.remove_button.set_sensitive(sensitive)

        # Update the homepage button
        url = self.appsystem.get_website(package)
        if url:
            self.url_website = url
            self.website_button.show()
        else:
            self.website_button.hide()

        donate = self.appsystem.get_donation_site(package)
        if donate:
            self.url_donate = donate
            self.donate_button.show()
        else:
            self.donate_button.hide()

        size = sc_format_size_local(package.installedSize)
        self.label_size.set_markup(size)

    def render_plain(self, input_string):
        """ Render a plain version of the description, no markdown """
        plain = As.markup_convert_simple(input_string)
        plain = plain.replace("&quot;", "\"").replace("&apos;", "'")
        return plain
