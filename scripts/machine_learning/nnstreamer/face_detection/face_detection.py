#!/usr/bin/env python3

"""
Copyright 2024-2026 NXP

SPDX-License-Identifier: BSD-3-Clause

This script launches the Face Detection NNStreamer example using a UI to pick settings.
"""

import os
import sys
import threading
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
    """The GUI window for the Face Detection example launcher"""

    def __init__(self):
        """Creates the UI window"""

        # Obtain GUI settings and configurations
        glade_file = (
            "/opt/gopoint-apps/"
            "scripts/machine_learning/nnstreamer/face_detection/face_detection.glade"
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

        # Get platform
        self.platform = subprocess.check_output(
            ["cat", "/sys/devices/soc0/soc_id"]
        ).decode("utf-8")[:-1]

        # General variables
        self.tflite_model = "ultraface_slim_uint8_float32.tflite"
        self.npu_tflite_model = (
            "ultraface_slim_uint8_float32.tflite"
        )
        self.neutron_tflite_model = "ultraface_slim_uint8_float32_neutron.tflite"
        self.vela_tflite_model = (
            MODELS_PATH
            + "ultraface_slim_uint8_float32_vela.tflite"
        )

        # Progress bar config
        self.pulsing = False
        self.timeout_id = None
        self.progress_bar.set_show_text(False)

        # Get main application window
        window = self.builder.get_object("main-window")

        # Main process for nnstreamer example
        self.output_process = None

        # OpenVX graph caching is not available on i.MX 8QuadMax platform.
        if self.platform == "i.MX8MP":
            os.environ["VIV_VX_CACHE_BINARY_GRAPH_DIR"] = "/opt/gopoint-apps/downloads"
            os.environ["VIV_VX_ENABLE_CACHE_GRAPH_BINARY"] = "1"

        # Obtain available devices
        # get_video_devices() is used instead of globbing /dev/video* because not
        # every node can capture. A USB webcam adds a metadata-only node, and the
        # i.MX ISI capture node exists even when no sensor is fitted; selecting
        # either one makes the pipeline fail at start-up. The list is sorted too,
        # so entry 0 is the lowest numbered usable camera rather than whatever
        # order the directory happened to return.
        devices = []
        for device in utils.get_video_devices():
            self.sources_list.append_text(device)
            devices.append(device)
        if devices:
            self.sources_list.set_active(0)

        if (
            self.platform in ("i.MX8MP", "i.MX8MM", "i.MX8QM")
            and "/dev/video3" in devices
        ):
            # Look the index up instead of assuming /dev/video3 is the
            # fourth entry. Unusable nodes are filtered out now, so its position
            # in the combo box no longer matches the number in its name.
            self.sources_list.set_active(devices.index("/dev/video3"))
        
        # Only offer the MIPI-CSI sensor if it is actually in the device tree.
        # soc_id cannot tell an EVK with an OS08A20 fitted from an FRDM-IMX95
        # with no camera at all - both report i.MX95 - so gating on the
        # platform alone put an unusable entry in the list and preselected it.
        self.os08a20_path = utils.get_os08a20_device_path()
        if self.platform == "i.MX95" and self.os08a20_path is not None:
            devices.append("OS08A20")
            self.sources_list.append_text("OS08A20")
            self.sources_list.set_active(len(devices) - 1)

        # Populate backends
        backends = []
        if self.platform in ("i.MX93", "i.MX95", "i.MX8MP"):
            backends.append("NPU")
        backends.append("CPU")
        for backend in backends:
            self.backend_list.append_text(backend)
        # Add GPU option for i.MX8
        if self.platform in ("i.MX8MP", "i.MX8MN", "i.MX8QM", "i.MX95"):
            self.backend_list.append_text("GPU")
        self.backend_list.set_active(0)

        # Populate resolution from what the selected camera actually supports,
        # rather than offering a fixed list every camera is assumed to do. A
        # hardcoded entry fails with "not-negotiated" on Start whenever the
        # sensor cannot deliver it, and the user gets no hint why.
        self.sources_list.connect("changed", self.on_source_changed)
        self.populate_resolutions()

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

    # Modes offered when the camera's caps cannot be read, e.g. when the
    # GStreamer python bindings are missing or the source is the libcamera
    # OS08A20 rather than a V4L2 node.
    FALLBACK_RESOLUTIONS = ["1920x1080@30", "640x480@30"]

    def populate_resolutions(self):
        """Fills the resolution combo box from the selected camera's caps."""
        device = self.sources_list.get_active_text()
        resolutions = []
        if device and device.startswith("/dev/"):
            resolutions = utils.get_video_resolutions(device)
        if not resolutions:
            resolutions = self.FALLBACK_RESOLUTIONS

        self.resolution_list.remove_all()
        for resolution in resolutions:
            self.resolution_list.append_text(resolution)
        self.resolution_list.set_active(0)

    def on_source_changed(self, widget):
        """Repopulates the resolutions when the user picks another camera.

        Without this the list would keep describing whichever camera happened
        to be selected when the window opened.
        """
        self.populate_resolutions()

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
        if not os.path.exists(self.vela_tflite_model):
            GLib.idle_add(
                self.status_bar.set_text,
                "Compiling model with vela and saving to cache...",
            )

            subprocess.run(
                "vela "
                + self.npu_tflite_model
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
        self.tflite_model = utils.download_file(self.tflite_model)

        # Verify if download is successfull
        if self.tflite_model == -1:
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.tflite_model == -2:
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.tflite_model == -3:
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
        self.npu_tflite_model = utils.download_file(self.npu_tflite_model)

        # Verify if download is successfull
        if self.npu_tflite_model == -1:
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.npu_tflite_model == -2:
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.npu_tflite_model == -3:
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /opt/gopoint-apps/downloads and try to download again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return

        GLib.idle_add(self.status_bar.set_text, "NPU model successfully downloaded!")

        if self.platform == "i.MX95":
            GLib.idle_add(self.status_bar.set_text, "Downloading NPU model...")

            self.neutron_tflite_model = utils.download_file(self.neutron_tflite_model)

            # Verify if download is successfull
            if self.neutron_tflite_model == -1:
                GLib.idle_add(
                    self.status_bar.set_text,
                    "Cannot find files!\n"
                    "Make sure required files are available in downloads database!",
                )
                self.pulsing = False
                self.unblock_buttons(True)
                return
            if self.neutron_tflite_model == -2:
                GLib.idle_add(
                    self.status_bar.set_text,
                    "Download failed!\n"
                    "Please make sure you have internet connection on the target and try again.",
                )
                self.pulsing = False
                self.unblock_buttons(True)
                return
            if self.neutron_tflite_model == -3:
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
                + self.npu_tflite_model
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

    def start(self, widget):
        """Read UI options on the main thread, then launch the demo in a worker thread.

        GTK is not thread-safe, so all widget access (reading combo box values and
        toggling sensitivity) must happen on the main GTK thread. Only the blocking
        subprocess launch is offloaded to a background thread.
        """
        self.unblock_buttons(False)

        self.status_bar.set_text("Running Face Detection...")

        # Get options from user (must be read on the main thread)
        device = self.sources_list.get_active_text()
        backend = self.backend_list.get_active_text()
        color = self.color_list.get_active_text()
        performance_display = self.display_performance.get_active()
        resolution = self.resolution_list.get_active_text()

        if device is None:
            # The source list can legitimately be empty now. get_video_devices()
            # hides nodes that cannot capture, so a board with no sensor fitted
            # lists nothing at all instead of offering a node that always fails.
            # Report that and hand the controls back rather than building a
            # command line out of None, which raises in the worker thread.
            self.status_bar.set_text(
                "No usable camera found! Connect a camera and restart the demo."
            )
            self.unblock_buttons(True)
            return True

        self._start_worker(device, backend, color, performance_display, resolution)
        return True

    @threaded
    def _start_worker(self, device, backend, color, performance_display, resolution):
        """Build the pipeline and launch the nnstreamer process off the main thread."""
        # Configure arguments
        model = self.npu_tflite_model
        normalization = ""
        display = ""
        graph_path = ""
        cam_op = ""
        res = ""
        env = os.environ.copy()
        if backend == "GPU":
            model = self.tflite_model
        if self.platform == "i.MX95" and backend == "NPU":
            model = self.neutron_tflite_model
        if backend == "NPU" and self.platform == "i.MX93":
            model = self.vela_tflite_model
        if performance_display:
            display = " -d "
        if color == "white":
            color = ""
        else:
            color = " -t" + color
        if self.platform == "i.MX8MP" and backend != "CPU":
            graph_path = " -g /opt/gopoint-apps/downloads"
        # Parse whatever the drop-down holds. Testing against one literal and
        # falling back to 640x480 silently ignored every other entry, which
        # made the list itself untrustworthy. In object_detection.py the tested
        # literal was not even in the list, so the branch could never run.
        width, height, fps = utils.parse_resolution(resolution)
        res = " -r {},{},{} ".format(width, height, fps)
        
        if device != "OS08A20":
            cam_op = " -c " + device
        else:
            env["CAMERA_BACKEND"]="libcamera"
            env["LIBCAMERA_PIPELINES_MATCH_LIST"]="nxp/neo,imx8-isi,simple"
            # Discovered at runtime: the sensor's i2c bus differs between
            # device trees, so a hardcoded path breaks on valid configurations.
            env["LIBCAMERA_CAM_DEVICE"]=self.os08a20_path
            env["LIBCAMERA_IPA_MODULE_PATH"]="/usr/lib/libcamera/ipa"
            res = " -r 1920,1080,60 "


        pipeline = (
            "/opt/gopoint-apps/scripts/machine_learning/nnstreamer/face_detection/example_face_detection_tflite"
            + cam_op
            + " -b "
            + backend
            + " -p "
            + model
            + display
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
            env=env
        )

        return True


if __name__ == "__main__":
    win = NNStreamerLauncher()
    gtk.main()
