#!/usr/bin/env python3

"""
Copyright 2021-2023 NXP

SPDX-License-Identifier: BSD-2-Clause

This script manages downloads.
Runs camera setup check.

"""

from os.path import exists
import subprocess
import glob

DOWNLOAD_FOLDER = "/home/root/.cache/gopoint/"
DOWNLOAD_DB = "/home/root/.nxp-demo-experience/downloads.txt"


def download_file(name):
    """Downloads a file from the DOWNLOAD_DB

    Arguments:
    name -- Name of the file on list
    """

    # Parse database
    path = ""
    url = ""
    alt_url = ""
    sha = ""
    found = False
    downloads = open(DOWNLOAD_DB, "r").read().splitlines()
    for i in range(len(downloads)):
        if downloads[i] == "name:" + name:
            path = downloads[i + 1][5:]
            url = downloads[i + 2][4:]
            alt_url = downloads[i + 3][8:]
            sha = downloads[i + 4][4:]
            found = True
    if not found:
        return -1

    # Check where file exists
    if exists(path):
        loc = path
    elif exists(DOWNLOAD_FOLDER + name):
        loc = DOWNLOAD_FOLDER + name
    else:
        out = subprocess.getstatusoutput(
            "wget -O  /home/root/.cache/demoexperience/" + name + " " + url
        )[0]
        if out != 0:
            out = subprocess.getstatusoutput(
                "wget -O  /home/root/.cache/demoexperience/" + name + " " + alt_url
            )[0]
        if out != 0:
            return -2
        loc = DOWNLOAD_FOLDER + name

    # SHA1 Check (if available)
    sha_check = ["sha1sum", loc, "-z"]
    check_process = subprocess.Popen(sha_check, stdout=subprocess.PIPE)
    if sha != "" and sha != check_process.stdout.read().split()[0].decode("utf-8"):
        return -3
    return loc

def run_check():
    """
    Returns list of device path if camera detected,
    else returns empty list
    """
    devices = []
    for device in glob.glob('/dev/video*'):
        devices.append(device)
    camera = []
    for dv in devices:
        dev = 'v4l2-ctl -d ' + dv + ' -D | grep "Video Capture" | wc -l'
        checkOutput = subprocess.getoutput(dev)
        if int(checkOutput) > 0 :
            camera.append(dv)
    return camera
