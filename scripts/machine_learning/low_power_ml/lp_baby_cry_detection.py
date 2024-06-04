#!/usr/bin/env python3

"""
Copyright 2023-2024 NXP
SPDX-License-Identifier: BSD-3-Clause

This script runs lp baby crying/glass breaking detection demo
"""

import os
import sys
import subprocess
from MSGsend import MSG_client

sys.path.append("/opt/gopoint-apps/scripts/")
import utils

if __name__ == "__main__":
    os.system('echo "\nStart demo" > /dev/console')
    os.system('echo "Downloading application elf..." > /dev/console')
    elf_file = utils.download_file("lp_baby_detection.elf")
    if elf_file == -1:
        os.system('echo "Cannot find files!" > /dev/console')
        os.system(
            'echo "Make sure required files are available in downloads database!" > /dev/console'
        )
        sys.exit(1)
    if elf_file == -2:
        os.system('echo "Download failed!" > /dev/console')
        os.system(
            'echo "Please make sure you have internet connection on the target and try again." > /dev/console'
        )
        sys.exit(1)
    if elf_file == -3:
        os.system('echo "Downloaded corrupted file!" > /dev/console')
        os.system(
            'echo "Please clean /opt/gopoint-apps/downloads/ and try to download again." > /dev/console'
        )
        sys.exit(1)
    os.system(
        "echo /opt/gopoint-apps/downloads/lp_baby_detection.elf > /sys/class/remoteproc/remoteproc0/firmware"
    )
    os.system("echo start > /sys/class/remoteproc/remoteproc0/state")
    os.system("sleep 1")
    os.system('echo "Suspend Linux..." > /dev/console')
    os.system("echo mem > /sys/power/state")
    os.system("sleep 1")
    os.system("modprobe imx_rpmsg_tty")
    os.system("sleep 1")
    os.system("stty -echo -F /dev/ttyRPMSG30")
    MSGprocess = subprocess.Popen(
        "cat /dev/ttyRPMSG30 &", shell=True, stdout=subprocess.PIPE
    )
    os.system('echo "wake up reason" > /dev/ttyRPMSG30')
    process = subprocess.Popen(
        "ps aux | grep -v grep | grep 'cat /dev/ttyRPMSG30' | awk '{print $2}'",
        shell=True,
        stdout=subprocess.PIPE,
    )
    pid = process.stdout.read().decode("utf-8").strip()
    os.system(f"kill -9 {pid}")

    Msg, _ = MSGprocess.communicate()
    Msg = Msg.decode("utf-8").strip()
    os.system(f'echo "LP_ML Demo: Detected {Msg}" > /dev/console')

    if Msg in ("glass breaking", "baby crying"):
        print("sending notification to server")
        client = MSG_client(server_ip="127.0.0.1")
        client.connect()
        client.send_msg(f"{Msg} Detected")
        client.close()
        print("Finished sending")

    os.system("echo stop > /sys/class/remoteproc/remoteproc0/state")
    os.system('echo "Demo finished!" > /dev/console')
