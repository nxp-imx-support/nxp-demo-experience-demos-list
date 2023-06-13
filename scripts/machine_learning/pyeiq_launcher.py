"""
pyeIQ Launcher.

Copyright 2021-2022 NXP
SPDX-License-Identifier: BSD-3-Clause

This python script launches demos from pyeIQ. It as checks if pyeIQ is
installed and gets the required files from the internet if needed.

The currently supported demos are:
- small_id: An object classification demo with a small image
- small_detect: An object detection demo with a small image
- small_mask: A mask detection demo with a small image

"""

import os
import socket
from subprocess import Popen
import sys
import threading
import time
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio
sys.path.append("/home/root/.nxp-demo-experience/scripts/")
import utils
import importlib.metadata

try:
    import eiq
    PYEIQ = True
except ImportError:
    PYEIQ = False


def check_connection(host="208.67.220.220", port=53, timeout=5):
    """Check if there is an internet connection."""
    time.sleep(1)
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False


class PyeiqDemo(Gtk.Window):
    """Run a single pyeIQ demo."""

    def __init__(self, demo):
        """Set up a pyeIQ demo to run."""
        Gtk.Window.__init__(self, title="pyeIQ Launcher")
        self.set_default_size(300, 100)

        box = Gtk.Box()
        box.set_homogeneous(True)

        # Create Toolbar
        header = Gtk.HeaderBar()
        header.set_title("PyeIQ Launcher")
        self.set_titlebar(header)

        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        header.pack_end(quit_button)
        quit_button.connect("clicked", Gtk.main_quit)

        self.label = Gtk.Label.new("Starting...")
        box.pack_start(self.label, True, True, 0)
        self.add(box)
        if demo == "small_id":
            self.demo_name = "object_classification_tflite"
            self.file_name = "small_keyboard.jpg"
        elif demo == "small_detect":
            self.demo_name = "object_detection_tflite"
            self.file_name = "small_dog.jpg"
        elif demo == "small_mask":
            self.demo_name = "covid19_detection"
            self.file_name = "small_mask.jpg"
        else:
            self.label.set_text("Invalid demo name!")
            return
        thread = threading.Thread(target=self.check)
        thread.daemon = True
        thread.start()

    def check(self):
        """Check the requirments and starts the demo."""
        file_name = "/home/root/.cache/demoexperience/" + self.file_name
        if PYEIQ is False or os.path.isfile(file_name) is False:
            self.label.set_text("Checking for internet connection...")
            if check_connection():
                if PYEIQ is False:
                    self.label.set_text("Downloading pyeIQ...")
                    Popen(
                        ["pip3", "install", "pyeiq==3.0.1", "requests"]).wait()
                if os.path.isfile(file_name) is False:
                    self.label.set_text("Downloading test image...")
                    pic = utils.download_file(self.file_name)
                    if pic == -1 or pic == -2 or pic == -3:
                        self.label.set_text("Cannot load picture!")
                        return
            else:
                self.label.set_text("No internet connection.")
                return
        version = importlib.metadata.version('pyeiq')
        if (version != "3.0.1"):
            self.label.set_text(
                "pyeIQ version not compatible.\nUninstall pyeIQ"
                " and rerun this demo!")
            return
        self.label.set_text("Setting up demo...")
        pic = utils.download_file(self.file_name)
        Popen(["pyeiq", "--run", self.demo_name, "-i", str(pic)]).wait()
        Gtk.main_quit()


if __name__ == "__main__":
    window = PyeiqDemo(sys.argv[1])
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()
