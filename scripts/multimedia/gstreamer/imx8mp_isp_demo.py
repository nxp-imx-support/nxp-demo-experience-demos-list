# Copyright 2021 NXP Semiconductors
#
# SPDX-License-Identifier: BSD-3-Clause

import subprocess
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
        self.set_border_width(10)
        if path is None:
            noCam = Gtk.Label.new("No Basler Camera!")
            self.add(noCam)
            return
        
        main_grid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(main_grid)
        
        self.content_stack = Gtk.Stack()
        #self.content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        #self.content_stack.set_transition_duration(500)

        options = [
            "Black Level Subtraction",
            "Dewarp and FPS"
        ]

        options_combo = Gtk.ComboBoxText()
        options_combo.set_entry_text_column(0)
        for option in options:
            options_combo.append_text(option)
        options_combo.set_active(0)
        options_combo.connect('changed', self.on_options_change)

        main_grid.pack_start(options_combo, True, True, 0)
        main_grid.pack_start(self.content_stack, True, True, 0)

        bls_grid = Gtk.Grid(row_homogeneous=True,
                         column_spacing=15,
                         row_spacing=15)
        bls_grid.set_margin_end(10)
        bls_grid.set_margin_start(10)

        r_label = Gtk.Label.new("Red")
        r_label.set_halign(1)

        gr_label = Gtk.Label.new("Green.R")
        gr_label.set_halign(1)

        gb_label = Gtk.Label.new("Green.B")
        gb_label.set_halign(1)

        b_label = Gtk.Label.new("Blue")
        b_label.set_halign(1)

        self.r_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 255, 1)
        self.r_scale.set_value(168)
        self.r_scale.connect('value-changed', self.on_change_bls)
        self.r_scale.set_hexpand(True)

        self.gr_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 255, 1)
        self.gr_scale.set_value(168)
        self.gr_scale.connect('value-changed', self.on_change_bls)
        self.gr_scale.set_hexpand(True)

        self.gb_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 255, 1)
        self.gb_scale.set_value(168)
        self.gb_scale.connect('value-changed', self.on_change_bls)
        self.gb_scale.set_hexpand(True)

        self.b_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 255, 1)
        self.b_scale.set_value(168)
        self.b_scale.connect('value-changed', self.on_change_bls)
        self.b_scale.set_hexpand(True)

        bls_grid.attach(r_label, 0, 1, 1, 1)
        bls_grid.attach(gr_label, 0, 2, 1, 1)
        bls_grid.attach(gb_label, 0, 3, 1, 1)
        bls_grid.attach(b_label, 0, 4, 1, 1)
        bls_grid.attach(self.r_scale, 1, 1, 1, 1)
        bls_grid.attach(self.gr_scale, 1, 2, 1, 1)
        bls_grid.attach(self.gb_scale, 1, 3, 1, 1)
        bls_grid.attach(self.b_scale, 1, 4, 1, 1)

        self.content_stack.add_named(bls_grid, "Black Level Subtraction")

        dewarp_grid = Gtk.Grid(row_homogeneous=True,
                         column_spacing=15,
                         row_spacing=15)
        dewarp_grid.set_margin_end(10)
        dewarp_grid.set_margin_start(10)

        vflip_label = Gtk.Label.new("Vertical Flip")
        vflip_label.set_halign(1)

        self.vflip_switch = Gtk.Switch()
        self.vflip_switch.connect("notify::active", self.on_change_vflip)
        self.vflip_switch.set_active(False)
        self.vflip_switch.set_halign(1)
        self.vflip_switch.set_valign(3)

        hflip_label = Gtk.Label.new("Horizontal Flip")
        hflip_label.set_halign(1)

        self.hflip_switch = Gtk.Switch()
        self.hflip_switch.connect("notify::active", self.on_change_hflip)
        self.hflip_switch.set_active(False)
        self.hflip_switch.set_halign(1)
        self.hflip_switch.set_margin_top(20)
        self.hflip_switch.set_margin_bottom(20)

        fps_label = Gtk.Label.new("FPS Max")
        fps_label.set_halign(1)

        self.fps_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 60, 1)
        self.fps_scale.set_value(168)
        self.fps_scale.connect('value-changed', self.on_change_fps)
        self.fps_scale.set_hexpand(True)

        dewarp_grid.attach(vflip_label, 0, 1, 1, 1)
        dewarp_grid.attach(hflip_label, 0, 2, 1, 1)
        dewarp_grid.attach(fps_label, 0, 3, 1, 1)
        dewarp_grid.attach(self.vflip_switch, 1, 1, 1, 1)
        dewarp_grid.attach(self.hflip_switch, 1, 2, 1, 1)
        dewarp_grid.attach(self.fps_scale, 1, 3, 1, 1)
        
        self.content_stack.add_named(dewarp_grid, "Dewarp and FPS")

    def on_change_bls(self, widget):
        r = self.r_scale.get_value()
        gr = self.gr_scale.get_value()
        gb = self.gb_scale.get_value()
        b = self.b_scale.get_value()
        self.change_isp("<id>:<bls.s.cfg>;<blue>:" + str(int(b)) +
        ";<green.b>:" + str(int(gb)) + ";<green.r>:" + str(int(gr)) +
        ";<red>:" + str(int(r)))

    def on_change_vflip(self, widget, thing):
        if(widget.get_active()):
            self.change_isp("<id>:<dwe.s.vflip>; <dwe>:{<vflip>:true}")
        else:
            self.change_isp("<id>:<dwe.s.vflip>; <dwe>:{<vflip>:false}")


    def on_change_hflip(self, widget, thing):
        if(widget.get_active()):
            self.change_isp("<id>:<dwe.s.hflip>; <dwe>:{<hflip>:true}")
        else:
            self.change_isp("<id>:<dwe.s.hflip>; <dwe>:{<hflip>:false}")

    def on_change_fps(self, widget):
        self.change_isp("<id>:<s.fps>; <fps>:" + str(int(widget.get_value())))

    def change_isp(self, command):
        os.system(
            "v4l2-ctl -d " + path + " -c viv_ext_ctrl='{" +
            command + "}'")
        
    def on_options_change(self, widght):
        self.content_stack.set_visible_child_name(widght.get_active_text())



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
                    path = dev.get_properties().get_string("device.path")
                    break
        if path is not None:
            Popen(["gst-launch-1.0", "v4l2src", "device=" + path, "!", "waylandsink"])
            break
    time.sleep(2)
    window = ispDemo()
    window.connect("destroy", on_close)
    window.show_all()
    Gtk.main()
