#!/usr/bin/env python3

"""
Copyright 2021-2024 NXP
SPDX-License-Identifier: BSD-2-Clause

This script manages downloads.
Runs camera setup check.
"""

import glob
import subprocess
import json
from os import mkdir
from os.path import exists

DOWNLOAD_FOLDER = "/home/root/.cache/gopoint"
DOWNLOAD_DB = "/home/root/.nxp-demo-experience/downloads.json"


def download_file(file_name):
    """Downloads a file from the DOWNLOAD_DB

    Arguments:
    file_name -- Name of the file on list
    """

    # Parse database
    url = str()
    alt_url = str()
    sha = str()

    # Check if assets folder exists
    if not exists(DOWNLOAD_FOLDER):
        mkdir(DOWNLOAD_FOLDER)

    # Read downloads.json file
    with open(DOWNLOAD_DB, encoding="utf-8") as downloads_json:
        database = json.load(downloads_json)

    # Look for requested file
    if file_name in database:
        url = database[file_name][0]["url"]
        alt_url = database[file_name][0]["alt_url"]
        sha = database[file_name][0]["sha"]
    else:
        return -1

    # Check where file exists
    if exists(DOWNLOAD_FOLDER + "/" + file_name):
        path = DOWNLOAD_FOLDER + "/" + file_name
    else:
        out = subprocess.getstatusoutput(
            "wget -O  /home/root/.cache/gopoint/" + file_name + " " + url
        )[0]
        if out != 0:
            out = subprocess.getstatusoutput(
                "wget -O  /home/root/.cache/gopoint/" + file_name + " " + alt_url
            )[0]
        if out != 0:
            return -2
        path = DOWNLOAD_FOLDER + "/" + file_name

    # SHA1 Check (if available)
    sha_check = ["sha1sum", path]
    with subprocess.Popen(sha_check, stdout=subprocess.PIPE) as check_process:
        if sha != "":
            if sha != check_process.stdout.read().split()[0].decode("utf-8"):
                return -3
        return path


def run_check():
    """
    Returns list of device path if camera detected,
    else returns empty list
    """
    devices = []
    for device in glob.glob("/dev/video*"):
        devices.append(device)

    camera = []
    for device in devices:
        dev = "v4l2-ctl -d " + device + ' -D | grep "Video Capture" | wc -l'
        check_output = subprocess.getoutput(dev)
        if int(check_output) > 0:
            camera.append(device)
    return camera
