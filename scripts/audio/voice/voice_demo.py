"""
Copyright 2022 NXP Semiconductors
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
        "/opt/imx-gpu-sdk/GLES2/Bloom/GLES2.Bloom_Wayland " + WINDOW,
        "/opt/imx-gpu-sdk/GLES2/Blur/GLES2.Blur_Wayland " + WINDOW,
        "/opt/imx-gpu-sdk/GLES2/EightLayerBlend/GLES2.EightLayerBlend_Wayland "
         + WINDOW,
        "/opt/imx-gpu-sdk/GLES2/FractalShader/GLES2.FractalShader_Wayland "
        + WINDOW,
        "/opt/imx-gpu-sdk/GLES2/LineBuilder101/GLES2.LineBuilder101_Wayland "
        + WINDOW,
        "/opt/imx-gpu-sdk/GLES2/S03_Transform/GLES2.S03_Transform_Wayland "
        + WINDOW,
        "/opt/imx-gpu-sdk/GLES2/S04_Projection/GLES2.S04_Projection_Wayland "
        + WINDOW,
        "/opt/imx-gpu-sdk/GLES2/S06_Texturing/GLES2.S06_Texturing_Wayland "
        + WINDOW ,
        "/opt/imx-gpu-sdk/GLES2/S07_EnvMapping/GLES2.S07_EnvMapping_Wayland "
        + WINDOW ,
        "/opt/imx-gpu-sdk/GLES2/S08_EnvMappingRefraction/GLES2.S08_EnvMapping"
        "Refraction_Wayland " + WINDOW,
        "/opt/viv_samples/tiger/tiger"
    ]

    def __init__(self):
        """Creates the loading window and then shows it"""
        super().__init__()

        self.commands = []
        self.commands_missing = True
        self.demo = None

        self.set_default_size(450, 200)
        self.set_resizable(False)
        self.set_border_width(10)

        header = Gtk.HeaderBar()
        header.set_title("i.MX Voice Control Demo")
        header.set_subtitle("Voice Solutions")
        self.set_titlebar(header)

        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        header.pack_end(quit_button)
        quit_button.connect("clicked", self.quit_demo)

        self.main_grid = Gtk.Grid(
            row_homogeneous=False, column_homogeneous=True,
            column_spacing=15, row_spacing=15)
        self.main_grid.set_margin_end(10)
        self.main_grid.set_margin_start(10)
        self.status_label = Gtk.Label.new("Setting up...")
        self.main_grid.attach(self.status_label, 0, 0, 1, 1)
        self.add(self.main_grid)

    def start_up(self):
        """Sets up VoiceSpot and VoiceSeeker"""
        GLib.idle_add(self.status_label.set_text,
            "\n\nLoading required modules...")
        res = subprocess.getstatusoutput(
            "modprobe snd-aloop"
        )
        if res[0] != 0:
            GLib.idle_add(self.status_label.set_text,
            "\n\nMissing snd-aloop.ko!")
            return
        GLib.idle_add(self.status_label.set_text,
            "\n\nSetting configuration files...")
        subprocess.getstatusoutput(
            "cp /etc/asound.conf /etc/asound_org.conf"
        )
        board = subprocess.check_output(
            ['cat', '/sys/devices/soc0/soc_id']
        ).decode('utf-8')[:-1]
        if board == "i.MX8MP":
            res = subprocess.getstatusoutput(
                "cp /unit_tests/nxp-afe/asound.conf_imx8mp /etc/asound.conf"
            )
        else:
            res = subprocess.getstatusoutput(
                "cp /unit_tests/nxp-afe/asound.conf /etc/asound.conf"
            )
        if res[0] != 0:
            GLib.idle_add(self.status_label.set_text,
                "\n\nConfigure files not found!")
            return
        GLib.idle_add(self.status_label.set_text,
            "\n\nStarting Voice UI and VoiceSpot...")
        try:
            self.voicespot = subprocess.Popen(
                ['script', '-q', '-c',
                '/home/root/.nxp-demo-experience/bin/voice_ui_app'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
        except:
            GLib.idle_add(self.status_label.set_text,
                "\n\nFailed to launch Voice UI!")
            return
        vs_watch = threading.Thread(
            target=self.handle_voicespot)
        vs_watch.start()
        GLib.idle_add(self.status_label.set_text,
            "\n\nStarting VoiceSeekerLite...")
        try:
            self.voiceseeker = subprocess.Popen(
                ['/unit_tests/nxp-afe/afe', 'libvoiceseekerlight'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT)
        except:
            GLib.idle_add(self.status_label.set_text,
                "\n\nFailed to start VoiceSeekerLite")
            return
        vse_watch = threading.Thread(
            target=self.handle_voiceseeker)
        vse_watch.start()
        GLib.idle_add(self.status_label.set_text,
            "\n\nFinishing up...")
        # Wait until commands are read from VIT model
        while(self.commands_missing):
            time.sleep(0.1)
        GLib.idle_add(self.start_main)
    
    def start_main(self):
        """Transitions the GUI to main operating mode"""
        ww_label = Gtk.Label.new(
            "Wake word:                        \n\'HEY NXP\'")
        command_string = 'List of commands:\n'
        for command in self.commands:
            command_string = command_string + command + '\n'
        phrases_label = Gtk.Label.new(command_string[:-1])
        self.command_label =  Gtk.Label.new("Last command:\nN/A")
        self.status_label =  Gtk.Label.new("Waiting for wake word...")
        self.main_grid.remove_row(0)
        self.main_grid.attach(ww_label, 0, 0, 1, 1)
        self.main_grid.attach(phrases_label, 0, 1, 1, 1)
        self.main_grid.attach(self.command_label, 1, 0, 1, 1)
        self.main_grid.attach(self.status_label, 1, 1, 1, 1)
        self.show_all()
        
    def handle_voicespot(self):
        """Handles the feedback from VoiceSpot"""
        while True:
            retcode = self.voicespot.poll()
            if retcode is not None:
                GLib.idle_add(self.status_label.set_text,
                    "VoiceSpot stopped running!")
                break
            line = self.voicespot.stdout.readline().decode("utf-8")[:-1]
            if line.startswith("trigger ="):
                GLib.idle_add(self.status_label.set_text,
                    "Listening...")
            if line.startswith("  Number of Commands"):
                com_len = int(line.split()[5])
                self.voicespot.stdout.readline().decode("utf-8")[:-1]
                for i in range(com_len):
                    item = self.voicespot.stdout.readline().decode(
                        "utf-8")[3:-1]
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
                    if self.demo != None:
                            self.demo.terminate()
                            self.demo = None
                    if wordarr[0] != "12":
                        self.demo = subprocess.Popen(
                            self.EXE[int(wordarr[0])-1].split())
                GLib.idle_add(self.command_label.set_text,
                    "Last command:\n" + word)
                GLib.idle_add(self.status_label.set_text,
                    "Waiting for wake word...")
            if DEBUG:
                print("SPOT: " + line)
    
    def handle_voiceseeker(self):
        """Handles the feedback from VoiceSeeker"""
        while True:
            retcode = self.voiceseeker.poll()
            if retcode is not None:
                GLib.idle_add(self.status_label.set_text,
                    "VoiceSeekerLite stopped running!")
                break
            if DEBUG:
                line = self.voiceseeker.stdout.readline().decode("utf-8")[:-1]
                print("SEEK: " + line)
            else:
                time.sleep(1)
    
    def quit_demo(self, object):
        """Stops the demo"""
        self.get_window().set_cursor(Gdk.Cursor(Gdk.CursorType.WATCH))
        if self.demo != None:
            self.demo.terminate()
        self.voiceseeker.terminate()
        self.voicespot.terminate()
        subprocess.run(
            ["cp", "/etc/asound_org.conf", "/etc/asound.conf"]
        )
        Gtk.main_quit()

def main():
    """Starts the demo"""
    gui = VoiceGUI()
    gui.show_all()
    voice_start = threading.Thread(
        target=gui.start_up)
    voice_start.start()
    Gtk.main()

if __name__ == "__main__":
    main()
