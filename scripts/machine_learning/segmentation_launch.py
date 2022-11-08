#!/usr/bin/env python3

"""
Copyright 2022 NXP
SPDX-License-Identifier: Apache-2.0

Model: MediaPipe Selfie Segmentation
Model's License: Apache-2.0
Original model available at: https://google.github.io/mediapipe/solutions/models.html
Model Card: https://drive.google.com/file/d/1dCfozqknMa068vVsO2j_1FgZkW_e3VWv/preview

The following is a demo to show human segmentation from video.
Application could be aimed at video conference.
The original MediaPipe model was quantized using per-tensor quantization to be
accelerated by the NPU on the i.MX8M Plus EVK.
"""

import cv2
import numpy as np
import tflite_runtime.interpreter as tflite
import time

import sys
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gst, GLib, Gio

sys.path.append("/home/root/.nxp-demo-experience/scripts/")

import utils
import glob
import os
import threading

class MainWindow(Gtk.Window):
    """Main GUI window that starts the demo"""

    def __init__(self):
        """Sets up the first window to do preroll setup"""
        super().__init__()
        self.set_default_size(450, 200)
        self.set_resizable(False)
        self.set_border_width(10)
        devices = []
        for device in glob.glob('/dev/video*'):
            devices.append(device)
        backends_available = ["NPU"]

        main_grid = Gtk.Grid(
            row_homogeneous=True, column_spacing=15, row_spacing=15)
        main_grid.set_margin_end(10)
        main_grid.set_margin_start(10)

        header = Gtk.HeaderBar()
        header.set_title("i.MX Segmentation Demo")
        header.set_subtitle("i.MX Machine Learning Demos")
        self.set_titlebar(header)

        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        header.pack_end(quit_button)
        quit_button.connect("clicked", Gtk.main_quit)

        source_label = Gtk.Label.new("Source")
        source_label.set_halign(1)

        self.source_select = Gtk.ComboBoxText()
        self.source_select.set_entry_text_column(0)
        for option in devices:
            self.source_select.append_text(option)
        self.source_select.set_active(0)
        self.source_select.set_hexpand(True)

        backend_label = Gtk.Label.new("Backend")
        backend_label.set_halign(1)

        self.backend_select = Gtk.ComboBoxText()
        self.backend_select.set_entry_text_column(0)
        for option in backends_available:
            self.backend_select.append_text(option)
        self.backend_select.set_active(0)
        self.backend_select.set_hexpand(True)

        self.launch_button = Gtk.Button.new_with_label("Run")
        self.launch_button.connect("clicked", self.on_change_start)

        self.status_bar = Gtk.Label.new()

        main_grid.attach(source_label, 0, 1, 1, 1)
        #main_grid.attach(backend_label, 0, 2, 1, 1)

        main_grid.attach(self.source_select, 1, 1, 1, 1)
        #main_grid.attach(self.backend_select, 1, 2, 1, 1)

        main_grid.attach(self.launch_button, 0, 3, 2, 1)
        main_grid.attach(self.status_bar, 0, 4, 2, 1)

        self.add(main_grid)

    def on_change_start(self, widget):
        """Starts the video stream"""
        self.status_bar.set_text("Starting demo...")
        widget.set_sensitive(False)
        self.backend_select.set_sensitive(False)
        self.source_select.set_sensitive(False)
        cam_thread = threading.Thread(
            target=start_demo,
            args=(self.backend_select.get_active_text(),
                  self.source_select.get_active_text()))
        cam_thread.daemon = True
        cam_thread.start()


def start_demo(backend, camera):
    global cam
    # Get assets
    GLib.idle_add(
        main_window.status_bar.set_text, "Downloading model...")
    model_path = utils.download_file("selfie_segmentation_quant.tflite")
    if model_path == -1 or model_path == -2 or model_path == -3:
        GLib.idle_add(
            main_window.status_bar.set_text, "Download failed! " +
            "Restart demo and try again!")
        while True:
            time.sleep(9999)
    GLib.idle_add(
        main_window.status_bar.set_text, "Downloading background...")
    bg_path = utils.download_file("bg_image.jpg")
    if bg_path == -1 or bg_path == -2 or bg_path == -3:
        GLib.idle_add(
            main_window.status_bar.set_text, "Download failed! " +
            "Restart demo and try again!")
        while True:
            time.sleep(9999)
    GLib.idle_add(main_window.status_bar.set_text,
                  "Warming up backend... (can take a couple minutes)")
    # Load model and use VX delegate for acceleration
    if backend == "NPU":
        ext_delegate = tflite.load_delegate("/usr/lib/libvx_delegate.so")
        interpreter = tflite.Interpreter(
            model_path=model_path,
            num_threads=4,
            experimental_delegates=[ext_delegate])
        os.environ["VIV_VX_CACHE_BINARY_GRAPH_DIR"] = ("/home/root/.cache"
                                                       "/demoexperience")
        os.environ["VIV_VX_ENABLE_CACHE_GRAPH_BINARY"] = "1"
    else:
        interpreter = tflite.Interpreter(
            model_path=model_path, num_threads=4)
    interpreter.allocate_tensors()
    input_index = interpreter.get_input_details()[0]['index']
    input_shape = interpreter.get_input_details()[0]['shape']
    test = np.zeros(input_shape, dtype=np.float32)
    interpreter.set_tensor(input_index, test)
    interpreter.invoke()

    GLib.idle_add(
        main_window.status_bar.set_text, "Starting demo...")
    cam = int(camera[-1])
    GLib.idle_add(main_window.close)
    GLib.idle_add(Gtk.main_quit)


if __name__ == "__main__":
    cam = -1
    main_window = MainWindow()
    main_window.show_all()
    Gtk.main()
    exit(cam)


