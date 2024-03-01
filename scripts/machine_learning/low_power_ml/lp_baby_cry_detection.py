#!/usr/bin/env python3

# Copyright 2023-2024 NXP
# SPDX-License-Identifier: BSD-3-Clause

import os
import sys

sys.path.append("/home/root/.nxp-demo-experience/scripts/")
import utils

utils.download_file("lp_baby_detection.elf")

os.system('echo "Start demo..."')
os.system(
    "echo /home/root/.cache/gopoint/lp_baby_detection.elf > /sys/class/remoteproc/remoteproc0/firmware"
)
os.system("echo start > /sys/class/remoteproc/remoteproc0/state")
os.system("sleep 1")
os.system('echo "Suspend Linux..."')
os.system("echo mem > /sys/power/state")
os.system("sleep 1")
os.system("echo stop > /sys/class/remoteproc/remoteproc0/state")
os.system('echo "Demo finished!"')
