# Copyright 2021 NXP Semiconductors
#
# SPDX-License-Identifier: BSD-3-Clause

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gst
import os
from subprocess import Popen
import time


class ispDemo(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="ISP Demo")
        self.set_default_size(440, 280)
        self.set_resizable(False)
        if path is None:
            noCam = Gtk.Label.new("No Basler Camera!")
            self.add(noCam)
            return
        grid = Gtk.Grid()
        grid.set_row_homogeneous(True)
        grid.set_margin_right(20)
        grid.set_margin_left(20)
        self.add(grid)

        r_label = Gtk.Label.new("Red")
        r_label.set_halign(1)
        r_label.set_valign(2)
        r_label.set_margin_bottom(16)

        gr_label = Gtk.Label.new("Green-Red")
        gr_label.set_halign(1)
        gr_label.set_valign(2)
        gr_label.set_margin_bottom(19)

        gb_label = Gtk.Label.new("Green-Blue")
        gb_label.set_halign(1)
        gb_label.set_valign(2)
        gb_label.set_margin_bottom(19)

        b_label = Gtk.Label.new("Blue")
        b_label.set_halign(1)
        b_label.set_valign(2)
        b_label.set_margin_bottom(19)

        self.r_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 255, 1)
        self.r_scale.set_value(168)
        self.r_scale.set_margin_left(15)
        self.r_scale.set_margin_top(10)
        self.r_scale.connect('value-changed', self.on_change_bls)
        self.r_scale.set_hexpand(True)

        self.gr_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 255, 1)
        self.gr_scale.set_value(168)
        self.gr_scale.set_margin_left(15)
        self.gr_scale.connect('value-changed', self.on_change_bls)

        self.gb_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 255, 1)
        self.gb_scale.set_value(168)
        self.gb_scale.set_margin_left(15)
        self.gb_scale.connect('value-changed', self.on_change_bls)

        self.b_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 255, 1)
        self.b_scale.set_value(168)
        self.b_scale.set_margin_left(15)
        self.b_scale.connect('value-changed', self.on_change_bls)

        grid.attach(r_label, 0, 1, 1, 1)
        grid.attach(gr_label, 0, 2, 1, 1)
        grid.attach(gb_label, 0, 3, 1, 1)
        grid.attach(b_label, 0, 4, 1, 1)
        grid.attach(self.r_scale, 1, 1, 1, 1)
        grid.attach(self.gr_scale, 1, 2, 1, 1)
        grid.attach(self.gb_scale, 1, 3, 1, 1)
        grid.attach(self.b_scale, 1, 4, 1, 1)

    def on_change_bls(self, widget):
        r = self.r_scale.get_value()
        gr = self.gr_scale.get_value()
        gb = self.gb_scale.get_value()
        b = self.b_scale.get_value()
        os.system(
            "/opt/imx8-isp/bin/vvext " + path[-1] + " 0 BLS \"" + str(int(r)) + ", " + str(int(gr)) + ", " + str(int(gb)) + ", " + str(
                int(b)) + "\"")


def on_close(self):
    os.system("pkill -P" + str(os.getpid()))
    Gtk.main_quit()


if __name__ == "__main__":
    Gst.init()
    dev_monitor = Gst.DeviceMonitor()
    dev_monitor.add_filter("Video/Source")
    dev_monitor.start()
    path = None
    for dev in dev_monitor.get_devices():
        if dev.get_display_name() == "VIV":
            dev_caps = dev.get_caps().normalize()
            for i in range(dev_caps.get_size()):
                caps_struct = dev_caps.get_structure(i)
                if caps_struct.get_name() != "video/x-raw":
                    continue
                framerate = ("{}/{}".format(*caps_struct.get_fraction("framerate")[1:]))
                if framerate != "0/0":
                    path = "device="+dev.get_properties().get_string("device.path")
                    break
        if path is not None:
            Popen(["gst-launch-1.0", "v4l2src", path, "!", "waylandsink"])
            break
    time.sleep(2)
    window = ispDemo()
    window.connect("destroy", on_close)
    window.show_all()
    Gtk.main()
