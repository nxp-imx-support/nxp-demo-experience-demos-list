"""
Copyright 2023 NXP

SPDX-License-Identifier: BSD-3-Clause
This file is responsible for showing
loading window until new window gets opened
"""

import gi
import sys, subprocess
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GdkPixbuf, Gio, GLib

class MyWindow(Gtk.Window):

    def __init__(self):
        Gtk.Window.__init__(self)
        image = Gtk.Image()
        hb = Gtk.HeaderBar()
        hb.props.title = "Notification"
        quit_button = Gtk.Button()
        quit_button.connect("clicked", exit)
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        self.set_titlebar(hb)
        quit_button.add(quit_image)
        hb.pack_end(quit_button)
        animation_path = "/home/root/.nxp-demo-experience/scripts/TSN/qbv/loading.gif"
        animation = GdkPixbuf.PixbufAnimation.new_from_file(animation_path)
        image.set_from_animation(animation)
        if (sys.argv[1] == "launch"):
           GLib.timeout_add_seconds(2.9, Gtk.main_quit)
        elif (sys.argv[1] == "run_demo"):
           GLib.timeout_add_seconds(19.7, Gtk.main_quit)
        self.add(image)
        self.show_all()
window = MyWindow()
window.connect("destroy", Gtk.main_quit)
Gtk.main()

