#!/usr/bin/env python3

"""
Copyright 2025 NXP
SPDX-License-Identifier: Apache-2.0

The following is a demo to show CAN Open usage on i.MX boards.
It simulates a car navigation system composed of sensors and 
a reversing camera screen.
Sensors are emulated using sliders.
"""


import gi
import subprocess
import os


# Check for correct Gtk and Gst versions
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk as gtk
from gi.repository import Gst, GLib


class SensorInput:

    def __init__(self):
        # Obtain GUI settings and configurations
        glade_file = "/opt/gopoint-apps/scripts/communication/car_navigation/sensor_input.glade"
        self.builder = gtk.Builder()
        self.builder.add_from_file(glade_file)
        self.builder.connect_signals(self)

        self.close_button = self.builder.get_object("close-button")
        self.close_can_output = self.builder.get_object("close-can-output")

        # Get the scale objects and set their ranges
        self.sensor1 = self.builder.get_object("sensor1")
        self.sensor2 = self.builder.get_object("sensor2")
        self.sensor3 = self.builder.get_object("sensor3")
        self.sensor4 = self.builder.get_object("sensor4")
        self.steering = self.builder.get_object("steering")

        self.sensor1.set_range(0, 50)
        self.sensor2.set_range(0, 50)
        self.sensor3.set_range(0, 50)
        self.sensor4.set_range(0, 50)
        self.steering.set_range(-50, 50)

        self.sensor1.set_value(50)
        self.sensor2.set_value(50)
        self.sensor3.set_value(50)
        self.sensor4.set_value(50)
        self.steering.set_value(0)

        self.sensor1.connect("value-changed", self.send_data_template(0))
        self.sensor2.connect("value-changed", self.send_data_template(1))
        self.sensor3.connect("value-changed", self.send_data_template(2))
        self.sensor4.connect("value-changed", self.send_data_template(3))
        self.steering.connect("value-changed", self.send_data_template(4))

        self.window = self.builder.get_object("window")

        Gst.init()
        self.main_loop = GLib.MainLoop()

        # Connect signals
        self.close_button.connect("clicked", self.quit_app)
        self.window.connect("delete-event", gtk.main_quit)
        self.window.show()

        # Reseting navigation
        subprocess.run(["cocomm", "[1] 10 w 0x2001 0 u8 50"])
        subprocess.run(["cocomm", "[1] 10 w 0x2001 1 u8 50"])
        subprocess.run(["cocomm", "[1] 10 w 0x2001 2 u8 50"])
        subprocess.run(["cocomm", "[1] 10 w 0x2001 3 u8 50"])
        subprocess.run(["cocomm", "[1] 10 w 0x2000 0 i8 0"])

    def quit_app(self, widget):
        """Closes GStreamer pipeline and GTK+3 GUI"""
        self.main_loop.quit()
        gtk.main_quit()

    def show_can_output_window(self, widget):
        self.can_output_window.show()

    def close_can_output_window(self, widget):
        self.can_output_window.hide()

    def send_data_template(self, arg):

        def send_data(_):
            if arg == 0:
                val, regs = self.sensor1.get_value(), "0x2001 0 u8"
            elif arg == 1:
                val, regs = self.sensor2.get_value(), "0x2001 1 u8"
            elif arg == 2:
                val, regs = self.sensor3.get_value(), "0x2001 2 u8"
            elif arg == 3:
                val, regs = self.sensor4.get_value(), "0x2001 3 u8"
            elif arg == 4:
                val, regs = self.steering.get_value(), "0x2000 0 i8"

            result = subprocess.run(["cocomm", f"[1] 10 w {regs} {int(val)}"])

        return send_data


if __name__ == "__main__":
    main = SensorInput()
    gtk.main()
