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
sys.path.append("/opt/gopoint-apps/scripts")
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
        self.resolution_list = self.builder.get_object("resolution-list")
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

        # Check target (i.MX 8M Plus vs i.MX 93)
        if os.path.exists("/usr/lib/libvx_delegate.so"):
            self.platform = "i.MX8MP"
            self.cache_enable = (
                "VIV_VX_ENABLE_CACHE_GRAPH_BINARY='1' "
                + "VIV_VX_CACHE_BINARY_GRAPH_DIR=/opt/gopoint-apps/downloads "
            )
        elif os.path.exists("/usr/lib/libethosu_delegate.so"):
            self.platform = "i.MX93"
        elif os.path.exists("/usr/lib/libneutron_delegate.so"):
            self.platform = "i.MX95"
        else:
            print("Target is not supported!")
            sys.exit()

        # Define names of info image
        if self.platform == "i.MX8MP":
            self.info_image = "imx8mp_dms_info.jpeg"
        elif self.platform == "i.MX93":
            self.info_image = "imx93_dms_info.jpeg"
        elif self.platform == "i.MX95":
            self.info_image = "imx95_dms_info.jpeg"
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

        # Obtian display resolution
        resolutions = [
            "1920x1080",
            "1280x720",
            "800x600",
            "720x480",
        ]

        for resolution in resolutions:
            self.resolution_list.append_text(resolution)
        self.resolution_list.set_active(0)

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

    def set_widgets_sensitive(self, sensitive):
        """
        Helper function to set widget sensitivity from main thread
        """
        self.run_button.set_sensitive(sensitive)
        self.sources_list.set_sensitive(sensitive)
        self.backend_list.set_sensitive(sensitive)
        self.resolution_list.set_sensitive(sensitive)

    @threaded
    def start(self, widget):
        """
        Function to start and run i.MX DMS demo
        """
        # Disable widgets using GLib.idle_add to ensure main thread execution
        GLib.idle_add(self.set_widgets_sensitive, False)
        
        device = self.sources_list.get_active_text()
        backend = self.backend_list.get_active_text()
        resolution = self.resolution_list.get_active_text()

        self.pulsing = True
        self.timeout_id = GLib.timeout_add(50, self.on_timeout)

        GLib.idle_add(self.status_bar.set_text, "Downloading models...")

        # Download result in a list
        download_result = []

        # Download assets
        model_face_detection = utils.download_file(self.face_detection_model)
        download_result.append(model_face_detection)
        model_face_landmark = utils.download_file(self.face_landmark_model)
        download_result.append(model_face_landmark)
        model_iris_landmark = utils.download_file(self.iris_landmark_model)
        download_result.append(model_iris_landmark)
        model_smk_call_detection = utils.download_file(self.smk_call_detection_model)
        download_result.append(model_smk_call_detection)
        info_image_s = utils.download_file(self.info_image)
        download_result.append(info_image_s)

        # Download neutron converted models for i.MX95
        if self.platform == "i.MX95":
            face_detection_neutron_model = utils.download_file("face_detection_ptq_neutron.tflite")
            download_result.append(face_detection_neutron_model)
            face_landmark_neutron_model = utils.download_file("face_landmark_ptq_neutron.tflite")
            download_result.append(face_landmark_neutron_model)
            iris_landmark_neutron_model = utils.download_file("iris_landmark_ptq_neutron.tflite")
            download_result.append(iris_landmark_neutron_model)
            smk_call_detection_neutron_model = utils.download_file("yolov4_tiny_smk_call_neutron.tflite")
            download_result.append(smk_call_detection_neutron_model)

        # Handle errors during download if present
        if -1 in download_result:
            self.pulsing = False
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            GLib.idle_add(self.set_widgets_sensitive, True)
            return False
        if -2 in download_result:
            self.pulsing = False
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            GLib.idle_add(self.set_widgets_sensitive, True)
            return False

        if -3 in download_result:
            self.pulsing = False
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /opt/gopoint-apps/downloads and try to download again.",
            )
            GLib.idle_add(self.set_widgets_sensitive, True)
            return False

        GLib.idle_add(self.status_bar.set_text, "Loading models to cache...")

        # Load models and save graphs on cache
        if self.platform == "i.MX8MP" and backend == "NPU":
            GLib.idle_add(
                self.status_bar.set_text,
                "Warming up face detection model and save to cache...",
            )

            try:
                subprocess.run(
                    self.cache_enable
                    + " /usr/bin/tensorflow-lite-*/examples/benchmark_model "
                    "--graph=/opt/gopoint-apps/downloads/"
                    + self.face_detection_model
                    + " --external_delegate_path=/usr/lib/libvx_delegate.so",
                    shell=True,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                print(f"Error running face detection benchmark: {e}")
                GLib.idle_add(self.set_widgets_sensitive, True)
                return False

            GLib.idle_add(
                self.status_bar.set_text,
                "Warming up face landmark model and save to cache...",
            )

            try:
                subprocess.run(
                    self.cache_enable
                    + " /usr/bin/tensorflow-lite-*/examples/benchmark_model "
                    "--graph=/opt/gopoint-apps/downloads/"
                    + self.face_landmark_model
                    + " --external_delegate_path=/usr/lib/libvx_delegate.so",
                    shell=True,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                print(f"Error running face landmark benchmark: {e}")
                GLib.idle_add(self.set_widgets_sensitive, True)
                return False

            GLib.idle_add(
                self.status_bar.set_text,
                "Warming up iris landmark model and save to cache...",
            )

            try:
                subprocess.run(
                    self.cache_enable
                    + " /usr/bin/tensorflow-lite-*/examples/benchmark_model "
                    "--graph=/opt/gopoint-apps/downloads/"
                    + self.iris_landmark_model
                    + " --external_delegate_path=/usr/lib/libvx_delegate.so",
                    shell=True,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                print(f"Error running iris landmark benchmark: {e}")
                GLib.idle_add(self.set_widgets_sensitive, True)
                return False

            GLib.idle_add(
                self.status_bar.set_text,
                "Warming up smk/call detection model and save to cache...",
            )

            try:
                subprocess.run(
                    self.cache_enable
                    + " /usr/bin/tensorflow-lite-*/examples/benchmark_model "
                    "--graph=/opt/gopoint-apps/downloads/"
                    + self.smk_call_detection_model
                    + " --external_delegate_path=/usr/lib/libvx_delegate.so",
                    shell=True,
                    check=True,
                )
            except subprocess.CalledProcessError as e:
                print(f"Error running smk/call detection benchmark: {e}")
                GLib.idle_add(self.set_widgets_sensitive, True)
                return False

        if self.platform == "i.MX93" and backend == "NPU":
            # overwrite models name if backend is NPU for imx93
            face_detection_vela_model = "face_detection_ptq_vela.tflite"
            face_landmark_vela_model = "face_landmark_ptq_vela.tflite"
            iris_landmark_vela_model = "iris_landmark_ptq_vela.tflite"
            smk_call_detection_vela_model = "yolov4_tiny_smk_call_vela.tflite"

            if not os.path.exists(
                "/opt/gopoint-apps/downloads/" + face_detection_vela_model
            ):
                GLib.idle_add(
                    self.status_bar.set_text,
                    "Compiling and saving face detection model to cache...",
                )

                try:
                    subprocess.run(
                        "vela /opt/gopoint-apps/downloads/"
                        + self.face_detection_model
                        + " --output-dir=/opt/gopoint-apps/downloads/",
                        shell=True,
                        check=True,
                    )
                except subprocess.CalledProcessError as e:
                    print(f"Error compiling face detection model: {e}")
                    GLib.idle_add(self.set_widgets_sensitive, True)
                    return False

            if not os.path.exists(
                "/opt/gopoint-apps/downloads/" + face_landmark_vela_model
            ):
                GLib.idle_add(
                    self.status_bar.set_text,
                    "Compiling and saving face landmark model to cache...",
                )

                try:
                    subprocess.run(
                        "vela /opt/gopoint-apps/downloads/"
                        + self.face_landmark_model
                        + " --output-dir=/opt/gopoint-apps/downloads/",
                        shell=True,
                        check=True,
                    )
                except subprocess.CalledProcessError as e:
                    print(f"Error compiling face landmark model: {e}")
                    GLib.idle_add(self.set_widgets_sensitive, True)
                    return False

            if not os.path.exists(
                "/opt/gopoint-apps/downloads/" + iris_landmark_vela_model
            ):
                GLib.idle_add(
                    self.status_bar.set_text,
                    "Compiling and saving iris landmark model to cache...",
                )

                try:
                    subprocess.run(
                        "vela /opt/gopoint-apps/downloads/"
                        + self.iris_landmark_model
                        + " --output-dir=/opt/gopoint-apps/downloads/",
                        shell=True,
                        check=True,
                    )
                except subprocess.CalledProcessError as e:
                    print(f"Error compiling iris landmark model: {e}")
                    GLib.idle_add(self.set_widgets_sensitive, True)
                    return False

            if not os.path.exists(
                "/opt/gopoint-apps/downloads/" + smk_call_detection_vela_model
            ):
                GLib.idle_add(
                    self.status_bar.set_text,
                    "Compiling and saving smk/call detection model to cache...",
                )

                try:
                    subprocess.run(
                        "vela /opt/gopoint-apps/downloads/"
                        + self.smk_call_detection_model
                        + " --output-dir=/opt/gopoint-apps/downloads/",
                        shell=True,
                        check=True,
                    )
                except subprocess.CalledProcessError as e:
                    print(f"Error compiling smk/call detection model: {e}")
                    GLib.idle_add(self.set_widgets_sensitive, True)
                    return False

        GLib.idle_add(self.status_bar.set_text, "Models are ready!")
        self.pulsing = False

        GLib.idle_add(
            self.status_bar.set_text,
            "Running i.MX DMS",
        )

        try:
            subprocess.run(
                self.cache_enable
                + "python3 "
                + cur_path
                + "/dms_demo.py"
                + " --device="
                + device
                + " --backend="
                + backend
                + " --model_path=/opt/gopoint-apps/downloads"
                + " --resolution="
                + resolution,
                shell=True,
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"Error running DMS demo: {e}")
            GLib.idle_add(self.status_bar.set_text, "Error running DMS demo")
        finally:
            # Always re-enable widgets when done
            GLib.idle_add(self.set_widgets_sensitive, True)

        return True


if __name__ == "__main__":
    main = ImxDMSLauncher()
    gtk.main()
