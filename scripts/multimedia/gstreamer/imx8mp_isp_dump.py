"""
Copyright 2021 NXP

SPDX-License-Identifier: BSD-2-Clause

This script provides a user interface for the “video_test” tool that is used
to dump the raw data from a camera into a file. Through the GUI, users are
able to select options such as the camera, mode, format, postprocessing
options, and a save location. After this, users can push a button to run
video_test and dump the frames onto the selected drive.

This demo will only work with cameras that work with video_test.
"""

import glob
import json
import subprocess
import os
from datetime import datetime
import threading
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gio

class VideoDump(Gtk.Window):
    """The GUI window for the launcher."""

    def __init__(self):
        """Create the UI window."""
        # Initialization
        Gtk.init_check()
        super().__init__()
        self.set_default_size(440, 280)
        self.set_resizable(False)
        self.set_border_width(10)

        # Create widgets
        main_grid = Gtk.Grid(row_homogeneous=False,
                            column_spacing=15,
                            row_spacing=15)
        main_grid.set_margin_end(10)
        main_grid.set_margin_start(10)
        self.add(main_grid)

        header = Gtk.HeaderBar()
        header.set_title("i.MX 8M Plus Video Dump Demo")
        header.set_subtitle("i.MX ISP Demos")
        self.set_titlebar(header)

        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        header.pack_end(quit_button)
        quit_button.connect("clicked", self.on_close)

        device_label = Gtk.Label.new("Camera")

        self.device_combo = Gtk.ComboBoxText()

        self.load_button = Gtk.Button.new_with_label("Load Camera")
        self.load_button.set_hexpand(True)

        separator = Gtk.Separator.new(0)

        mode_label = Gtk.Label.new("Mode")

        self.mode_combo = Gtk.ComboBoxText()
        self.mode_combo.set_hexpand(True)
        self.mode_combo.set_sensitive(False)

        format_label = Gtk.Label.new("Format")

        self.format_combo = Gtk.ComboBoxText()
        self.format_combo.set_hexpand(True)
        self.format_combo.set_sensitive(False)

        postprocess_label = Gtk.Label.new("Postprocessing")

        self.postprocess_combo = Gtk.ComboBoxText()
        self.postprocess_combo.set_hexpand(True)
        self.postprocess_combo.set_sensitive(False)

        height_label = Gtk.Label.new("Height")

        self.height_entry = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 300, 2160, 2)
        self.height_entry.set_value(1080)
        self.height_entry.set_hexpand(True)
        self.height_entry.set_sensitive(False)

        width_label = Gtk.Label.new("Width")

        self.width_entry = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 300, 3840, 2)
        self.width_entry.set_value(1920)
        self.width_entry.set_hexpand(True)
        self.width_entry.set_sensitive(False)

        fps_label = Gtk.Label.new("FPS")

        self.fps_entry = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 1, 60, 1)
        self.fps_entry.set_value(30)
        self.fps_entry.set_hexpand(True)
        self.fps_entry.set_sensitive(False)

        disk_label = Gtk.Label.new("Save to...")

        self.disk_combo = Gtk.ComboBoxText()
        self.disk_combo.set_hexpand(True)
        self.disk_combo.set_sensitive(False)

        self.launch_button = Gtk.Button.new_with_label("Dump Frames")
        self.launch_button.set_hexpand(True)
        self.launch_button.set_sensitive(False)

        separator_bottom = Gtk.Separator.new(0)

        self.status_bar = Gtk.Statusbar.new()
        self.status_bar.push(0, "Select a camera to load")

        for camera in glob.glob('/dev/video*'):
            self.device_combo.append_text(camera)

        drive_finder = subprocess.run(
            ['lsblk','-o', 'NAME,MOUNTPOINT', '-x', 'MOUNTPOINT', '-J'],
            capture_output=True, text=True)
        drive_db = json.loads(drive_finder.stdout)["blockdevices"]
        for drive in drive_db:
            if drive["mountpoint"] is not None:
                self.disk_combo.append_text(drive["mountpoint"])

        formats = [
            "RAW12",
            "RAW10",
            "RAW8",
            "NV16",
            "NV12",
            "YUYV"
        ]
        for frmt in formats:
            self.format_combo.append_text(frmt)

        postprocess_options = [
            "None",
            "Crop",
            "Scale"
        ]
        for options in postprocess_options:
            self.postprocess_combo.append_text(options)


        self.device_combo.set_active(0)
        self.disk_combo.set_active(0)
        self.format_combo.set_active(0)
        self.postprocess_combo.set_active(0)

        main_grid.attach(device_label, 0, 0, 1, 1)
        main_grid.attach(self.device_combo, 1, 0, 1, 1)
        main_grid.attach(self.load_button, 0, 1, 2, 1)
        main_grid.attach(separator, 0, 2, 2, 1)
        main_grid.attach(mode_label, 0, 3, 1, 1)
        main_grid.attach(self.mode_combo, 1, 3, 1, 1)
        main_grid.attach(format_label, 0, 4, 1, 1)
        main_grid.attach(self.format_combo, 1, 4, 1, 1)
        main_grid.attach(postprocess_label, 0, 5, 1, 1)
        main_grid.attach(self.postprocess_combo, 1, 5, 1, 1)
        main_grid.attach(height_label, 0, 7, 1, 1)
        main_grid.attach(self.height_entry, 1, 7, 1, 1)
        main_grid.attach(width_label, 0, 6, 1, 1)
        main_grid.attach(self.width_entry, 1, 6, 1, 1)
        main_grid.attach(fps_label, 0, 8, 1, 1)
        main_grid.attach(self.fps_entry, 1, 8, 1, 1)
        main_grid.attach(disk_label, 0, 9, 1, 1)
        main_grid.attach(self.disk_combo, 1, 9, 1, 1)
        main_grid.attach(self.launch_button, 0, 10, 2, 1)
        main_grid.attach(separator_bottom, 0, 11, 2, 1)
        main_grid.attach(self.status_bar, 0, 12, 2, 1)

        self.load_button.connect("clicked",self.load_camera)
        self.running = False
        self.launch_button.connect("clicked",self.on_run)
        self.mode_combo.connect("changed",self.mode_change)
        self.postprocess_combo.connect("changed",self.process_change)


    class Mode:
        """Holds the mode details."""

        def __init__(self, index, width, height, fps, hdr):
            """Create the mode."""
            self.index = index
            self.width = width
            self.height = height
            self.fps = fps
            self.hdr = hdr

    def get_mode(self):
        """Do dummy run to read the modes for a camera."""
        mode_finder = subprocess.run(
            ['/opt/imx8-isp/bin/video_test', '-w', '999999999', '-h',
            '999999999', '-f', 'YUYV', '-t', '0', '-d',
            self.device_combo.get_active_text()[10:]],
            capture_output=True, text=True)
        mode_text = mode_finder.stdout.replace(
            " ", "").replace("\t", "").split('\n')
        self.mode_set = {}
        mode_cur = None
        for line in mode_text:
            if line.startswith('ERROR'):
                break
            elif line.startswith('{'):
                mode_cur = self.Mode(-1, -1, -1, -1, -1)
            elif line.startswith('}'):
                if mode_cur is None:
                    break
                self.mode_set[mode_cur.index] = mode_cur
                mode_cur = None
            elif line.startswith('index'):
                mode_cur.index = line[6:]
            elif line.startswith('width'):
                mode_cur.width = line[6:]
                if mode_cur.width == "0":
                    if mode_cur.index == "0" or mode_cur.index == "2":
                        mode_cur.width = "3840"
                    else:
                        mode_cur.width = "1920"
            elif line.startswith('height'):
                mode_cur.height = line[7:]
                if mode_cur.height == "0":
                    if mode_cur.index == "0" or mode_cur.index == "2":
                        mode_cur.height = "2160"
                    else:
                        mode_cur.height = "1080"
            elif line.startswith('fps'):
                mode_cur.fps = line[4:]
            elif line.startswith('hdr_mode'):
                mode_cur.hdr = line[9:]
        GLib.idle_add(self.update_gui_mode)

    def update_gui_mode(self):
        """Run callback to update GUI with mode options."""
        if len(self.mode_set) == 0:
            error_dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CANCEL,
                text="Incompatible camera!",
            )
            error_dialog.format_secondary_text(
                "The selected camera cannot be run with this demo."
            )
            error_dialog.run()
            error_dialog.destroy()
            self.status_bar.push(
                0, self.device_combo.get_active_text() + " failed to load!")
        else:
            for mode in self.mode_set.keys():
                self.mode_combo.append_text(mode)
            self.mode_combo.set_active(0)
            self.height_entry.set_value(
                int(self.mode_set[self.mode_combo.get_active_text()].height))
            self.width_entry.set_value(
                int(self.mode_set[self.mode_combo.get_active_text()].width))
            self.fps_entry.set_value(
                int(self.mode_set[self.mode_combo.get_active_text()].fps))
            self.mode_combo.set_sensitive(True)
            self.format_combo.set_sensitive(True)
            self.postprocess_combo.set_sensitive(True)
            if (
                self.postprocess_combo.get_active_text() == "Crop" or
                self.postprocess_combo.get_active_text() == "Scale"):
                self.height_entry.set_sensitive(True)
                self.width_entry.set_sensitive(True)
            self.fps_entry.set_sensitive(False)
            self.disk_combo.set_sensitive(True)
            self.launch_button.set_sensitive(True)
            self.status_bar.push(
                0, self.device_combo.get_active_text() + " loaded!")
        self.load_button.set_sensitive(True)
        self.device_combo.set_sensitive(True)

    def load_camera(self, button):
        """Get the mode for the selected camera."""
        button.set_sensitive(False)
        self.device_combo.set_sensitive(False)
        self.mode_combo.set_sensitive(False)
        self.format_combo.set_sensitive(False)
        self.postprocess_combo.set_sensitive(False)
        self.height_entry.set_sensitive(False)
        self.width_entry.set_sensitive(False)
        self.fps_entry.set_sensitive(False)
        self.disk_combo.set_sensitive(False)
        self.launch_button.set_sensitive(False)
        self.status_bar.push(
            0,"Loading " + self.device_combo.get_active_text() + "...")
        thread = threading.Thread(target=self.get_mode)
        thread.daemon = True
        thread.start()

    def mode_change(self, combo_box):
        """Change the UI for a given mode."""
        if self.mode_combo.get_active_text() is not None:
            self.height_entry.set_value(
                int(self.mode_set[self.mode_combo.get_active_text()].height))
            self.width_entry.set_value(
                int(self.mode_set[self.mode_combo.get_active_text()].width))
            self.fps_entry.set_value(
                int(self.mode_set[self.mode_combo.get_active_text()].fps))

    def process_change(self, combo_box):
        """Change UI based on post-process selector"""
        if (self.postprocess_combo.get_active_text() == "Crop" or
            self.postprocess_combo.get_active_text() == "Scale"):
            self.height_entry.set_sensitive(True)
            self.width_entry.set_sensitive(True)
        else:
            self.height_entry.set_sensitive(False)
            self.width_entry.set_sensitive(False)
            self.mode_change(combo_box)

    def on_close(self, unused):
        """Close the GUI and everything else."""
        os.system("pkill -P" + str(os.getpid()))
        Gtk.main_quit()

    def send_status(self, status):
        """Send a message to the status bar."""
        self.status_bar.push(0, status)

    def change_button(self, text, active):
        """Change the text on the button."""
        self.launch_button.set_label(text)
        self.launch_button.set_sensitive(active)

    def unlock_controls(self):
        """Enable controls."""
        self.device_combo.set_sensitive(True)
        self.mode_combo.set_sensitive(True)
        self.load_button.set_sensitive(True)
        self.format_combo.set_sensitive(True)
        self.postprocess_combo.set_sensitive(True)
        if (self.postprocess_combo.get_active_text() == "Crop" or
            self.postprocess_combo.get_active_text() == "Scale"):
            self.height_entry.set_sensitive(True)
            self.width_entry.set_sensitive(True)
        self.fps_entry.set_sensitive(False)
        self.disk_combo.set_sensitive(True)
        self.launch_button.set_sensitive(True)

    def throw_error(self, error):
        """Create an error dialog."""
        error_dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.ERROR,
                    buttons=Gtk.ButtonsType.CANCEL,
                    text="Error occurred!",
                )
        error_dialog.format_secondary_text(
            "The following error occurred: " + error)
        error_dialog.run()
        error_dialog.destroy()

    def run_video_test(self):
        """Start dumping frames onto a USB drive."""
        os.chdir(self.disk_combo.get_active_text())
        dirname = (self.mode_combo.get_active_text() + "_" + 
            self.format_combo.get_active_text() + "_" +
            str(int(self.height_entry.get_value())) + "_" +
            str(int(self.width_entry.get_value())) + "_" +
            datetime.now().strftime("%m-%d-%Y_%H-%M-%S"))
        os.mkdir(dirname)
        os.chdir(dirname)
        command = ["/opt/imx8-isp/bin/video_test", "-w",
                    str(int(self.width_entry.get_value())), "-h",
                    str(int(self.height_entry.get_value())), "-f",
                    self.format_combo.get_active_text(), "-t", "2", "-m",
                    self.mode_combo.get_active_text(), "-d",
                    self.device_combo.get_active_text()[10:]]
        if self.postprocess_combo.get_active_text() == "Crop":
            command.append("-c")
        if self.postprocess_combo.get_active_text() == "Scale":
            command.append("-s")
        self.video_test = subprocess.Popen(command)
        self.running = True
        GLib.idle_add(self.change_button,"Stop Dump", True)
        while True:
            run_check = self.video_test.poll()
            if run_check is None:
                files = len(os.listdir())
                if files > 0:
                    GLib.idle_add(
                        self.send_status, str(files) + " frames dumped.")
                if self.stop_flag:
                    GLib.idle_add(self.send_status, "Exiting...")
                    self.video_test.terminate()
                    try:
                        self.video_test.wait(5)
                    except:
                        self.video_test.kill()
                    GLib.idle_add(
                        self.send_status,
                        "Saving to disk... (This may take a while)")
                    subprocess.run(["sync"])
                    GLib.idle_add(
                        self.send_status, str(len(os.listdir())) +
                        " frames saved to " + self.disk_combo.get_active_text()
                        + "!")
                    break
            else:
                GLib.idle_add(
                    self.send_status, 
                    "The dump stopped unexpectedly. Looking into reason...")
                error_finder = subprocess.run(
                    command, capture_output=True, text=True)
                error_text = error_finder.stdout.replace("\t","").split('\n')
                error_reported = "Unknown error"
                for line in error_text:
                    if 'ERROR' in line:
                        error_reported = line[line.index('ERROR'):]
                        break
                GLib.idle_add(self.throw_error, error_reported)
                GLib.idle_add(self.send_status, "An error stopped the dump")
                GLib.idle_add(self.change_button, "Dump Frames", True)
                GLib.idle_add(self.unlock_controls)
                break
        self.running = False
        GLib.idle_add(self.change_button, "Dump Frames", True)
        GLib.idle_add(self.unlock_controls)

    def on_run(self, button):
        """Start or stop dumpping frames."""
        if not self.running:
            self.stop_flag = False
            self.send_status("Initializing...")
            button.set_sensitive(False)
            self.device_combo.set_sensitive(False)
            self.mode_combo.set_sensitive(False)
            self.format_combo.set_sensitive(False)
            self.postprocess_combo.set_sensitive(False)
            self.height_entry.set_sensitive(False)
            self.width_entry.set_sensitive(False)
            self.fps_entry.set_sensitive(False)
            self.disk_combo.set_sensitive(False)
            self.launch_button.set_sensitive(False)
            self.load_button.set_sensitive(False)
            thread = threading.Thread(target=self.run_video_test)
            thread.daemon = True
            thread.start()
        else:
            self.stop_flag = True
            self.change_button("Stop Dump", False)


if __name__ == "__main__":
    demo_window = VideoDump()
    demo_window.connect("destroy", Gtk.main_quit)
    demo_window.show_all()
    Gtk.main()
