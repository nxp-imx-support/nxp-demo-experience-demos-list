#!/usr/bin/env python3

"""
Copyright 2024-2026 NXP

SPDX-License-Identifier: BSD-3-Clause

This script launches the Pose and Face Detection NNStreamer example using a UI to pick settings.
"""

import os
import sys
import threading
import glob
import subprocess
import time
import gi

# Check for correct Gtk version
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk
from gi.repository import GLib

# Import utils
sys.path.append("/opt/gopoint-apps/scripts/")
import utils

MODELS_PATH = "/opt/gopoint-apps/downloads/"


def threaded(fn):
    """
    Handle threads out of main GTK thread
    """

    def wrapper(*args, **kwargs):
        threading.Thread(target=fn, args=args, kwargs=kwargs).start()

    return wrapper


class NNStreamerLauncher:
    """The GUI window for the Emotion Detection example launcher"""

    def __init__(self):
        """Creates the UI window"""

        # Obtain GUI settings and configurations
        glade_file = (
            "/opt/gopoint-apps/"
            "scripts/machine_learning/nnstreamer/pose_face/pose_face.glade"
        )
        self.builder = gtk.Builder()
        self.builder.add_from_file(glade_file)
        self.builder.connect_signals(self)

        # Create instances of widgets
        self.sources_list = self.builder.get_object("sources-list")
        self.backend_list = self.builder.get_object("backend-list")
        self.resolution_list = self.builder.get_object("resolution-list")
        self.color_list = self.builder.get_object("color-list")
        self.display_performance = self.builder.get_object("display-performance")
        self.start_button = self.builder.get_object("start-button")
        self.header_bar = self.builder.get_object("header-bar")
        self.status_bar = self.builder.get_object("status-bar")
        self.about_button = self.builder.get_object("about-button")
        self.about_dialog = self.builder.get_object("about-dialog")
        self.progress_bar = self.builder.get_object("progress-bar")
        self.close_button = self.builder.get_object("close-button")

        # General variables
        self.tflite_model_a = "ultraface_slim_uint8_float32.tflite"
        self.tflite_npu_model_a = (
            "ultraface_slim_uint8_float32.tflite"
        )
        self.tflite_vela_model_a = (
            MODELS_PATH
            + "ultraface_slim_uint8_float32_vela.tflite"
        )
        self.tflite_model_b = "movenet_quant.tflite"
        self.npu_tflite_model_b = (
            "movenet_quant.tflite"
        )
        self.vela_tflite_model_b = (
            MODELS_PATH
            + "movenet_quant_vela.tflite"
        )


        # Progress bar config
        self.pulsing = False
        self.timeout_id = None
        self.progress_bar.set_show_text(False)

        # Get main application window
        window = self.builder.get_object("main-window")

        # Main process for nnstreamer example
        self.output_process = None

        # Get platform
        self.platform = subprocess.check_output(
            ["cat", "/sys/devices/soc0/soc_id"]
        ).decode("utf-8")[:-1]

        # OpenVX graph caching is not available on i.MX 8QuadMax platform.
        if self.platform == "i.MX8MP":
            os.environ["VIV_VX_CACHE_BINARY_GRAPH_DIR"] = "/opt/gopoint-apps/downloads"
            os.environ["VIV_VX_ENABLE_CACHE_GRAPH_BINARY"] = "1"

        # Obtain available devices
        devices = []
        for device in glob.glob("/dev/video*"):
            self.sources_list.append_text(device)
            devices.append(device)
        self.sources_list.set_active(0)

        if (
            self.platform in ("i.MX8MP", "i.MX8MM", "i.MX8QM")
            and "/dev/video3" in devices
        ):
            self.sources_list.set_active(3)

        if self.platform in ("i.MX95"):
            devices.append("OS08A20")
            self.sources_list.append_text("OS08A20")
            self.sources_list.set_active(len(devices) - 1)

        # Populate backends
        backends = []
        if self.platform in ("i.MX8MP"):
            backends.append("NPU")
        backends.append("CPU")
        for backend in backends:
            self.backend_list.append_text(backend)
        # Add GPU option for i.MX8
        if self.platform in ("i.MX8MP", "i.MX8MN", "i.MX8QM"):
            self.backend_list.append_text("GPU")
        self.backend_list.set_active(0)

        # Populate resolution for video
        resolutions = ["1920x1080@30", "640x480@30"]
        for resolution in resolutions:
            self.resolution_list.append_text(resolution)
        self.resolution_list.set_active(0)

        colors = ["white", "red", "green", "blue", "black"]
        for color in colors:
            self.color_list.append_text(color)
        self.color_list.set_active(0)

        self.close_button.connect("clicked", self.quit_app)
        window.connect("delete-event", gtk.main_quit)
        window.show()

        # Preload model
        preload_thread = threading.Thread(target=self.preload, daemon=True)
        preload_thread.start()

    def quit_app(self, widget):
        """Closes GTK+3 GUI and kills NNStreamer process"""
        if self.output_process:
            self.output_process.kill()
        gtk.main_quit()

    def about_button_activate(self, widget):
        """
        Function to handle about dialog window
        """
        self.about_dialog.run()
        time.sleep(1)
        self.about_dialog.hide()
        return True

    def on_timeout(self):
        """
        Function to handle progress bar
        """
        if self.pulsing:
            self.progress_bar.set_show_text(True)
            self.progress_bar.pulse()
            return True
        self.progress_bar.set_show_text(False)
        self.progress_bar.set_fraction(0.0)
        return False

    def compile_vela(self):
        """Compile vela models"""
        if not os.path.exists(self.tflite_vela_model_a):
            GLib.idle_add(
                self.status_bar.set_text,
                "Compiling model with vela and saving to cache...",
            )

            subprocess.run(
                "vela "
                + self.tflite_npu_model_a
                + " --output-dir=/opt/gopoint-apps/downloads/",
                shell=True,
                check=True,
            )
        if not os.path.exists(self.vela_tflite_model_b):
            GLib.idle_add(
                self.status_bar.set_text,
                "Compiling model with vela and saving to cache...",
            )

            subprocess.run(
                "vela "
                + self.npu_tflite_model_b
                + " --output-dir=/opt/gopoint-apps/downloads/",
                shell=True,
                check=True,
            )

    def preload(self):
        """Download the models, compile the models and setup default configuration"""

        # Block run button and start progress bar
        self.unblock_buttons(False)
        self.pulsing = True
        self.timeout_id = GLib.timeout_add(50, self.on_timeout)

        GLib.idle_add(self.status_bar.set_text, "Downloading CPU model...")
        self.tflite_model_a = utils.download_file(self.tflite_model_a)

        # Verify if download is successfull
        if self.tflite_model_a == -1:
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.tflite_model_a == -2:
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.tflite_model_a == -3:
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /opt/gopoint-apps/downloads and try to download again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return

        GLib.idle_add(self.status_bar.set_text, "CPU model successfully downloaded!")

        GLib.idle_add(self.status_bar.set_text, "Downloading NPU model...")
        self.tflite_npu_model_a = utils.download_file(self.tflite_npu_model_a)

        # Verify if download is successfull
        if self.tflite_npu_model_a == -1:
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.tflite_npu_model_a == -2:
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.tflite_npu_model_a == -3:
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /opt/gopoint-apps/downloads and try to download again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return

        GLib.idle_add(self.status_bar.set_text, "NPU model successfully downloaded!")

        GLib.idle_add(self.status_bar.set_text, "Downloading CPU model...")
        self.tflite_model_a = utils.download_file(self.tflite_model_b)

        # Verify if download is successfull
        if self.tflite_model_a == -1:
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.tflite_model_a == -2:
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.tflite_model_a == -3:
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /opt/gopoint-apps/downloads and try to download again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return

        GLib.idle_add(self.status_bar.set_text, "CPU model successfully downloaded!")
        

        GLib.idle_add(self.status_bar.set_text, "Downloading NPU model...")
        self.npu_tflite_model_b = utils.download_file(self.npu_tflite_model_b)

        # Verify if download is successfull
        if self.npu_tflite_model_b == -1:
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.npu_tflite_model_b == -2:
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.npu_tflite_model_b == -3:
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /opt/gopoint-apps/downloads and try to download again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return

        GLib.idle_add(self.status_bar.set_text, "NPU model successfully downloaded!")

        # Compile model using vela tool for i.MX 93
        if self.platform == "i.MX93":
            self.compile_vela()

        # If i.MX 8M PLus, pre-run model to avoid warmup time during execution
        if self.platform == "i.MX8MP":
            GLib.idle_add(
                self.status_bar.set_text,
                "Warming up model and saving to cache...",
            )

            subprocess.run(
                "/usr/bin/tensorflow-lite-*/examples/benchmark_model "
                "--graph="
                + self.tflite_npu_model_a
                + " --external_delegate_path=/usr/lib/libvx_delegate.so",
                shell=True,
                check=True,
            )

            subprocess.run(
                "/usr/bin/tensorflow-lite-*/examples/benchmark_model "
                "--graph="
                + self.npu_tflite_model_b
                + " --external_delegate_path=/usr/lib/libvx_delegate.so",
                shell=True,
                check=True,
            )

        self.pulsing = False
        GLib.idle_add(self.status_bar.set_text, "Application is ready!")
        self.unblock_buttons(True)

    def unblock_buttons(self, status):
        """Block/unblock buttons"""
        self.start_button.set_sensitive(status)
        self.sources_list.set_sensitive(status)
        self.backend_list.set_sensitive(status)
        self.resolution_list.set_sensitive(status)
        self.color_list.set_sensitive(status)
        self.display_performance.set_sensitive(status)

    @threaded
    def start(self, widget):
        """Start the nnstreamer demo"""
        self.unblock_buttons(False)

        GLib.idle_add(
            self.status_bar.set_text,
            "Running Pose/Face...",
        )

        # Get options from user
        device = self.sources_list.get_active_text()
        backend = self.backend_list.get_active_text() + "," + self.backend_list.get_active_text()
        color = self.color_list.get_active_text()
        performance_display = self.display_performance.get_active()

        # Configure arguments
        model = self.tflite_npu_model_a + "," + self.npu_tflite_model_b
        normalization = ""
        display = ""
        graph_path = ""
        cam_op = ""
        res = ""
        env = os.environ.copy()
        if backend in ("GPU"):
            normalization = " -n castInt32,castInt32"
            model = self.tflite_model_a + "," + self.tflite_model_b
        elif backend == "NPU" and self.platform == "i.MX93":
            model = self.tflite_vela_model_a + "," + self.vela_tflite_model_b
        if performance_display:
            display = " -d "
        if color == "white":
            color = ""
        else:
            color = " -t" + color
        if self.platform == "i.MX8MP" and backend != "CPU":
            graph_path = " -g /opt/gopoint-apps/downloads"
        if self.resolution_list.get_active_text() == "1920x1080@30":
            res = " -r 1920,1080,30 "
        else:
            res = " -r 640,480,30 "
        
        if device != "OS08A20":
            cam_op = " -c " + device
        else:
            env["CAMERA_BACKEND"]="libcamera"
            env["LIBCAMERA_PIPELINES_MATCH_LIST"]="nxp/neo,imx8-isi,simple"
            env["LIBCAMERA_CAM_DEVICE"]="/base/soc/bus@42000000/i2c@42540000/os08a20_mipi@36"
            env["LIBCAMERA_IPA_MODULE_PATH"]="/usr/lib/libcamera/ipa"
        pipeline = (
            "/opt/gopoint-apps/scripts/machine_learning/nnstreamer/pose_face/example_face_and_pose_detection_tflite"
            + cam_op
            + " -b "
            + backend
            + " -p "
            + model
            + display
            + normalization
            + graph_path
            + color
            + res
        )

        self.output_process = subprocess.Popen(
            pipeline,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )

        return True


if __name__ == "__main__":
    win = NNStreamerLauncher()
    gtk.main()
