#!/usr/bin/env python3

"""
Copyright 2024 NXP
SPDX-License-Identifier: BSD-3-Clause

This script launches the i.MX DMS demo using a GUI
"""

import os
import sys
import glob
import subprocess
import threading
import time
import gi

# Check for correct Gtk version
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk
from gi.repository import GLib

# Import utils
sys.path.append("/home/root/.nxp-demo-experience/scripts")
import utils

cur_path = os.path.dirname(os.path.abspath(__file__))


def threaded(fn):
    """
    Handle threads out of main GTK thread
    """

    def wrapper(*args, **kwargs):
        threading.Thread(target=fn, args=args, kwargs=kwargs).start()

    return wrapper


class ImxDMSLauncher:
    """
    i.MX DMS launcher
    """

    def __init__(self):
        # Obtain GUI settings and configurations
        glade_file = cur_path + "/imx_dms_demo.glade"

        self.builder = gtk.Builder()
        self.builder.add_from_file(glade_file)
        self.builder.connect_signals(self)

        # Create instances of widgets
        self.sources_list = self.builder.get_object("sources-list")
        self.backend_list = self.builder.get_object("backend-list")
        self.run_button = self.builder.get_object("run-button")
        self.status_bar = self.builder.get_object("status-bar")
        self.about_button = self.builder.get_object("about-button")
        self.about_dialog = self.builder.get_object("about-dialog")
        self.progress_bar = self.builder.get_object("progress-bar")

        # Progress bar config
        self.pulsing = False
        self.timeout_id = None
        self.progress_bar.set_show_text(False)

        # Get main application window
        window = self.builder.get_object("main-window")

        self.platform = None
        self.cache_enable = ""

        # Check target (i.MX8M Plus vs i.MX93)
        if os.path.exists("/usr/lib/libvx_delegate.so"):
            self.platform = "i.MX8MP"
            self.cache_enable = (
                "VIV_VX_ENABLE_CACHE_GRAPH_BINARY='1' "
                + "VIV_VX_CACHE_BINARY_GRAPH_DIR=/home/root/.cache/gopoint "
            )
        elif os.path.exists("/usr/lib/libethosu_delegate.so"):
            self.platform = "i.MX93"
        else:
            print("Target is not supported!")
            sys.exit()

        # Define names of info image
        if self.platform == "i.MX8MP":
            self.info_image = "imx8mp_dms_info.jpeg"
        elif self.platform == "i.MX93":
            self.info_image = "imx93_dms_info.jpeg"
        else:
            print("Target is not supported!")
            sys.exit()

        # Define names of models
        self.face_detection_model = "face_detection_ptq.tflite"
        self.face_landmark_model = "face_landmark_ptq.tflite"
        self.iris_landmark_model = "iris_landmark_ptq.tflite"
        self.smk_call_detection_model = "yolov4_tiny_smk_call.tflite"

        # Obtain available devices
        devices = []
        for device in glob.glob("/dev/video*"):
            devices.append(device)

        for device in devices:
            self.sources_list.append_text(device)

        self.sources_list.set_active(len(devices) - 1)

        # Obtain backend
        self.backend_list.append_text("NPU")
        self.backend_list.append_text("CPU")
        self.backend_list.set_active(0)

        self.run_button.connect("clicked", self.start)

        window.connect("delete-event", gtk.main_quit)
        window.show()

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

    @threaded
    def start(self, widget):
        """
        Function to start and run i.MX DMS demo
        """
        self.run_button.set_sensitive(False)
        self.sources_list.set_sensitive(False)
        self.backend_list.set_sensitive(False)
        device = self.sources_list.get_active_text()
        backend = self.backend_list.get_active_text()

        self.pulsing = True
        self.timeout_id = GLib.timeout_add(50, self.on_timeout)

        GLib.idle_add(self.status_bar.set_text, "Downloading models...")

        # Download assets
        model_face_detection = utils.download_file(self.face_detection_model)
        model_face_landmark = utils.download_file(self.face_landmark_model)
        model_iris_landmark = utils.download_file(self.iris_landmark_model)
        model_smk_call_detection = utils.download_file(self.smk_call_detection_model)
        info_image_s = utils.download_file(self.info_image)

        # Handle errors during download if present
        if (
            model_face_detection == -1
            or model_face_landmark == -1
            or model_iris_landmark == -1
            or model_smk_call_detection == -1
            or info_image_s == -1
        ):
            self.pulsing = False
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.run_button.set_sensitive(True)
            self.sources_list.set_sensitive(True)
            self.backend_list.set_sensitive(True)
            return False
        if (
            model_face_detection == -2
            or model_face_landmark == -2
            or model_iris_landmark == -2
            or model_smk_call_detection == -2
            or info_image_s == -2
        ):
            self.pulsing = False
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.run_button.set_sensitive(True)
            self.sources_list.set_sensitive(True)
            self.backend_list.set_sensitive(True)
            return False

        if (
            model_face_detection == -3
            or model_face_landmark == -3
            or model_iris_landmark == -3
            or model_smk_call_detection == -3
            or info_image_s == -3
        ):
            self.pulsing = False
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /home/root/.cache/gopoint and try to download again.",
            )
            self.run_button.set_sensitive(True)
            self.sources_list.set_sensitive(True)
            self.backend_list.set_sensitive(True)
            return False

        GLib.idle_add(self.status_bar.set_text, "Loading models to cache...")

        # Load models and save graphs on cache
        if self.platform == "i.MX8MP" and backend == "NPU":
            GLib.idle_add(
                self.status_bar.set_text,
                "Warming up face detection model and save to cache...",
            )

            subprocess.run(
                self.cache_enable
                + " /usr/bin/tensorflow-lite-*/examples/benchmark_model "
                "--graph=/home/root/.cache/gopoint/"
                + self.face_detection_model
                + " --external_delegate_path=/usr/lib/libvx_delegate.so",
                shell=True,
                check=True,
            )

            GLib.idle_add(
                self.status_bar.set_text,
                "Warming up face landmark model and save to cache...",
            )

            subprocess.run(
                self.cache_enable
                + " /usr/bin/tensorflow-lite-*/examples/benchmark_model "
                "--graph=/home/root/.cache/gopoint/"
                + self.face_landmark_model
                + " --external_delegate_path=/usr/lib/libvx_delegate.so",
                shell=True,
                check=True,
            )

            GLib.idle_add(
                self.status_bar.set_text,
                "Warming up iris landmark model and save to cache...",
            )

            subprocess.run(
                self.cache_enable
                + " /usr/bin/tensorflow-lite-*/examples/benchmark_model "
                "--graph=/home/root/.cache/gopoint/"
                + self.iris_landmark_model
                + " --external_delegate_path=/usr/lib/libvx_delegate.so",
                shell=True,
                check=True,
            )

            GLib.idle_add(
                self.status_bar.set_text,
                "Warming up smk/call detection model and save to cache...",
            )

            subprocess.run(
                self.cache_enable
                + " /usr/bin/tensorflow-lite-*/examples/benchmark_model "
                "--graph=/home/root/.cache/gopoint/"
                + self.smk_call_detection_model
                + " --external_delegate_path=/usr/lib/libvx_delegate.so",
                shell=True,
                check=True,
            )

        if self.platform == "i.MX93" and backend == "NPU":
            # overwrite models name if backend is NPU for imx93
            face_detection_vela_model = "face_detection_ptq_vela.tflite"
            face_landmark_vela_model = "face_landmark_ptq_vela.tflite"
            iris_landmark_vela_model = "iris_landmark_ptq_vela.tflite"
            smk_call_detection_vela_model = "yolov4_tiny_smk_call_vela.tflite"

            if not os.path.exists(
                "/home/root/.cache/gopoint/" + face_detection_vela_model
            ):
                GLib.idle_add(
                    self.status_bar.set_text,
                    "Compiling and saving face detection model to cache...",
                )

                subprocess.run(
                    "vela /home/root/.cache/gopoint/"
                    + self.face_detection_model
                    + " --output-dir=/home/root/.cache/gopoint/",
                    shell=True,
                    check=True,
                )

            if not os.path.exists(
                "/home/root/.cache/gopoint/" + face_landmark_vela_model
            ):
                GLib.idle_add(
                    self.status_bar.set_text,
                    "Compiling and saving face landmark model to cache...",
                )

                subprocess.run(
                    "vela /home/root/.cache/gopoint/"
                    + self.face_landmark_model
                    + " --output-dir=/home/root/.cache/gopoint/",
                    shell=True,
                    check=True,
                )

            if not os.path.exists(
                "/home/root/.cache/gopoint/" + iris_landmark_vela_model
            ):
                GLib.idle_add(
                    self.status_bar.set_text,
                    "Compiling and saving iris landmark model to cache...",
                )

                subprocess.run(
                    "vela /home/root/.cache/gopoint/"
                    + self.iris_landmark_model
                    + " --output-dir=/home/root/.cache/gopoint/",
                    shell=True,
                    check=True,
                )

            if not os.path.exists(
                "/home/root/.cache/gopoint/" + smk_call_detection_vela_model
            ):
                GLib.idle_add(
                    self.status_bar.set_text,
                    "Compiling and saving smk/call detection model to cache...",
                )

                subprocess.run(
                    "vela /home/root/.cache/gopoint/"
                    + self.smk_call_detection_model
                    + " --output-dir=/home/root/.cache/gopoint/",
                    shell=True,
                    check=True,
                )

        GLib.idle_add(self.status_bar.set_text, "Models are ready!")
        self.pulsing = False

        GLib.idle_add(
            self.status_bar.set_text,
            "Running i.MX DMS",
        )

        subprocess.run(
            self.cache_enable
            + "python3 "
            + cur_path
            + "/dms_demo.py"
            + " --device="
            + device
            + " --backend="
            + backend
            + " --model_path=/home/root/.cache/gopoint",
            shell=True,
            check=True,
            capture_output=True,
        )

        self.run_button.set_sensitive(True)
        self.sources_list.set_sensitive(True)
        self.backend_list.set_sensitive(True)

        return True


if __name__ == "__main__":
    main = ImxDMSLauncher()
    gtk.main()
