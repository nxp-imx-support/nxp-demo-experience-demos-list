#!/usr/bin/env python3

"""
Copyright 2022 NXP

SPDX-License-Identifier: Apache-2.0 

This script benchmarks the ML performance on NPU and CPU
"""

import gi
import threading
import subprocess
import sys
import os
sys.path.append("/home/root/.nxp-demo-experience/scripts/")
import utils
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gio, Gdk

class DownloadGUI(Gtk.Window):
    """The main voice GUI application."""

    def __init__(self):
        """Creates the loading window and then shows it"""
        super().__init__()
        self.cpu_time = -1
        self.npu_time = -1

        self.set_default_size(450, 100)
        self.set_resizable(False)
        self.set_border_width(10)

        header = Gtk.HeaderBar()
        header.set_title("TFLite Benchmarking Demo")
        header.set_subtitle("Machine Learning")
        self.set_titlebar(header)

        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        header.pack_end(quit_button)
        quit_button.connect("clicked", Gtk.main_quit)

        self.main_grid = Gtk.Grid(
            row_homogeneous=False, column_homogeneous=True,
            column_spacing=15, row_spacing=15)
        self.main_grid.set_margin_end(10)
        self.main_grid.set_margin_start(10)
        self.status_label = Gtk.Label.new("Setting up...")
        self.main_grid.attach(self.status_label, 0, 0, 1, 1)
        self.add(self.main_grid)

    def preload(self):
        """Downloads all the models"""
        GLib.idle_add(self.status_label.set_text,
            "\n\nDownloading CPU model...")
        self.cpu_model = utils.download_file(
            "mobilenet_v1_1.0_224_quant.tflite")
        if (self.cpu_model == -1 or self.cpu_model == -2
            or self.cpu_model == -3):
            GLib.idle_add(self.status_label.set_text,
            "\n\nCannot download CPU Model!")
            return
        GLib.idle_add(self.status_label.set_text,
            "\n\nDownloading NPU model...")
        self.npu_model = utils.download_file(
            "mobilenet_v1_1.0_224_quant_vela.tflite")
        if (self.npu_model == -1 or self.npu_model == -2
            or self.npu_model == -3):
            GLib.idle_add(self.status_label.set_text,
            "\n\nCannot download NPU Model!")
            return
        self.benchmark_model()

    def benchmark_model(self):
        """Benchmark the models"""
        GLib.idle_add(self.status_label.set_text,
            "\n\nFinding benchmark tool...")
        benchmark_path = subprocess.check_output(
            ['find', '/usr/bin', '-name', 'benchmark_model']
        ).decode('utf-8').splitlines()
        if len(benchmark_path) < 1:
            GLib.idle_add(self.status_label.set_text,
            "\n\nMissing benchmarking tool!")
            return
        benchmark_path = benchmark_path[0]
        os.system("echo 4 > /proc/sys/kernel/printk")
        GLib.idle_add(self.status_label.set_text,
            "\n\nRunning CPU Model...")
        cpu_out = subprocess.check_output(
            [benchmark_path, "--num_threads=2", "--graph=" + self.cpu_model]
            ).decode('utf-8').splitlines()
        self.cpu_time = self.get_time(cpu_out)
        GLib.idle_add(self.status_label.set_text,
            "\n\nRunning NPU Model...")
        npu_out = subprocess.check_output(
            [benchmark_path, "--num_threads=2", "--graph=" + self.npu_model]
            ).decode('utf-8').splitlines()
        self.npu_time = self.get_time(npu_out)
        self.display_out()

    def display_out(self):
        """Display the output"""
        if (self.npu_time < self.cpu_time):
            ratio = str(round(((self.cpu_time-self.npu_time)/self.cpu_time)*100, 2))
            comp = "The NPU is " + ratio + "% faster than the CPU!"
        elif (self.npu_time > self.cpu_time):
            ratio = str(round(((self.npu_time-self.cpu_time)/self.npu_time)*100, 2))
            comp = "The CPU is " + ratio + "% faster than the NPU!"
        else:
             comp = "The CPU and NPU are equal!"
        out = (
                "\nTime to run on CPU: " +
                str(round(self.cpu_time,2)) + " ms (" + 
                str(round(1000/self.cpu_time, 2)) + " IPS)\n\n" +
                "Time to run on NPU: " +
                str(round(self.npu_time,2)) + " ms (" +
                str(round(1000/self.npu_time, 2)) + " IPS)\n\n" +
                comp + "\n"
        )
        GLib.idle_add(self.status_label.set_text, out)

    def get_time(self, output):
        """Get the time (in ms) from the output"""
        for line in output:
            if line.startswith("Inference timings in us:"):
                time = float(line[line.find("Inference (avg):")+17:])/1000
                return time 

def main():
    """Start the demo"""
    # Display window
    window = DownloadGUI()
    window.show_all()
    download_thread = threading.Thread(
            target=window.preload)
    download_thread.start()
    # Run GTK loop
    Gtk.main()

if __name__ == "__main__":
    main()
