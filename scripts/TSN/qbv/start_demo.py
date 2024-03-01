"""
Copyright 2023 NXP

SPDX-License-Identifier: BSD-3-Clause

This script triggers to configure IP to the interfaces,
and opens the UI page for the demo.
"""

import os
import time
import subprocess
import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

def show_dialog(message, title):
    dialog = Gtk.MessageDialog(None, 0, Gtk.MessageType.INFO, Gtk.ButtonsType.OK, message)
    dialog.set_title(title)
    dialog.run()
    dialog.destroy()
    
#Get information of system
device = subprocess.check_output(
    "hostname",shell=True
)

os.system(
    "python3 /home/root/.nxp-demo-experience/scripts/TSN/qbv/loading_window.py launch &"
)
#check if device is i.MX8mmevk
if (b'8mm' in device):
    os.system("sh /home/root/.nxp-demo-experience/scripts/TSN/qbv/IP_mini.sh")
    time.sleep(1)
    os.system("python3 /home/root/.nxp-demo-experience/scripts/TSN/qbv/demo_qbv.py")

#check if device is i.MX8MPevk
elif (b'8mp' in device):
    os.system("sh /home/root/.nxp-demo-experience/scripts/TSN/qbv/IP_plus.sh")
    time.sleep(1)
    output1 = subprocess.check_output(
        "ifconfig eth0| grep 'inet ' | awk '{print $2}'", shell=True
    )
    ip_eth0 = output1.strip().decode()
    output2 = subprocess.check_output(
        "ifconfig eth1| grep 'inet ' | awk '{print $2}'", shell=True
    )
    ip_eth1 = output2.strip().decode()
    message = f"Eth0 ip address:{ip_eth0}\nEth1 ip address:{ip_eth1}\nNow run demo on i.MX8Mmini"
    title = "IP addresses"
    show_dialog(message,title)

