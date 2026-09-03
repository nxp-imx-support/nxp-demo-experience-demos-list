#!/usr/bin/env python3

"""
Copyright 2021-2024, 2026 NXP
SPDX-License-Identifier: BSD-3-Clause

This script manages downloads.
Runs camera setup check.
"""

import glob
import subprocess
import json
from os import makedirs
from os.path import exists

DOWNLOAD_FOLDER = "/opt/gopoint-apps/downloads"
DOWNLOAD_DB = "/opt/gopoint-apps/downloads.json"

# Lowest framerate still considered usable for a live inference preview.
# Cameras often advertise their largest geometry at 5 fps only, which
# negotiates but looks broken behind a classifier, so get_video_resolutions()
# ranks anything at or above this ahead of the slow high-resolution modes.
MIN_USABLE_FPS = 15


def download_file(file_name):
    """Downloads a file from the DOWNLOAD_DB

    Arguments:
    file_name -- Name of the file on list
    """

    # Parse database
    url = str()
    alt_url = str()
    sha = str()

    # Make sure the assets folder exists.
    # makedirs() creates any missing parent directory, and exist_ok=True keeps
    # concurrent preloads from racing each other between the check and the
    # create. Plain mkdir() failed with FileNotFoundError when the parent tree
    # was absent and with FileExistsError when two demos preloaded at once.
    makedirs(DOWNLOAD_FOLDER, exist_ok=True)

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
            "wget -O  /opt/gopoint-apps/downloads/" + file_name + " " + url
        )[0]
        if out != 0:
            out = subprocess.getstatusoutput(
                "wget -O  /opt/gopoint-apps/downloads/" + file_name + " " + alt_url
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


def get_video_devices():
    """Returns a sorted list of video device paths that can actually capture.

    Nodes are discovered through the GStreamer device monitor rather than by
    globbing /dev/video*, because not every /dev/video node is a usable
    camera. Two kinds have to be excluded:

      - Metadata nodes. A UVC webcam exposes a second node whose Device Caps
        advertise "Metadata Capture" only. Selecting it makes v4l2src fail
        with "Device '/dev/videoN' is not a capture device."
      - Capture nodes with no sensor attached. On i.MX the mxc-isi capture
        node exists even when no MIPI camera is fitted; it reports raw
        formats but every framerate is 0/0 and streaming fails on buffer
        pool activation.

    The 0/0 framerate test is the same one imx8mp_camera_demo.py already
    uses. Sorting matters because glob returns directory order, which is not
    numeric, so the first entry is not necessarily /dev/video0.

    Returns an empty list when no usable camera is present.
    """
    try:
        import gi

        gi.require_version("Gst", "1.0")
        from gi.repository import Gst
    except (ImportError, ValueError):
        return sorted(run_check())

    if not Gst.is_initialized():
        Gst.init(None)

    monitor = Gst.DeviceMonitor()
    monitor.add_filter("Video/Source")
    monitor.start()

    cameras = []
    for device in monitor.get_devices():
        path = device.get_properties().get_string("device.path")
        if not path:
            continue
        caps = device.get_caps()
        if caps is None:
            continue
        caps = caps.normalize()
        framerates = []
        for index in range(caps.get_size()):
            structure = caps.get_structure(index)
            if structure.get_name() != "video/x-raw":
                continue
            framerates.append(
                "{}/{}".format(*structure.get_fraction("framerate")[1:])
            )
        # No raw caps at all means a metadata-only node; all-zero framerates
        # mean a capture node with nothing connected to it.
        if framerates and not all(rate == "0/0" for rate in framerates):
            cameras.append(path)

    monitor.stop()
    return sorted(cameras)


def get_video_resolutions(device_path):
    """Returns a list of "WIDTHxHEIGHT@FPS" strings the device can really do.

    The demos used to offer a hardcoded list such as ["1920x1080@15",
    "640x480@30"] no matter which camera was selected. That is wrong whenever
    the camera cannot do the entry that happens to be first, and the user has
    no way to tell: the pipeline just fails with "not-negotiated" on Start.
    A Logitech StreamCam is a real example - at 1080p it offers raw YUY2 at
    5 fps only, and the 15 fps the list advertised exists solely as MJPG.

    Only plain video/x-raw structures are considered. Two other kinds of caps
    are deliberately skipped:

      - image/jpeg. v4l2src will decode MJPG transparently, so a 1080p@15
        entry looks negotiable in isolation, but as soon as a converter is
        downstream the pipeline fails. The demos always have a converter, so
        advertising an MJPG-only mode would recreate the original defect.
      - video/x-raw with format=DMA_DRM. These are the dmabuf variants and
        they advertise framerates the system-memory path cannot deliver.

    Only one entry is kept per resolution, at the highest framerate that
    resolution supports, because a camera typically advertises the same
    geometry at every framerate down to 5 fps and listing all of them makes
    the drop-down unusable. A StreamCam yields 52 raw modes but only 10
    distinct resolutions.

    Ordering puts modes that reach MIN_USABLE_FPS first, largest area first
    within that group, and the slow high-resolution modes after them. Entry 0
    is therefore the largest geometry that still moves at a sensible framerate
    rather than the largest geometry outright - on a StreamCam that is
    960x540@15, not 1920x1080@5, which is the biggest mode the camera can do
    but too slow to classify a moving subject. Returns an empty list when the
    caps cannot be read, and the caller is expected to fall back to its own
    list in that case.
    """
    try:
        import gi

        gi.require_version("Gst", "1.0")
        from gi.repository import Gst
    except (ImportError, ValueError):
        return []

    if not Gst.is_initialized():
        Gst.init(None)

    monitor = Gst.DeviceMonitor()
    monitor.add_filter("Video/Source")
    monitor.start()

    modes = set()
    for device in monitor.get_devices():
        if device.get_properties().get_string("device.path") != device_path:
            continue
        caps = device.get_caps()
        if caps is None:
            continue
        # normalize() expands the { 480, 360 } style lists into one structure
        # per concrete value, so each structure below is a single mode.
        caps = caps.normalize()
        for index in range(caps.get_size()):
            structure = caps.get_structure(index)
            if structure.get_name() != "video/x-raw":
                continue
            if structure.get_string("format") == "DMA_DRM":
                continue
            ok_w, width = structure.get_int("width")
            ok_h, height = structure.get_int("height")
            ok_f, num, den = structure.get_fraction("framerate")
            if not (ok_w and ok_h and ok_f) or den == 0:
                continue
            # Skip framerates that are not a whole number of frames per
            # second. The demos pass the rate to the example as an integer
            # "-r W,H,FPS", so a cap such as 15/2 (7.5 fps) cannot be
            # expressed. Truncating it to 7 asks the camera for a rate it
            # never advertised and the pipeline dies with an internal data
            # stream error. A StreamCam advertises 1600x896 at 15/2 and 5/1
            # only, so this is what keeps that entry honest at 5 fps.
            if num % den != 0:
                continue
            fps = num // den
            # 0/0 means a capture node with no sensor attached.
            if fps <= 0:
                continue
            modes.add((width, height, fps))

    monitor.stop()

    # Collapse to one entry per resolution, keeping its fastest framerate.
    fastest = {}
    for width, height, fps in modes:
        key = (width, height)
        if fps > fastest.get(key, 0):
            fastest[key] = fps

    # Sort so usable framerates come first, then largest area, then framerate.
    ordered = sorted(
        ((w, h, f) for (w, h), f in fastest.items()),
        key=lambda m: (m[2] >= MIN_USABLE_FPS, m[0] * m[1], m[2]),
        reverse=True,
    )
    return ["{}x{}@{}".format(w, h, f) for w, h, f in ordered]


def parse_resolution(resolution, fallback=(640, 480, 30)):
    """Splits a "WIDTHxHEIGHT@FPS" string into an (width, height, fps) tuple.

    The demos used to test the drop-down value against one literal string and
    silently fall back to 640x480@30 for anything else, so any mode added to
    the list would have been accepted by the UI and then ignored. Parsing the
    value keeps the drop-down honest whatever it contains.
    """
    try:
        geometry, _, rate = resolution.partition("@")
        width, _, height = geometry.partition("x")
        return int(width), int(height), int(rate)
    except (AttributeError, ValueError):
        return fallback


# Device-tree node name of the MIPI-CSI sensor the i.MX 95 demos drive through
# libcamera, and the i2c address it answers on.
OS08A20_NODE = "os08a20_mipi@36"


def get_os08a20_device_path():
    """Finds the OS08A20's device-tree path, or returns None if it is absent.

    The demos used to hardcode
    /base/soc/bus@42000000/i2c@42530000/os08a20_mipi@36 as LIBCAMERA_CAM_DEVICE.
    That is only correct for one family of device trees: the same sensor sits on
    i2c@42540000 on some 15x15 FRDM DTBs and on i2c@44350000 on the -combo ones,
    so a hardcoded bus address makes the demo fail on a board that is wired
    perfectly well. Discovering the node instead means any DTB that exposes the
    sensor works.

    Returning None also lets a caller tell "no sensor fitted" from "sensor
    present", which the platform check alone cannot do - an FRDM-IMX95 with no
    camera reports the same soc_id as an EVK with one.

    libcamera expects the path rooted at /base, which is how it prints the
    device, while the kernel exposes the same tree under
    /sys/firmware/devicetree/base. Only the /sys/firmware/devicetree prefix is
    stripped, so the /base component survives and the returned string is the
    form libcamera matches on. Stripping /base as well yields /soc/... which is
    how procfs names the tree but not something libcamera recognises.

    The globs are tried shallowest first so the match is the shortest path that
    contains the node, and each candidate list is sorted to keep the result
    stable when a DTB somehow exposes the sensor twice.
    """
    prefix = "/sys/firmware/devicetree"
    for depth in ("*/i2c@*/", "*/*/i2c@*/", "*/*/*/i2c@*/"):
        matches = sorted(glob.glob(prefix + "/base/" + depth + OS08A20_NODE))
        if matches:
            return matches[0][len(prefix):]
    return None


def run_check():
    """
    Returns list of device path if camera detected,
    else returns empty list


    Kept for compatibility. Prefer get_video_devices(), which also filters
    out metadata-only nodes and capture nodes with no sensor attached.
    """
    devices = sorted(glob.glob("/dev/video*"))

    camera = []
    for device in devices:
        # Read the Device Caps block only. The "Capabilities" block above it
        # describes the whole physical device, so a webcam's metadata node
        # lists "Video Capture" there even though the node itself cannot
        # capture, which made the previous whole-output grep accept it.
        dev = (
            "v4l2-ctl -d "
            + device
            + " --info | sed -n '/Device Caps/,/^\\t[^\\t]/p'"
            + ' | grep -c "Video Capture"'
        )
        check_output = subprocess.getoutput(dev)
        if int(check_output) > 0:
            camera.append(device)
    return camera
