#!/usr/bin/env python3

"""
Copyright 2021-2024 NXP

SPDX-License-Identifier: BSD-2-Clause

This script launches the NNStreamer ML Demos using a UI to pick settings.
"""

import os
import sys
import threading
import glob
import subprocess
import gi
import signal

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gio

sys.path.append("/home/root/.nxp-demo-experience/scripts/")
import utils


class MLLaunch(Gtk.Window):
    """The GUI window for the ML demo launcher"""

    def __init__(self, demo):
        """Creates the UI window"""
        # Initialization
        self.demo = demo
        super().__init__(title=demo)
        self.set_default_size(450, 200)
        self.set_resizable(False)
        self.output_process = 0

        signal.signal(signal.SIGINT, self.exit)
        signal.signal(signal.SIGTERM, self.exit)

        # Get platform
        self.platform = subprocess.check_output(
            ["cat", "/sys/devices/soc0/soc_id"]
        ).decode("utf-8")[:-1]

        # OpenVX graph caching is not available on i.MX 8QuadMax platform.
        if self.platform != ("i.MX8QM", "i.MX93", "i.MX95"):
            os.environ["VIV_VX_CACHE_BINARY_GRAPH_DIR"] = "/home/root/.cache/gopoint"
            os.environ["VIV_VX_ENABLE_CACHE_GRAPH_BINARY"] = "1"

        # Get widget properties
        devices = []
        if self.demo == "pose":
            if self.platform != "i.MX93":
                devices.append("Example Video")

        for device in glob.glob("/dev/video*"):
            devices.append(device)

        backends_available = ["CPU"]
        if os.path.exists("/usr/lib/libvx_delegate.so") and self.demo != "pose":
            backends_available.insert(1, "GPU")
        if (
            os.path.exists("/usr/lib/libtim-vx.so")
            and self.demo != "brand"
            and self.platform != "i.MX8QM"
        ):
            backends_available.insert(0, "NPU")
        if os.path.exists("/usr/lib/libethosu_delegate.so"):
            backends_available.insert(0, "NPU")
            #backends_available.pop()

        displays_available = ["Weston"]

        # Create widgets
        main_grid = Gtk.Grid.new()
        device_label = Gtk.Label.new("Source")
        self.device_combo = Gtk.ComboBoxText()
        backend_label = Gtk.Label.new("Backend")
        self.backend_combo = Gtk.ComboBoxText()
        self.display_combo = Gtk.ComboBoxText()
        self.launch_button = Gtk.Button.new_with_label("Run")
        self.status_bar = Gtk.Label.new()
        header = Gtk.HeaderBar()
        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        self.width_entry = self.r_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 300, 1920, 2
        )
        self.height_entry = self.r_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 300, 1080, 2
        )
        self.fps_entry = self.r_scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 1, 60, 1
        )
        self.width_label = Gtk.Label.new("Width")
        self.height_label = Gtk.Label.new("Height")
        self.fps_label = Gtk.Label.new("FPS")
        self.update_time = None

        # Organize widgets
        self.add(main_grid)
        self.set_titlebar(header)

        quit_button.add(quit_image)
        header.pack_end(quit_button)

        main_grid.set_row_spacing(10)
        main_grid.set_border_width(10)

        main_grid.attach(device_label, 0, 1, 2, 1)
        device_label.set_hexpand(True)
        main_grid.attach(backend_label, 0, 2, 2, 1)
        if(self.demo != "pose"):
            main_grid.attach(self.width_label, 0, 4, 2, 1)
            main_grid.attach(self.height_label, 0, 5, 2, 1)
            main_grid.attach(self.fps_label, 0, 6, 2, 1)

        main_grid.attach(self.device_combo, 2, 1, 2, 1)
        self.device_combo.set_hexpand(True)
        main_grid.attach(self.backend_combo, 2, 2, 2, 1)
        if(self.demo != "pose"):
            main_grid.attach(self.width_entry, 2, 4, 2, 1)
            main_grid.attach(self.height_entry, 2, 5, 2, 1)
            main_grid.attach(self.fps_entry, 2, 6, 2, 1)

        main_grid.attach(self.launch_button, 0, 7, 4, 1)
        main_grid.attach(self.status_bar, 0, 8, 4, 1)

        # Configure widgets
        for device in devices:
            self.device_combo.append_text(device)
        for backend in backends_available:
            self.backend_combo.append_text(backend)
        for display in displays_available:
            self.display_combo.append_text(display)

        self.device_combo.set_active(0)
        self.backend_combo.set_active(0)
        self.display_combo.set_active(0)

        self.width_entry.set_value(640)
        self.height_entry.set_value(480)
        self.fps_entry.set_value(30)

        self.device_combo.connect("changed", self.on_source_change)
        self.launch_button.connect("clicked", self.start)
        quit_button.connect("clicked", self.but_exit)
        if self.demo == "detect":
            header.set_title("Object Detection")
        elif self.demo == "id":
            header.set_title("Image Classification")
        elif self.demo == "pose":
            header.set_title("Pose Estimation")
        elif self.demo == "brand":
            header.set_title("Brand Demo")
        else:
            header.set_title("NNStreamer Demo")
        header.set_subtitle("NNStreamer Examples")

    def start(self, button):
        """Starts the ML Demo with selected settings"""
        self.update_time = GLib.get_monotonic_time()
        self.launch_button.set_sensitive(False)
        if self.demo == "detect":
            backend = self.backend_combo.get_active_text()
            if backend != "NPU":
                model = utils.download_file(
                    "ssdlite_mobilenet_v2_coco_no_postprocess.tflite"
                )
            else:
                model = utils.download_file(
                    "ssdlite_mobilenet_v2_coco_quant_uint8_float32_no_postprocess.tflite"
                )
                if self.platform == "i.MX93":
                    model = self.compile_vela(model)
            labels = utils.download_file("coco_labels_list.txt")
            box = utils.download_file("box_priors.txt")
            device = self.device_combo.get_active_text()
        if self.demo == "id":
            backend = self.backend_combo.get_active_text()
            if backend != "NPU":
                model = utils.download_file(
                    "mobilenet_v1_1.0_224.tflite"
                )
            else:
                model = utils.download_file(
                    "mobilenet_v1_1.0_224_quant_uint8_float32.tflite"
                )
                if self.platform == "i.MX93":
                    model = self.compile_vela(model)
            labels = utils.download_file("labels_mobilenet_quant_v1_224.txt")
            box = 0
            device = self.device_combo.get_active_text()
        if self.demo == "pose":
            backend = self.backend_combo.get_active_text()
            if backend != "NPU":
                model = utils.download_file(
                    "movenet_single_pose_lightning.tflite"
                )
            else:
                model = utils.download_file(
                    "movenet_quant.tflite"
                )
                if self.platform == "i.MX93":
                    model = self.compile_vela(model)
            labels = 0
            box = 0
            device = self.device_combo.get_active_text()
            if device == "Example Video":
                device = utils.download_file(
                    "Conditioning_Drill_1-_Power_Jump.webm.480p.vp9.webm"
                )

        if model == -1 or labels == -1 or device == -1 or box == -1:
            self.status_bar.set_text("Cannot find files!")
            self.launch_button.set_sensitive(True)
            return

        if model == -2 or labels == -2 or device == -2 or box == -2:
            self.status_bar.set_text("Download failed!")
            self.launch_button.set_sensitive(True)
            return

        if model == -3 or labels == -3 or device == -3 or box == -3:
            self.status_bar.set_text("Downloaded bad file!")
            self.launch_button.set_sensitive(True)
            return

        if self.demo == "detect":
            command = "CAMERA_WIDTH=\"" + str(int(self.width_entry.get_value())) + "\" "
            command += "CAMERA_HEIGHT=\"" + str(int(self.height_entry.get_value())) + "\" "
            command += "CAMERA_FPS=\"" + str(int(self.fps_entry.get_value())) + "\" "
            command += "BACKEND=\"" + self.backend_combo.get_active_text() + "\" "
            command += "CAMERA_DEVICE=\"" + device + "\" "
            command += ("/home/root/.nxp-demo-experience/scripts/machine_learning/"
                       "nnstreamer/detection/example_detection_mobilenet_ssd_v2_tflite.sh")
            self.output_process = subprocess.Popen(
                command,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8"
            )
        if self.demo == "id":
            command = "CAMERA_WIDTH=\"" + str(int(self.width_entry.get_value())) + "\" "
            command += "CAMERA_HEIGHT=\"" + str(int(self.height_entry.get_value())) + "\" "
            command += "CAMERA_FPS=\"" + str(int(self.fps_entry.get_value())) + "\" "
            command += "BACKEND=\"" + self.backend_combo.get_active_text() + "\" "
            command += "CAMERA_DEVICE=\"" + device + "\" "
            command += ("/home/root/.nxp-demo-experience/scripts/machine_learning/"
                       "nnstreamer/classification/example_classification_mobilenet_v1_tflite.sh")
            self.output_process = subprocess.Popen(
                command,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8"
            )
        if self.demo == "pose":
            command = "BACKEND=\"" + self.backend_combo.get_active_text() + "\" "
            command += "CAMERA_DEVICE=\"" + device + "\" "
            if(device.startswith("/dev/")):
                command += "SOURCE=CAMERA "
            else:
                command += "SOURCE=VIDEO "
            command += ("/home/root/.nxp-demo-experience/scripts/machine_learning/"
                       "nnstreamer/pose/example_pose_movenet_tflite.py")
            self.output_process = subprocess.Popen(
                command,
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8"
            )
        self.launch_button.set_sensitive(True)
    
    def status_update(self, pros):
        GLib.idle_add(
                self.launch_button.set_sensitive, False
            )
        GLib.idle_add(
                self.status_bar.set_text, "Running..."
            )
        pros.wait()
        GLib.idle_add(
                self.status_bar.set_text, "Script Stopped"
            )
        GLib.idle_add(
                self.launch_button.set_sensitive, True
            )

    def on_source_change(self, widget):
        """Callback to lock sliders"""
        if self.device_combo.get_active_text() == "Example Video":
            self.width_entry.set_value(1920)
            self.height_entry.set_value(1080)
            self.width_entry.set_sensitive(False)
            self.height_entry.set_sensitive(False)
        else:
            self.width_entry.set_sensitive(True)
            self.height_entry.set_sensitive(True)

    def compile_vela(self, model):
        """Compile vela models"""
        vela_model = self.vela_name(model)
        if not os.path.exists(vela_model):
            GLib.idle_add(
                self.status_bar.set_text,
                "Compiling model with vela and saving to cache...",
            )

            subprocess.run(
                "vela " + model + " --output-dir=/home/root/.cache/gopoint/",
                shell=True,
                check=True,
            )

        return vela_model

    def vela_name(self, model_name):
        """
        Appends the vela label to model name
        """
        tokens = model_name.split(".tflite")
        return (
            "/home/root/.cache/gopoint/" + (tokens[-2] + "_vela.tflite").split("/")[-1]
        )
    
    def but_exit(self, unused):
        self.exit(None,None)

    def exit(self, unused, unused2):
        if(self.output_process != 0):
            if(self.demo == "pose"):
                self.output_process.kill()
            else:
                subprocess.run("pkill gst-launch-1.0",
                shell=True)
        exit()


if __name__ == "__main__":
    if (
        len(sys.argv) != 2
        and sys.argv[1] != "detect"
        and sys.argv[1] != "id"
        and sys.argv[1] != "pose"
    ):
        print("Demos available: detect, id, pose")
    else:
        win = MLLaunch(sys.argv[1])
        win.connect("destroy", Gtk.main_quit)
        win.show_all()
        Gtk.main()