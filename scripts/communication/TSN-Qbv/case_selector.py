"""
Copyright 2023-2024, 2026 NXP

SPDX-License-Identifier: BSD-3-Clause

This file creates a window with two buttons for selecting
between launching the demo or running the demo.
"""

import gi
import sys
import subprocess
import os
import time

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, Gio

class CaseSelectorWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self)
        self.set_border_width(10)
        self.set_resizable(False)
        self.set_size_request(600, 400)
        self.set_position(Gtk.WindowPosition.CENTER)
        
        # Header bar
        header = Gtk.HeaderBar()
        header.props.title = "TSN 802.1Qbv"
        self.set_titlebar(header)
        
        # Quit button
        quit_button = Gtk.Button()
        quit_button.connect("clicked", Gtk.main_quit)
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        header.pack_end(quit_button)
        
        # Main vertical box
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        vbox.set_margin_top(20)
        vbox.set_margin_bottom(20)
        vbox.set_margin_start(20)
        vbox.set_margin_end(20)
        self.add(vbox)
        
        # Image
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            filename="/opt/gopoint-apps/scripts/communication/TSN-Qbv/TSN_Qbv_setup_diagram.png",
            width=1280,
            height=720,
            preserve_aspect_ratio=True,
        )
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        vbox.pack_start(image, False, False, 0)
        
        # Button box
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        button_box.set_halign(Gtk.Align.CENTER)
        vbox.pack_start(button_box, False, False, 0)
        
        # Launch Demo button
        camera_button = Gtk.Button(label="Camera")
        camera_button.set_size_request(200, 50)
        camera_button.connect("clicked", self.on_camera_clicked)
        button_box.pack_start(camera_button, False, False, 0)
        
        # Run Demo button
        display_button = Gtk.Button(label="Display")
        display_button.set_size_request(200, 50)
        display_button.connect("clicked", self.on_display_clicked)
        button_box.pack_start(display_button, False, False, 0)
        
        self.connect("destroy", Gtk.main_quit)
        self.show_all()
    
    def on_camera_clicked(self, button):
        os.system("touch /tmp/TSN_demo_camera_mode.flag")
        subprocess.Popen(["python3", "/opt/gopoint-apps/scripts/communication/TSN-Qbv/start_demo.py"])
        Gtk.main_quit()
    
    def on_display_clicked(self, button):
        os.system("touch /tmp/TSN_demo_display_mode.flag")
        subprocess.Popen(["python3", "/opt/gopoint-apps/scripts/communication/TSN-Qbv/start_demo.py"])
        Gtk.main_quit()


if __name__ == "__main__":
    result = subprocess.run(
        ["systemctl", "is-active", "weston"],
        capture_output=True,
        text=True
    )
    active_weston = result.stdout.strip() == "active"

    if active_weston:
        window = CaseSelectorWindow()
        Gtk.main()
    else:
        print("Weston is not running. The only available case is camera mode.")
        if "yes" == input('Type "yes" to start: '):
            print("Demo is starting in background in camera mode...")
            os.system("sh /opt/gopoint-apps/scripts/communication/TSN-Qbv/case_selector_camera_no_gui.sh &")
            time.sleep(2)
        else:
            print("Demo not started. Goodbye!")