#!/usr/bin/env python3

"""
Copyright 2025 NXP
SPDX-License-Identifier: Apache-2.0

The following is a demo to show CAN Open usage on i.MX boards.
It simulates a car navigation system composed of sensors and 
a reversing camera screen.
Sensors are emulated using sliders.
"""

import os
import sys
import subprocess
import threading
import time
import glob
import numpy as np
import gi

from PIL import Image

# Check for correct Gtk and Gst versions
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk as gtk
from gi.repository import Gst, GLib


def threaded(fn):
    """Handle threads out of main GTK thread"""

    def wrapper(*args, **kwargs):
        threading.Thread(target=fn, args=args, kwargs=kwargs).start()

    return wrapper


class CarNavigation:

    def __init__(self):
        # Obtain GUI settings and configurations
        glade_file = "/opt/gopoint-apps/scripts/communication/car_navigation/CarNav.glade"
        self.builder = gtk.Builder()
        self.builder.add_from_file(glade_file)
        self.builder.connect_signals(self)

        # Get main application window and about dialog
        window = self.builder.get_object("main-window")
        self.about_dialog = self.builder.get_object("about-dialog")

        # Create instances of labels for performance information
        self.video_ms = self.builder.get_object("video-ms")
        self.video_fps = self.builder.get_object("video-fps")
        self.inference_ms = self.builder.get_object("inference-ms")
        self.inference_ips = self.builder.get_object("inference-ips")

        # Create instances for combo boxes
        self.part_box = self.builder.get_object("combo-box-part")
        self.device_box = self.builder.get_object("combo-box-device")

        # Create instances for buttons
        self.run_button = self.builder.get_object("run-button")
        self.about_button = self.builder.get_object("about-button")
        self.close_button = self.builder.get_object("close-button")

        # Obtain available devices
        for device in glob.glob("/sys/class/net/can*"):
            self.device_box.append_text(device.split("/")[-1])
        self.device_box.set_active(0)

        self.part_box.set_active(0)

        Gst.init()
        self.main_loop = GLib.MainLoop()

        # Connect signals
        self.close_button.connect("clicked", self.quit_app)
        window.connect("delete-event", gtk.main_quit)
        window.show()

    def quit_app(self, widget):
        """Closes GStreamer pipeline and GTK+3 GUI"""
        self.main_loop.quit()
        gtk.main_quit()

    def about_button_activate(self, widget):
        """
        Function to handle about dialog window
        """
        self.about_dialog.run()
        time.sleep(100 / 1000)
        self.about_dialog.hide()
        return True

    def about_dialog_activate(self, widget):
        """Function to handle the about dialog window"""
        self.about_dialog.run()
        self.about_dialog.hide()

    @threaded
    def start(self, widget):
        part = self.part_box.get_active_id()
        can = self.device_box.get_active_text()

        os.system(f"ip link set down {can}")
        os.system(f"ip link set {can} type can bitrate 250000")
        os.system(f"ip link set up {can}")

        print("Start", part, "on", can)
        if part == "1":
            os.system(
                "canopend " + str(can) + " -i 5 -c local-/tmp/CO_command_socket &"
            )
            time.sleep(2)
            subprocess.run(["python3", "/opt/gopoint-apps/scripts/communication/car_navigation/sensor_input.py"])

        if part == "2":
            subprocess.run(["python3", "/opt/gopoint-apps/scripts/communication/car_navigation/car_reverse_screen.py", str(can)])


if __name__ == "__main__":
    main = CarNavigation()
    gtk.main()
