"""
Copyright 2023 NXP

SPDX-License-Identifier: BSD-3-Clause

This script triggers to configure IP to the interfaces,
and opens the UI page for the demo.
"""

import os
import time

os.system(
    "python3 /home/root/.nxp-demo-experience/scripts/TSN/qbv/loading_window.py launch &"
)
os.system("sh /home/root/.nxp-demo-experience/scripts/TSN/qbv/IP_mini.sh")
time.sleep(1)
os.system("python3 /home/root/.nxp-demo-experience/scripts/TSN/qbv/demo_qbv.py")
