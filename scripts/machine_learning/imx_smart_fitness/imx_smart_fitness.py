#!/usr/bin/env python3

"""
Copyright 2023-2024, 2026 NXP
SPDX-License-Identifier: Apache-2.0

This script launches the i.MX Smart Fitness demo using a GUI
"""

import os
import sys
import subprocess
import threading
import time
import gi

# Check for correct Gtk version
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk
from gi.repository import GLib

# Import utils
sys.path.append("/opt/gopoint-apps/scripts")
import utils


def threaded(fn):
    """
    Handle threads out of main GTK thread
    """

    def wrapper(*args, **kwargs):
        threading.Thread(target=fn, args=args, kwargs=kwargs).start()

    return wrapper


class ImxSmartFitness:
    """
    i.MX Smart Fitness GUI launcher
    """

    def __init__(self):
        # Obtain GUI settings and configurations
        glade_file = (
            "/opt/gopoint-apps/"
            "scripts/machine_learning/imx_smart_fitness/imx_smart_fitness.glade"
        )
        self.builder = gtk.Builder()
        self.builder.add_from_file(glade_file)
        self.builder.connect_signals(self)

        # Create instances of widgets
        self.label = self.builder.get_object("source-label")
        self.sources_list = self.builder.get_object("sources-list")
        self.run_button = self.builder.get_object("run-button")
        self.status_bar = self.builder.get_object("status-bar")
        self.about_button = self.builder.get_object("about-button")
        self.about_dialog = self.builder.get_object("about-dialog")
        self.progress_bar = self.builder.get_object("progress-bar")
        self.close_button = self.builder.get_object("close-button")

        # Progress bar config
        self.pulsing = False
        self.timeout_id = None
        self.progress_bar.set_show_text(False)

        # Get main application window
        window = self.builder.get_object("main-window")

        self.platform = None
        self.cache_enable = ""

        # Define names of models
        self.model_detection_tflite = "pose_detection_quant.tflite"
        self.model_detection_vela = "pose_detection_quant_vela.tflite"
        self.model_landmark_tflite = "pose_landmark_lite_quant.tflite"
        self.model_landmark_vela = "pose_landmark_lite_quant_vela.tflite"

        # Main process for imx_smart_fitness
        self.output_process = None

        # Check target (i.MX 8M Plus vs i.MX 93)
        if os.path.exists("/usr/lib/libvx_delegate.so"):
            self.platform = "i.MX8MP"
            self.cache_enable = (
                "VIV_VX_ENABLE_CACHE_GRAPH_BINARY='1' "
                + "VIV_VX_CACHE_BINARY_GRAPH_DIR=/opt/gopoint-apps/downloads "
            )
        elif os.path.exists("/usr/lib/libethosu_delegate.so"):
            self.platform = "i.MX93"
        else:
            print("Target is not supported!")
            sys.exit()

        # Obtain available devices
        # get_video_devices() filters out nodes that cannot capture: a USB webcam
        # adds a metadata-only node, and the i.MX ISI capture node exists even
        # when no sensor is fitted. Selecting either makes the pipeline fail at
        # start-up, so they must not appear in the list.
        devices = []
        for device in utils.get_video_devices():
            devices.append(device)

        for device in devices:
            self.sources_list.append_text(device)

        # Guard the index: set_active(-1) on an empty list clears the selection
        # instead of choosing anything, which used to hide the "no camera" case.
        if devices:
            self.sources_list.set_active(len(devices) - 1)

        self.run_button.connect("clicked", self.start)

        self.close_button.connect("clicked", self.quit_app)
        window.connect("delete-event", gtk.main_quit)
        window.show()

    def quit_app(self, widget):
        """Closes GTK+3 GUI and kills imx_smart_fitness process"""
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

    def start(self, widget):
        """Read UI options on the main thread, then run the demo in a worker thread.

        GTK is not thread-safe, so widget access must happen on the main GTK
        thread. Only the blocking work runs in the worker thread.
        """
        self.run_button.set_sensitive(False)
        self.sources_list.set_sensitive(False)

        # Get options from user (must be read on the main thread)
        device = self.sources_list.get_active_text()

        self.pulsing = True
        self.timeout_id = GLib.timeout_add(50, self.on_timeout)

        self._start_worker(device)
        return True

    @threaded
    def _start_worker(self, device):
        """Download models, warm up, and launch the fitness process off the main thread."""
        GLib.idle_add(self.status_bar.set_text, "Downloading models...")

        # Download assets
        model_detection = utils.download_file(self.model_detection_tflite)
        model_landmarks = utils.download_file(self.model_landmark_tflite)
        anchors = utils.download_file("anchors.txt")
        embeddings = utils.download_file("pose_embeddings.csv")

        # Handle errors during download if present
        if (
            model_detection == -1
            or model_landmarks == -1
            or anchors == -1
            or embeddings == -1
        ):
            self.pulsing = False
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            GLib.idle_add(self.run_button.set_sensitive, True)
            GLib.idle_add(self.sources_list.set_sensitive, True)
            return False
        if (
            model_detection == -2
            or model_landmarks == -2
            or anchors == -2
            or embeddings == -2
        ):
            self.pulsing = False
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            GLib.idle_add(self.run_button.set_sensitive, True)
            GLib.idle_add(self.sources_list.set_sensitive, True)
            return False

        if (
            model_detection == -3
            or model_landmarks == -3
            or anchors == -3
            or embeddings == -3
        ):
            self.pulsing = False
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /opt/gopoint-apps/downloads and try to download again.",
            )
            GLib.idle_add(self.run_button.set_sensitive, True)
            GLib.idle_add(self.sources_list.set_sensitive, True)
            return False

        GLib.idle_add(self.status_bar.set_text, "Loading models to cache...")

        # Load models and save graphs on cache
        if self.platform == "i.MX8MP":
            GLib.idle_add(
                self.status_bar.set_text,
                "Warming up detection model and saving to cache...",
            )

            subprocess.run(
                self.cache_enable
                + " /usr/bin/tensorflow-lite-*/examples/benchmark_model "
                "--graph=/opt/gopoint-apps/downloads/"
                + self.model_detection_tflite
                + " --external_delegate_path=/usr/lib/libvx_delegate.so",
                shell=True,
                check=True,
            )

            GLib.idle_add(
                self.status_bar.set_text,
                "Warming up landmark model and saving to cache...",
            )

            subprocess.run(
                self.cache_enable
                + " /usr/bin/tensorflow-lite-*/examples/benchmark_model "
                "--graph=/opt/gopoint-apps/downloads/"
                + self.model_landmark_tflite
                + " --external_delegate_path=/usr/lib/libvx_delegate.so",
                shell=True,
                check=True,
            )

        if self.platform == "i.MX93":
            if not os.path.exists(
                "/opt/gopoint-apps/downloads/" + self.model_detection_vela
            ):
                GLib.idle_add(
                    self.status_bar.set_text,
                    "Compiling and saving detection model to cache...",
                )

                subprocess.run(
                    "vela /opt/gopoint-apps/downloads/"
                    + self.model_detection_tflite
                    + " --output-dir=/opt/gopoint-apps/downloads/",
                    shell=True,
                    check=True,
                )

            if not os.path.exists(
                "/opt/gopoint-apps/downloads/" + self.model_landmark_vela
            ):
                GLib.idle_add(
                    self.status_bar.set_text,
                    "Compiling and saving landmark model to cache...",
                )

                subprocess.run(
                    "vela /opt/gopoint-apps/downloads/"
                    + self.model_landmark_tflite
                    + " --output-dir=/opt/gopoint-apps/downloads/",
                    shell=True,
                    check=True,
                )

        GLib.idle_add(self.status_bar.set_text, "Models are ready!")
        self.pulsing = False

        GLib.idle_add(
            self.status_bar.set_text,
            "Running i.MX Smart Fitness...",
        )

        self.output_process = subprocess.Popen(
            self.cache_enable + " /opt/gopoint-apps/scripts/"
            "machine_learning/imx_smart_fitness/imx-smart-fitness "
            "--device="
            + device
            + " --target="
            + self.platform
            + " --pose-detection-model=/opt/gopoint-apps/downloads/"
            + (
                self.model_detection_tflite
                if self.platform == "i.MX8MP"
                else self.model_detection_vela
            )
            + " --pose-landmark-model=/opt/gopoint-apps/downloads/"
            + (
                self.model_landmark_tflite
                if self.platform == "i.MX8MP"
                else self.model_landmark_vela
            )
            + " --pose-embeddings=/opt/gopoint-apps/downloads/pose_embeddings.csv"
            " --anchors=/opt/gopoint-apps/downloads/anchors.txt",
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
        )

        _, error = self.output_process.communicate()

        output_error_v4l2src = "Error message received from element [v4l2src0]"
        if output_error_v4l2src in str(error):
            self.output_process.kill()
            GLib.idle_add(
                self.status_bar.set_text,
                "Source device not compatible...\nPlease select another device!",
            )
            GLib.idle_add(self.run_button.set_sensitive, True)
            GLib.idle_add(self.sources_list.set_sensitive, True)
            return False

        return True


if __name__ == "__main__":
    main = ImxSmartFitness()
    gtk.main()
