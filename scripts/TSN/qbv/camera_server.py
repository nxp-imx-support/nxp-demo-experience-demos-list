"""
Copyright 2023 NXP

SPDX-License-Identifier: BSD-3-Clause

This script helps for the camera streaming using gstreamer in 
server, which collects the feed and transfers via UDP.
"""

import sys
import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst, GObject, GLib

first_argument = sys.argv[1]


class ObjectDetection:
    def __init__(self):
        Gst.init()
        self.loop_1 = GLib.MainLoop()

    def cam_stream(self):
        server_command = "v4l2src device={} ! videoconvert ! video/x-raw, format=YUY2, width=640,height=480 ! jpegenc ! rtpjpegpay ! udpsink host=172.15.0.5 port=5000".format(
            first_argument
        )
        pipeline_1 = Gst.parse_launch(server_command)
        bus_1 = pipeline_1.get_bus()
        bus_1.add_signal_watch()
        pipeline_1.set_state(Gst.State.PLAYING)
        self.loop_1.run()
        self.pipeline_1.set_state(Gst.State.NULL)
        self.bus_1.remove_signal_watch()


if __name__ == "__main__":
    example = ObjectDetection()
    example.cam_stream()
