"""
Copyright 2021-2024 NXP
SPDX-License-Identifier: BSD-3-Clause

i.MX8M Plus camera demo.
"""

from argparse import ArgumentParser
from subprocess import Popen
import sys
import gi

from gi.repository import Gst, Gtk

gi.require_version("Gst", "1.0")
gi.require_version("Gtk", "3.0")


CAM_PIPELINE = "gst-launch-1.0 v4l2src device={} ! waylandsink"

ENC_PIPELINE = (
    "gst-launch-1.0 v4l2src device={} ! imxvideoconvert_g2d !"
    " queue ! vpuenc_hevc ! multiqueue ! vpudec ! waylandsink"
)

MULTI_CAM_PIPELINE = (
    "gst-launch-1.0 imxcompositor_g2d name=c "
    "sink_0::xpos=0 sink_0::ypos=0 sink_0::width=1920 "
    "sink_0::height=1080 sink_0::keep-ratio=true "
    "sink_1::xpos=0 sink_1::ypos=0 sink_1::width=640 "
    "sink_1::height=480 sink_1::keep-ratio=true ! "
    "waylandsink sync=false "
    "v4l2src device={} ! video/x-raw,width=1920,height=1080,framerate=30/1 ! "
    "imxvideoconvert_g2d ! c.sink_0 "
    "v4l2src device={} ! video/x-raw,width=640,height=480,framerate=30/1 ! "
    "imxvideoconvert_g2d ! c.sink_1"
)


class MessageWindow(Gtk.Window):
    """Window to show messages to the user."""

    def __init__(self, message):
        """Create the message window."""
        Gtk.Window.__init__(self, title="Warning")
        self.set_default_size(640, 480)

        box = Gtk.Box()
        box.set_homogeneous(True)

        self.label = Gtk.Label.new(message)
        box.pack_start(self.label, True, True, 0)
        self.add(box)


class SelectCamWindow(Gtk.Window):
    """Main UI Window."""

    def __init__(self, func):
        """Create the UI window."""
        Gtk.Window.__init__(self, title="i.MX 8M Plus Camera Demo")
        self.set_default_size(640, 480)
        self.device = ""
        self.func = func

        box = Gtk.VBox()

        label = Gtk.Label.new("Select the video capture device:")
        box.pack_start(label, False, False, 20)

        dev_combo = Gtk.ComboBoxText()
        dev_combo.set_entry_text_column(0)
        dev_combo.connect("changed", self.on_dev_combo_changed)
        video_device = VideoDevice()

        for dev in video_device.devices_list:
            dev_combo.append_text(dev)

        dev_combo.set_active(0)
        box.pack_start(dev_combo, False, False, 20)

        button = Gtk.Button.new_with_label("Run")
        button.connect("clicked", self.on_run_clicked)
        box.pack_start(button, False, False, 30)

        self.add(box)

    def on_dev_combo_changed(self, combo):
        """Device selected by the user."""
        self.device = combo.get_active_text()

    def on_run_clicked(self, button):
        """Run the pipeline."""
        self.func(self.device)


class VideoDevice:
    """Available video devices."""

    def __init__(self):
        self.devices_list = []
        self.get_devices()

        if not self.devices_list:
            message_window("No video capture device was found.")
            sys.exit("No video capture device was found.")

    def get_devices(self):
        """Get the list of all available video devices."""
        Gst.init()
        dev_monitor = Gst.DeviceMonitor()
        dev_monitor.add_filter("Video/Source")
        dev_monitor.start()

        for dev in dev_monitor.get_devices():
            props = dev.get_properties()
            device = props.get_string("device.path")
            caps = self.get_device_caps(dev.get_caps().normalize())

            if "0/0" not in caps:
                self.devices_list.append(device)

        dev_monitor.stop()

    def get_device_caps(self, dev_caps):
        """Get the caps of all available video device."""
        caps_list = []

        for i in range(dev_caps.get_size()):
            caps_struct = dev_caps.get_structure(i)
            if caps_struct.get_name() != "video/x-raw":
                continue

            framerate = "{}/{}".format(*caps_struct.get_fraction("framerate")[1:])
            caps_list.append(framerate)

        return caps_list


def open_camera(dev):
    """Launch CAM_PIPELINE gstreamer pipeline."""
    Popen(CAM_PIPELINE.format(dev), shell=True, executable="/bin/bash").wait()


def vpu_enc_dec(dev):
    """Launch ENC_PIPELINE gstreamer pipeline."""
    Popen(ENC_PIPELINE.format(dev), shell=True, executable="/bin/bash").wait()


def multi_cam():
    """Launch MULTI_CAM_PIPELINE gstreamer pipeline."""
    video_dev = VideoDevice()

    if len(video_dev.devices_list) < 2:
        message_window("You need a Basler Camera and an OV5640 to run this demo.")
    else:
        Popen(
            MULTI_CAM_PIPELINE.format(
                video_dev.devices_list[1], video_dev.devices_list[0]
            ),
            shell=True,
            executable="/bin/bash",
        ).wait()


def message_window(message):
    """Create and launch a window to display a message."""
    window = MessageWindow(message)
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()


def select_cam(func):
    """Create and launch the main UI window."""
    window = SelectCamWindow(func)
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("--open_camera", type=bool, default=False)
    parser.add_argument("--vpu_enc", type=bool, default=False)
    parser.add_argument("--multi_cam", type=bool, default=False)
    args = parser.parse_args()

    if args.open_camera:
        select_cam(open_camera)
    elif args.vpu_enc:
        select_cam(vpu_enc_dec)
    elif args.multi_cam:
        multi_cam()
