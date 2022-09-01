"""
Video Test Demo.

Copyright 2022 NXP Semiconductors
SPDX-License-Identifier: BSD-3-Clause

This demo is meant for users to try out cameras and displays connected to a
board. This simple UI allows for different cameras to be selected, or if no
camera is selected, users can use a test source.
"""
import glob
import threading
import subprocess
import os

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio, GLib

def run_pipeline(pipeline, type):
    """Run the pipeline the user selects."""
    subprocess.run(pipeline.split(' '))

class MainWindow(Gtk.Window):
    """Main UI window."""

    def __init__(self):
        """Create the UI window."""
        super().__init__()
        self.set_default_size(450, 200)
        self.set_resizable(False)
        self.set_border_width(10)
        main_grid = Gtk.Grid(
            row_homogeneous=True, column_spacing=15, row_spacing=15)
        main_grid.set_margin_end(10)
        main_grid.set_margin_start(10)

        header = Gtk.HeaderBar()
        header.set_title("Video Test Demo")
        header.set_subtitle("GStreamer Demos")
        self.set_titlebar(header)

        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        header.pack_end(quit_button)
        quit_button.connect("clicked", self.on_exit)

        source_label = Gtk.Label(
            label="Source"
        )

        self.devices = ["Test Source"]
        for device in glob.glob('/dev/video*'):
            self.devices.append(device)
        self.source_select = Gtk.ComboBoxText()
        for option in self.devices:
            self.source_select.append_text(option)
        self.source_select.set_active(0)
        self.source_select.set_hexpand(True)

        resolution_label = Gtk.Label(
            label="Resolution"
        )

        resolutions = ["3840x2160", "2560x1440", "1920x1080",
        "1280x720", "800x600", "720x480"]
        self.resolution_select = Gtk.ComboBoxText()
        for res in resolutions:
            self.resolution_select.append_text(res)
        self.resolution_select.set_active(2)

        self.scale_check = Gtk.CheckButton.new_with_label("Scale to output")

        quit_label = Gtk.Label(
            label="Once started, users may stop the video feed using the\n"
            "quit button in this window. Playback windows can be dragged\n"
            "with the mouse."
        )

        self.launch_button = Gtk.Button.new_with_label("Run")
        self.launch_button.connect("clicked", self.on_start)

        main_grid.attach(source_label, 0, 0, 1, 1)
        main_grid.attach(self.source_select, 1, 0, 1, 1)
        main_grid.attach(resolution_label, 0, 1, 1, 1)
        main_grid.attach(self.resolution_select, 1, 1, 1, 1)
        main_grid.attach(self.scale_check, 0, 2, 2, 1)
        main_grid.attach(quit_label, 0, 3, 2, 1)
        main_grid.attach(self.launch_button, 0, 4, 2, 1)

        self.add(main_grid)

    def on_start(self, widget):
        self.source_select.set_sensitive(False)
        self.resolution_select.set_sensitive(False)
        self.scale_check.set_sensitive(False)
        self.launch_button.set_sensitive(False)
        """Set up and start the pipeline."""
        source = self.source_select.get_active_text()
        if source == "Test Source":
            source = "videotestsrc"
        else:
            source = "v4l2src device=" + source
        resolution = self.resolution_select.get_active_text()
        width = resolution[:resolution.find("x")]
        height = resolution[resolution.find("x")+1:]
        format = "video/x-raw,width=" + width + ",height=" + height
        if self.scale_check.get_active():
            sink = "waylandsink"
        else:
            sink = (
                "waylandsink window-width=" + width + " window-height=" +
                height)
        pipeline = "gst-launch-1.0 " + source + " ! " + format + " ! " + sink
        stream_thread = threading.Thread(
            target=run_pipeline, args=(pipeline,"gstreamer"))
        stream_thread.start()
        if source != "videotestsrc":
            index = self.devices.index(self.source_select.get_active_text())
            self.devices.remove(self.devices[index])
            self.source_select.remove(index)
            self.source_select.set_active(0)
        self.source_select.set_sensitive(True)
        self.resolution_select.set_sensitive(True)
        self.scale_check.set_sensitive(True)
        self.launch_button.set_sensitive(True)
    
    def on_exit(self, widget):
        subprocess.run(["pkill", "-P", str(os.getpid())])
        Gtk.main_quit()

if __name__ == "__main__":
    main_window = MainWindow()
    main_window.show_all()
    Gtk.main()
