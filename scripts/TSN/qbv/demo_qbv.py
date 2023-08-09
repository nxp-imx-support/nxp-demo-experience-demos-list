"""
Copyright 2023 NXP
SPDX-License-Identifier: BSD-3-Clause

This script provides the UI to the user, showcasing the setup diagram,
camera to be selected, ensuring the setup connectivity and starts the demo.
"""

import os
import subprocess
import paramiko
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, Gio

hostUserName = "root"
hostIP = "172.15.0.1"
hostPwd = "null"
eth0_operstate = os.popen("cat /sys/class/net/eth0/operstate").read()
eth1_operstate = os.popen("cat /sys/class/net/eth1/operstate").read()
output1 = subprocess.check_output(
    "ifconfig eth1| grep 'inet ' | awk '{print $2}'", shell=True
)
ip_address1 = output1.strip().decode()
output2 = subprocess.check_output(
    "ifconfig eth0| grep 'inet ' | awk '{print $2}'", shell=True
)
ip_address2 = output2.strip().decode()
list1 = ["Fail", "Fail"]


class DialogWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self)
        self.set_border_width(10)
        self.set_resizable(True)
        self.set_size_request(1200, 900)
        self.set_position(Gtk.WindowPosition.CENTER)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add(box)
        self.connect("destroy", Gtk.main_quit)
        header = Gtk.HeaderBar()
        header.props.title = "TSN 802.1Qbv"
        self.quit_button = Gtk.Button()
        self.quit_button.connect("clicked", self.on_stop)
        self.quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        self.quit_image = Gtk.Image.new_from_gicon(self.quit_icon, Gtk.IconSize.BUTTON)
        self.set_titlebar(header)
        self.quit_button.add(self.quit_image)
        header.pack_end(self.quit_button)
        label1 = Gtk.Label(
            label="TSN 802.1 Qbv - Enhancements to Traffic Scheduling Time-Aware Shaper - It separates communication\non the Ethernet network into a fixed length, repeating time cycles, thereby contributing to\nthe delivery of time-critical traffic."
        )
        box.pack_start(label1, True, True, 0)
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
            filename="/home/root/.nxp-demo-experience/scripts/TSN/qbv/TSN_Qbv_setup_diagram.png",
            width=900,
            height=520,
            preserve_aspect_ratio=False,
        )
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        box.pack_start(image, True, True, 0)
        label3 = Gtk.Label("Video source:")
        if (
            eth0_operstate.strip() == "up"
            and eth1_operstate.strip() == "up"
            and ip_address1 == "192.168.0.2"
            and ip_address2 == "172.15.0.5"
        ):
            ssh = paramiko.SSHClient()
            ssh.load_system_host_keys()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostIP, port=22, username=hostUserName, password=hostPwd)
            stdin, stdout, stderr = ssh.exec_command(
                "v4l2-ctl --list-devices | grep -A 9999 -i cam | tail -n +1 | grep -o '/dev/video[0-9]' | awk 'NR==1 || NR==3 || NR==5 || NR==7 || NR==9'"
            )
            output = stdout.read().decode("utf-8")
            detected_ports = output.strip().split("\n")
            print(detected_ports)
            if detected_ports in [[""]]:
                dialog = Gtk.Dialog(
                    title="Notification",
                    parent=None,
                    flags=0,
                    buttons=(Gtk.STOCK_OK, Gtk.ResponseType.OK),
                )
                image = Gtk.Image()
                image.set_from_file(
                    "/home/root/.nxp-demo-experience/scripts/TSN/qbv/TSN_Qbv_setup_diagram.png"
                )
                box_notification = Gtk.Box(
                    orientation=Gtk.Orientation.VERTICAL, spacing=6
                )
                label = Gtk.Label()
                label.set_text(
                    "Please connect a camera to the i.MX8MPlus and run the demo."
                )
                box_notification.pack_start(label, True, True, 0)
                box_notification.pack_start(image, True, True, 0)
                content_area = dialog.get_content_area()
                content_area.add(box_notification)
                dialog.show_all()
                dialog.run()
                os.system(
                    "python3 /home/root/.nxp-demo-experience/scripts/TSN/qbv/tsnqbv.py stop root 192.168.0.1"
                )
                dialog.destroy()
        else:
            dialog = Gtk.Dialog(
                title="Notification",
                parent=None,
                flags=0,
                buttons=(Gtk.STOCK_OK, Gtk.ResponseType.OK),
            )
            image = Gtk.Image()
            image.set_from_file(
                "/home/root/.nxp-demo-experience/scripts/TSN/qbv/TSN_Qbv_setup_diagram.png"
            )
            box_notification = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            label = Gtk.Label()
            label.set_text(
                """Please verify the connections and execute the "IP_plus.sh" script on the i.MX8MPlus board."""
            )
            box_notification.pack_start(label, True, True, 0)
            box_notification.pack_start(image, True, True, 0)
            content_area = dialog.get_content_area()
            content_area.add(box_notification)
            dialog.show_all()
            dialog.run()
            os.system(
                "python3 /home/root/.nxp-demo-experience/scripts/TSN/qbv/tsnqbv.py stop root 192.168.0.1"
            )
            dialog.destroy()
        videos = ["--Select Video Port--"] + detected_ports
        print(videos)
        self.video_combo = Gtk.ComboBoxText()
        self.video_combo.set_entry_text_column(0)
        self.video_combo.connect("changed", self.on_video_combo_changed)
        for video in videos:
            self.video_combo.append_text(video)
        self.video_combo.set_active(0)
        vbox = Gtk.HBox()
        vbox.add(label3)
        vbox.add(self.video_combo)
        self.button1 = Gtk.ToggleButton()
        self.button1.connect("toggled", self.on_toggle_button_toggled)
        self.update_button_text()
        self.button1.set_sensitive(False)
        box.pack_start(vbox, False, False, 0)
        box.pack_start(self.button1, False, False, 0)

    def on_toggle_button_toggled(self, button):
        if button.get_active():
            self.on_start()
        else:
            self.on_stop(button)
        self.update_button_text()

    def update_button_text(self):
        if self.button1.get_active():
            self.button1.set_label("Stop Demo")
        else:
            self.button1.set_label("Start Demo")

    def on_start(self):
        if list1[0] == "Pass" and list1[1] == "Pass":
            os.system(
                "python3 /home/root/.nxp-demo-experience/scripts/TSN/qbv/loading_window.py run_demo &"
            )
            os.system(
                "python3 /home/root/.nxp-demo-experience/scripts/TSN/qbv/tsnqbv.py start root 192.168.0.1 &"
            )
            self.button1.set_sensitive(True)
        else:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Notification",
            )
            dialog.format_secondary_text(
                "Please verify the connections or video source."
            )
            dialog.run()
            dialog.destroy()

    def on_stop(self, button):
        os.system(
            "python3 /home/root/.nxp-demo-experience/scripts/TSN/qbv/tsnqbv.py stop root 192.168.0.1 &"
        )

    def on_video_combo_changed(self, combo):
        text = combo.get_active_text()
        print(text)
        y = open("/home/root/.nxp-demo-experience/scripts/TSN/qbv/video.txt", "w")
        y.write(text)
        y.close()
        list1[0] = "Pass"
        list1[1] = "Pass"
        try:
            if text == "--Select Video Port--":
                self.button1.set_sensitive(False)
            else:
                self.button1.set_sensitive(True)
        except:
            pass


win = DialogWindow()
win.show_all()
Gtk.main()
