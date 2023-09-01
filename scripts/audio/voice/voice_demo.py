"""
Copyright 2022-2023 NXP
SPDX-License-Identifier: BSD-3-Clause

This demo sets up and runs the VoiceSeeker/VoiceSpot/VIT demo that has been
included in the BSP.

The launcher will first attempt to set up a voice application. If
successful, it will display the commands to say and what the current status
is. If it fails, it will tell the user.
"""

import gi
import threading
import subprocess
import time

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gio, Gdk


DEBUG = False


class VoiceGUI(Gtk.Window):
    """The main voice GUI application."""

    WINDOW = "--Window [0,0,480,360]"
    EXE = [
        "/opt/imx-gpu-sdk/GLES2/Bloom___Wayland_XDG/GLES2.Bloom___Wayland_XDG "
        + WINDOW,
        "/opt/imx-gpu-sdk/GLES2/Blur___Wayland_XDG/GLES2.Blur___Wayland_XDG " + WINDOW,
        "/opt/imx-gpu-sdk/GLES2/EightLayerBlend___Wayland_XDG/GLES2.EightLayerBlend___Wayland_XDG "
        + WINDOW,
        "/opt/imx-gpu-sdk/GLES2/FractalShader___Wayland_XDG/GLES2.FractalShader___Wayland_XDG "
        + WINDOW,
        "/opt/imx-gpu-sdk/GLES2/LineBuilder101___Wayland_XDG/GLES2.LineBuilder101___Wayland_XDG "
        + WINDOW,
        "/opt/imx-gpu-sdk/GLES2/S03_Transform___Wayland_XDG/GLES2.S03_Transform___Wayland_XDG "
        + WINDOW,
        "/opt/imx-gpu-sdk/GLES2/S04_Projection___Wayland_XDG/GLES2.S04_Projection___Wayland_XDG "
        + WINDOW,
        "/opt/imx-gpu-sdk/GLES2/S06_Texturing___Wayland_XDG/GLES2.S06_Texturing___Wayland_XDG "
        + WINDOW,
        "/opt/imx-gpu-sdk/GLES2/S07_EnvMapping___Wayland_XDG/GLES2.S07_EnvMapping___Wayland_XDG "
        + WINDOW,
        "/opt/imx-gpu-sdk/GLES2/S08_EnvMappingRefraction___Wayland_XDG/GLES2.S08_EnvMappingRefraction___Wayland_XDG "
        + WINDOW,
        "/home/root/.nxp-demo-experience/scripts/audio/voice/sleep.sh",
    ]

    def __init__(self):
        """Creates the loading window and then shows it"""
        super().__init__()

        self.commands = []
        self.commands_missing = True
        self.demo = None

        self.set_default_size(450, -1)
        self.set_resizable(False)
        self.set_border_width(10)

        header = Gtk.HeaderBar()
        header.set_title("i.MX Voice Control Demo")
        header.set_subtitle("Voice Solutions")
        self.set_titlebar(header)

        self.quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        self.quit_button.add(quit_image)
        header.pack_end(self.quit_button)
        self.quit_button.connect("clicked", Gtk.main_quit)

        self.main_grid = Gtk.Grid(
            row_homogeneous=False,
            column_homogeneous=True,
            column_spacing=15,
            row_spacing=15,
        )
        self.main_grid.set_margin_end(10)
        self.main_grid.set_margin_start(10)
        self.lpv_button = Gtk.CheckButton.new_with_label(label="Use Cortex-M Core")
        self.warning_label = Gtk.Label.new(
            "To use low power voice, please follow the instructions in\n"
            "the i.MX Linux User's Guide (8.3.4) to set up the Cortex-M\n"
            "core. The suspend fuction will only suspend the system when\n"
            "using Cortex-M Core."
        )
        self.start_start = Gtk.Button(label="Start")
        self.status_label = Gtk.Label.new("")
        self.start_start.connect("clicked", self.kick_off)
        self.main_grid.attach(self.warning_label, 0, 0, 1, 1)
        self.main_grid.attach(self.lpv_button, 0, 1, 1, 1)
        self.main_grid.attach(self.start_start, 0, 2, 1, 1)
        self.main_grid.attach(self.status_label, 0, 3, 1, 1)
        self.add(self.main_grid)

    def kick_off(self, unused):
        GLib.idle_add(self.start_start.set_sensitive, False)
        GLib.idle_add(self.lpv_button.set_sensitive, False)
        voice_start = threading.Thread(target=self.start_up)
        voice_start.start()

    def start_up(self):
        """Sets up VoiceSpot and VoiceSeeker"""
        GLib.idle_add(self.status_label.set_text, "Loading required modules...")
        res = subprocess.getstatusoutput("modprobe snd-aloop")
        if res[0] != 0:
            GLib.idle_add(self.status_label.set_text, "\n\nMissing snd-aloop.ko!")
            return
        GLib.idle_add(self.status_label.set_text, "Setting configuration files...")
        subprocess.getstatusoutput("cp /etc/asound.conf /etc/asound_org.conf")
        board = subprocess.check_output(["cat", "/sys/devices/soc0/soc_id"]).decode(
            "utf-8"
        )[:-1]
        if board == "i.MX8MP":
            if self.lpv_button.get_active():
                res = subprocess.getstatusoutput(
                    "cp /unit_tests/nxp-afe/asound.conf_imx8mp /etc/"
                    "asound.conf"
                )
            else:
                res = subprocess.getstatusoutput(
                    "cp /unit_tests/nxp-afe/asound.conf_imx8mp /etc/asound.conf"
                )
        else:
            if self.lpv_button.get_active():
                res = subprocess.getstatusoutput(
                    "cp /unit_tests/nxp-afe/asound.conf_imx8mm /etc/"
                    "asound.conf"
                )
            else:
                res = subprocess.getstatusoutput(
                    "cp /unit_tests/nxp-afe/asound.conf_imx8mm /etc/asound.conf"
                )
        if res[0] != 0:
            GLib.idle_add(self.status_label.set_text, "Configure files not found!")
            return
        GLib.idle_add(self.status_label.set_text, "Starting Voice UI and VoiceSpot...")
        try:
            self.voicespot = subprocess.Popen(
                [
                    "script",
                    "-q",
                    "-c",
                    "/home/root/.nxp-demo-experience/bin/voice_ui_app",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except:
            GLib.idle_add(self.status_label.set_text, "Failed to launch Voice UI!")
            return
        vs_watch = threading.Thread(target=self.handle_voicespot)
        vs_watch.start()
        GLib.idle_add(self.status_label.set_text, "Starting VoiceSeekerLite...")
        try:
            self.voiceseeker = subprocess.Popen(
                ["/unit_tests/nxp-afe/afe", "libvoiceseekerlight"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
        except:
            GLib.idle_add(self.status_label.set_text, "Failed to start VoiceSeekerLite")
            return
        vse_watch = threading.Thread(target=self.handle_voiceseeker)
        vse_watch.start()
        GLib.idle_add(self.status_label.set_text, "Finishing up...")
        # Wait until commands are read from VIT model
        while self.commands_missing:
            time.sleep(0.1)
        self.quit_button.connect("clicked", self.quit_demo)
        GLib.idle_add(self.start_main)

    def start_main(self):
        """Transitions the GUI to main operating mode"""
        ww_label = Gtk.Label.new("Wake word:                        \n'HEY NXP'")
        command_string = "List of commands:\n"
        for command in self.commands:
            command_string = command_string + command + "\n"
        phrases_label = Gtk.Label.new(command_string[:-1])
        self.command_label = Gtk.Label.new("Last command:\nN/A")
        self.status_label = Gtk.Label.new("Waiting for wake word...")
        self.main_grid2 = Gtk.Grid(
            row_homogeneous=False,
            column_homogeneous=True,
            column_spacing=15,
            row_spacing=15,
        )
        self.main_grid2.attach(ww_label, 0, 0, 1, 1)
        self.main_grid2.attach(phrases_label, 0, 1, 1, 1)
        self.main_grid2.attach(self.command_label, 1, 0, 1, 1)
        self.main_grid2.attach(self.status_label, 1, 1, 1, 1)
        self.remove(self.main_grid)
        self.add(self.main_grid2)
        self.show_all()

    def handle_voicespot(self):
        """Handles the feedback from VoiceSpot"""
        while True:
            retcode = self.voicespot.poll()
            if retcode is not None:
                GLib.idle_add(self.status_label.set_text, "VoiceSpot stopped running!")
                break
            line = self.voicespot.stdout.readline().decode("utf-8")[:-1]
            if line.startswith("trigger ="):
                GLib.idle_add(self.status_label.set_text, "Listening...")
            if line.startswith("  Number of Commands"):
                com_len = int(line.split()[5])
                self.voicespot.stdout.readline().decode("utf-8")[:-1]
                self.voicespot.stdout.readline().decode("utf-8")[:-1]
                self.voicespot.stdout.readline().decode("utf-8")[:-1]
                for i in range(com_len):
                    item = self.voicespot.stdout.readline().decode("utf-8")[3:-1]
                    self.commands.append(item)
                self.commands_missing = False
            if line.startswith(" - Voice Command detected"):
                wordarr = line.split()[4:]
                if wordarr[0] == "0" or wordarr[0] == "255":
                    word = "No valid command detected"
                else:
                    word = ""
                    for x in wordarr[1:]:
                        word = word + x + " "
                    if self.demo is not None:
                        self.demo.terminate()
                        self.demo = None
                    if wordarr[0] != "12" and wordarr[0] != "11":
                        self.demo = subprocess.Popen(
                            self.EXE[int(wordarr[0]) - 1].split()
                        )
                    if wordarr[0] == "11":
                        if self.lpv_button.get_active():
                            subprocess.Popen(self.EXE[int(wordarr[0]) - 1].split())
                        else:
                            word = word + " (Skipped)"
                GLib.idle_add(self.command_label.set_text, "Last command:\n" + word)
                GLib.idle_add(self.status_label.set_text, "Waiting for wake word...")
            if DEBUG:
                print("SPOT: " + line)

    def handle_voiceseeker(self):
        """Handles the feedback from VoiceSeeker"""
        while True:
            retcode = self.voiceseeker.poll()
            if retcode is not None:
                GLib.idle_add(
                    self.status_label.set_text, "VoiceSeekerLite stopped running!"
                )
                break
            if DEBUG:
                line = self.voiceseeker.stdout.readline().decode("utf-8")[:-1]
                print("SEEK: " + line)
            else:
                time.sleep(1)

    def quit_demo(self, object):
        """Stops the demo"""
        self.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
        if self.demo is not None:
            self.demo.terminate()
        self.voiceseeker.terminate()
        self.voicespot.terminate()
        subprocess.run(["cp", "/etc/asound_org.conf", "/etc/asound.conf"])
        Gtk.main_quit()


def main():
    """Starts the demo"""
    gui = VoiceGUI()
    gui.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
