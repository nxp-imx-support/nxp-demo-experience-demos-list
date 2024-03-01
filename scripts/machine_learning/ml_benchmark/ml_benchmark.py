#!/usr/bin/env python3

"""
Copyright 2022-2024 NXP
SPDX-License-Identifier: Apache-2.0

This script benchmarks the ML performance on NPU and CPU
User can choose a desired TFLite model for benchmark comparison
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
sys.path.append("/home/root/.nxp-demo-experience/scripts")
import utils

MODELS_PATH = "/home/root/.cache/gopoint/"


def threaded(fn):
    """Handle threads out of main GTK thread"""

    def wrapper(*args, **kwargs):
        threading.Thread(target=fn, args=args, kwargs=kwargs).start()

    return wrapper


class MLBenchmark:
    """MLBenchmark GUI launcher"""

    def __init__(self):
        # Obtain GUI settings and configurations
        glade_file = (
            "/home/root/.nxp-demo-experience/"
            "scripts/machine_learning/ml_benchmark/ml_benchmark.glade"
        )
        self.builder = gtk.Builder()
        self.builder.add_from_file(glade_file)
        self.builder.connect_signals(self)

        # Get main application window
        window = self.builder.get_object("main-window")

        # Create instances of widgets
        self.label_threads = self.builder.get_object("threads-label")
        self.number_threads = self.builder.get_object("number-threads")
        self.text_box = self.builder.get_object("text-box")
        self.run_button = self.builder.get_object("run-button")
        self.status_bar = self.builder.get_object("status-bar")
        self.about_button = self.builder.get_object("about-button")
        self.file_chooser = self.builder.get_object("file-chooser")
        self.about_dialog = self.builder.get_object("about-dialog")
        self.progress_bar = self.builder.get_object("progress-bar")

        # Progress bar config
        self.pulsing = False
        self.timeout_id = None
        self.progress_bar.set_show_text(False)

        # General variables
        self.platform = None
        self.cache_enable = ""
        self.threads_available = []
        self.cpu_model = str()
        self.npu_model = str()
        self.delegate = str()

        # Check target (i.MX8M Plus vs i.MX93)
        if os.path.exists("/usr/lib/libvx_delegate.so"):
            self.platform = "i.MX8MP"
            self.cache_enable = (
                "VIV_VX_ENABLE_CACHE_GRAPH_BINARY='1' "
                + "VIV_VX_CACHE_BINARY_GRAPH_DIR=/home/root/.cache/gopoint "
            )
            self.threads_available = ["1", "2", "3", "4"]
            self.delegate = "/usr/lib/libvx_delegate.so"
        elif os.path.exists("/usr/lib/libethosu_delegate.so"):
            self.platform = "i.MX93"
            self.threads_available = ["1", "2"]
            self.delegate = "/usr/lib/libethosu_delegate.so"
        else:
            print("Target is not supported!")
            sys.exit()

        # Populate threads in button list
        for thread in self.threads_available:
            self.number_threads.append_text(thread)
        self.number_threads.set_active(0)

        # Connect signals
        self.run_button.connect("clicked", self.start)
        window.connect("delete-event", gtk.main_quit)
        window.show()

        # Preload default model
        preload_thread = threading.Thread(target=self.preload, daemon=True)
        preload_thread.start()

    def get_time(self, output):
        """Get the time (in ms) from the output"""
        for line in output:
            if line.startswith("INFO: Inference timings in us:"):
                time_ms = float(line[line.find("Inference (avg):") + 17 :]) / 1000.0
                return time_ms
        return float(0.0)

    def about_dialog_activate(self, widget):
        """Function to handle the about dialog window"""
        self.about_dialog.run()
        self.about_dialog.hide()

    def on_timeout(self):
        """Function to handle progress bar"""
        if self.pulsing:
            self.progress_bar.set_show_text(True)
            self.progress_bar.pulse()
            return True
        self.progress_bar.set_show_text(False)
        self.progress_bar.set_fraction(0.0)
        return False

    @threaded
    def start(self, widget):
        """Benchmark the models"""
        self.run_button.set_sensitive(False)
        self.number_threads.set_sensitive(False)
        self.file_chooser.set_sensitive(False)

        self.cpu_model = self.npu_model = self.file_chooser.get_filename()
        if "_vela.tflite" in self.cpu_model:
            GLib.idle_add(
                self.status_bar.set_text, "Please select a non-compiled Vela model!"
            )
            self.run_button.set_sensitive(True)
            self.number_threads.set_sensitive(True)
            self.file_chooser.set_sensitive(True)
            return False

        if self.platform == "i.MX93":
            self.compile_vela()

        benchmark_path = (
            subprocess.check_output(["find", "/usr/bin", "-name", "benchmark_model"])
            .decode("utf-8")
            .splitlines()
        )
        if len(benchmark_path) < 1:
            GLib.idle_add(self.status_bar.set_text, "Missing benchmarking tool!")
            self.run_button.set_sensitive(True)
            self.number_threads.set_sensitive(True)
            self.file_chooser.set_sensitive(True)
            time.sleep(1)
            return False

        benchmark_path = benchmark_path[0]
        number_threads = self.number_threads.get_active_text()
        GLib.idle_add(self.status_bar.set_text, "Running CPU model...")

        cpu_out = (
            subprocess.check_output(
                [
                    benchmark_path,
                    "--num_threads=" + number_threads,
                    "--graph=" + self.cpu_model,
                ]
            )
            .decode("utf-8")
            .splitlines()
        )
        self.cpu_time = self.get_time(cpu_out)

        GLib.idle_add(self.status_bar.set_text, "Running NPU model...")

        npu_out = (
            subprocess.check_output(
                [
                    benchmark_path,
                    "--graph=" + self.npu_model,
                    "--external_delegate_path=" + self.delegate,
                ]
            )
            .decode("utf-8")
            .splitlines()
        )
        self.npu_time = self.get_time(npu_out)

        GLib.idle_add(self.status_bar.set_text, "Benchmarks finished!")

        if self.npu_time < self.cpu_time:
            ratio = str(round(((self.cpu_time) / self.npu_time), 2))
            comp = "The NPU can run " + ratio + " times during 1 CPU run!"
        elif self.npu_time > self.cpu_time:
            ratio = str(round(((self.npu_time) / self.cpu_time), 2))
            comp = "The CPU can run " + ratio + " times during 1 NPU run!"
        else:
            comp = "The CPU and NPU are equal!"
        out = (
            "\nTime to run on CPU: "
            + str(round(self.cpu_time, 2))
            + " ms ("
            + str(round(1000 / self.cpu_time, 2))
            + " IPS)\n"
            + "Time to run on NPU: "
            + str(round(self.npu_time, 2))
            + " ms ("
            + str(round(1000 / self.npu_time, 2))
            + " IPS)\n\n"
            + comp
            + "\n"
        )

        GLib.idle_add(self.text_box.set_text, out)
        self.run_button.set_sensitive(True)
        self.number_threads.set_sensitive(True)
        self.file_chooser.set_sensitive(True)

        return True

    def preload(self):
        """Download the default model"""

        # Block run button and start progress bar
        self.run_button.set_sensitive(False)
        self.number_threads.set_sensitive(False)
        self.file_chooser.set_sensitive(False)
        self.pulsing = True
        self.timeout_id = GLib.timeout_add(50, self.on_timeout)

        GLib.idle_add(self.status_bar.set_text, "Downloading model...")
        default_model = "mobilenet_v1_1.0_224_quant.tflite"
        self.cpu_model = utils.download_file(default_model)

        # Verify if download is successfull
        if self.cpu_model == -1:
            GLib.idle_add(self.status_bar.set_text, "Cannot find files!")
            self.pulsing = False
            self.run_button.set_sensitive(True)
            self.number_threads.set_sensitive(True)
            self.file_chooser.set_sensitive(True)
            return
        if self.cpu_model == -2:
            GLib.idle_add(self.status_bar.set_text, "Download failed!")
            self.pulsing = False
            self.run_button.set_sensitive(True)
            self.number_threads.set_sensitive(True)
            self.file_chooser.set_sensitive(True)
            return
        if self.cpu_model == -3:
            GLib.idle_add(self.status_bar.set_text, "Corrupted file!")
            self.pulsing = False
            self.run_button.set_sensitive(True)
            self.number_threads.set_sensitive(True)
            self.file_chooser.set_sensitive(True)
            return

        GLib.idle_add(self.status_bar.set_text, "Model successfully downloaded!")

        # Wait one second to show message to user
        time.sleep(1)

        self.file_chooser.set_filename(self.cpu_model)

        # Compile model using vela tool for i.MX93
        if self.platform == "i.MX93":
            self.compile_vela()
        else:
            self.npu_model = self.cpu_model

        GLib.idle_add(self.status_bar.set_text, "Models are ready for inference!")

        self.run_button.set_sensitive(True)
        self.number_threads.set_sensitive(True)
        self.file_chooser.set_sensitive(True)
        self.pulsing = False

    def compile_vela(self):
        """Compile vela model"""
        self.npu_model = self.vela_name(self.cpu_model)
        if not os.path.exists(self.npu_model):
            GLib.idle_add(
                self.status_bar.set_text,
                "Compiling model with vela and saving to cache...",
            )

            subprocess.run(
                "vela " + self.cpu_model + " --output-dir=/home/root/.cache/gopoint/",
                shell=True,
                check=True,
            )

    def vela_name(self, model_name):
        """
        Appends the vela label to model name
        """
        tokens = model_name.split(".tflite")
        return MODELS_PATH + (tokens[-2] + "_vela.tflite").split("/")[-1]


if __name__ == "__main__":
    main = MLBenchmark()
    gtk.main()
