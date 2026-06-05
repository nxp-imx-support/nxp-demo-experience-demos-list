"""
Copyright 2023-2024 NXP

SPDX-License-Identifier: BSD-3-Clause

This script triggers to configure IP to the interfaces,
and opens the UI page for the demo.
"""

import os
import time
import subprocess
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk


def show_dialog(message, title):
    dialog = Gtk.MessageDialog(
        None, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.OK, message
    )
    dialog.set_title(title)
    dialog.run()
    dialog.destroy()


# Get information of system
device = subprocess.check_output("hostname", shell=True)
if b"8mm" in device or b"8mp" in device:
    FIRST_INTERFACE = "eth0"
    SECOND_INTERFACE = "eth1"
elif b"943" in device:
    FIRST_INTERFACE = "eth1"
    SECOND_INTERFACE = "eth2"

os.system("python3 /opt/gopoint-apps/scripts/communication/TSN-Qbv/loading_window.py launch &")
# Check function (Camera or Display])

case = subprocess.check_output("ls /tmp/TSN_demo*", shell=True)
os.system("rm /tmp/TSN_demo*")
print(case)

if b"display" in case:
    os.system("sh /opt/gopoint-apps/scripts/communication/TSN-Qbv/IP_mini.sh")
    time.sleep(1)
    os.system("python3 /opt/gopoint-apps/scripts/communication/TSN-Qbv/demo_qbv.py")

elif b"camera" in case:
    os.system("sh /opt/gopoint-apps/scripts/communication/TSN-Qbv/IP_plus.sh")
    time.sleep(1)
    output1 = subprocess.check_output(
        f"ifconfig {FIRST_INTERFACE}| grep 'inet ' | awk '{{print $2}}'", shell=True
    )
    ip_eth0 = output1.strip().decode()
    output2 = subprocess.check_output(
        f"ifconfig {SECOND_INTERFACE}| grep 'inet ' | awk '{{print $2}}'", shell=True
    )
    ip_eth1 = output2.strip().decode()
    message = f"{FIRST_INTERFACE} ip address:{ip_eth0}\n{SECOND_INTERFACE} ip address:{ip_eth1}\nNow run demo on i.MX8Mmini"
    title = "IP addresses"
    show_dialog(message, title)
