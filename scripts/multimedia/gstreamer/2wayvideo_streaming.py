#!/usr/bin/env python3

"""

Copyright 2023 NXP

SPDX-License-Identifier: BSD-3-Clause

This application showcases a two way video streaming demo which displays video
encode and decode capabilities between i.MX8M devices in a local network.
"""

import subprocess
import logging
import os
import time
import socket
import sys
import json
import gi
from threading import Thread

gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gtk, Gst, Gio, GLib, Gdk

sys.path.append("/home/root/.nxp-demo-experience/scripts/")
import utils


class InstallationWindow(Gtk.Window):
    """
    Display installation progress
    """

    def __init__(self):
        super().__init__(title="2Way Video Streaming")
        self.set_border_width(10)
        self.connect("destroy", Gtk.main_quit)

        self.label = Gtk.Label(label="Installing packages!")
        self.progressbar = Gtk.ProgressBar()
        self.timeout_id = GLib.timeout_add(50, self.on_timeout, None)
        self.activity_mode = 0

        self.grid = Gtk.Grid(
            row_homogeneous=True,
            column_homogeneous=True,
        )
        self.grid.attach(self.progressbar, 0, 0, 2, 1)
        self.grid.attach(self.label, 0, 5, 2, 2)

        self.add(self.grid)
        self.show_all()

    def on_timeout(self, user_data):
        """
        Update value on the progress bar
        """
        if self.activity_mode == 1:
            self.progressbar.pulse()
        elif self.activity_mode == 0:
            new_value = self.progressbar.get_fraction() + 0.01
            if new_value > 1:
                new_value = 0
            self.progressbar.set_fraction(new_value)
        return True


class DialogWindow(Gtk.Window):
    """
    Display error message for user
    """

    def __init__(self):
        super().__init__()
        self.dialog()

    def dialog(self):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Installation Error Message",
        )
        dialog.format_secondary_text(" Package Installation failed!")
        dialog.run()
        dialog.destroy()
        sys.exit(1)


def installation():
    #  display and install
    global wl
    wl = InstallationWindow()
    wl.connect("destroy", Gtk.main_quit)
    wl.show_all()
    Gtk.main()


ssdpy_exists = 1

try:
    from ssdpy import SSDPServer
    from ssdpy import SSDPClient
except ModuleNotFoundError:
    ssdpy_exists = 0

if ssdpy_exists == 0:
    thread = Thread(
        target=installation,
    )
    thread.start()
    try:
        subprocess.run(
            [sys.executable, "-m", "pip3", "install", "ssdpy"], check=True, timeout=30
        )
        from ssdpy import SSDPServer
        from ssdpy import SSDPClient

        GLib.idle_add(wl.destroy)
        ssdpy_exists = 1
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        # if no network, exit with message
        GLib.idle_add(wl.destroy)
        w = DialogWindow()
        w.connect("destroy", Gtk.main_quit)
        w.show_all()
        Gtk.main()

participantAddr = []
"""
The Search Target, used to narrow down the responses that should be received.
Defaults to "ssdp:all" which should get responses from any SSDP-enabled device.
"""
SSDP_ST = "ssdp:all"
camera = []
discoveredDevices = []
ssdpStatus = "Searching"
START = True
file_location = "/home/root/.cache/gopoint/device_info.json"
participants = []


def get_resolution():
    """
    Returns width and height of the display connected
    """
    screen = Gdk.Display.get_default()
    width = 0
    height = 0
    for x in range(0, screen.get_n_monitors()):
        width += screen.get_monitor(x).get_geometry().width
        if height < screen.get_monitor(x).get_geometry().height:
            height = screen.get_monitor(x).get_geometry().height
    return width, height


def getSOCID():
    """
    Returns SOC ID
    """
    with open("/sys/devices/soc0/soc_id", "r") as f:
        soc_id = f.read().replace("\n", "")
        f.close()
    return soc_id


def getMyIp():
    """
    Return its own IP address
    """
    sock_obj = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_obj.connect(("8.8.8.8", 80))
    self_ip = sock_obj.getsockname()[0]
    loopback = socket.gethostbyname(socket.gethostname())
    if self_ip == loopback:
        raise Exception("ERROR: Trying to figure out my IP address")
    else:
        # Shutting down socket, cleaning up resources
        sock_obj.close()
        return self_ip


def sendOutSSDPNotification(myIP, SOC_ID):
    """
    This is SSDP server response to relevant M-search packet on local network
    """
    server = SSDPServer(USN, device_type=SOC_ID, location=myIP)
    server.serve_forever()


def check_file():
    """
    This function checks if user name exists in file path, else returns false
    """
    try:
        if os.path.getsize(file_location) > 0:
            # file exists
            global USN
            with open(file_location, "r") as f:
                j_object = json.load(f)
                temp = j_object["name"]
                f.close()
            if not temp:
                # empty file
                return False
            USN = temp
            return True
    except OSError as e:
        # file does not exists
        return False


def ssdpSearch(myIP, SOC_ID):
    """
    It will send out M-Search packet on network relaying its presence
    to any server who is listening
    """

    def runSearch(devices):
        """
        Filter for i.MX devices
        """
        for device in devices:
            try:
                if (
                    device.get("nt").startswith(SOC_ID[:3]) is True
                    and device.get("location") != myIP
                    and device.get("location") not in participantAddr
                ):
                    participantAddr.append(device.get("location"))
                    discoveredDevices.append(device)
                    d = {}
                    d["NAME"] = device.get("usn")
                    d["IP"] = device.get("location")
                    d["SOC_ID"] = device.get("nt")
                    participants.append(d)
            except AttributeError:
                continue

    while True:
        global ssdpStatus
        global START
        if ssdpStatus == "Searching" and START:
            client = SSDPClient()
            t_end = time.time() + 10
            while not participantAddr and time.time() < t_end:
                devices = client.m_search(st=SSDP_ST, mx=5)
                runSearch(devices)
            ssdpStatus = "StandBy"
            START = False
            GLib.idle_add(w2.initiate_client_window)
            GLib.idle_add(w2.destroy)

        elif ssdpStatus == "Searching" and not START:
            GLib.idle_add(win.button1.set_label, "Searching...")
            GLib.idle_add(win.button1.set_sensitive, False)
            old_count = len(participantAddr)
            client = SSDPClient()
            t_end = time.time() + 5
            while time.time() < t_end:
                devices = client.m_search(st=SSDP_ST, mx=5)
                runSearch(devices)
            for i, j in enumerate(participants):
                if i < old_count:
                    continue
                else:
                    GLib.idle_add(win.device_select.append_text, (j.get("NAME")))
                    GLib.idle_add(win.button1.set_label, "Found Device")
                    time.sleep(1)
            ssdpStatus = "StandBy"
            GLib.idle_add(win.button1.set_label, "Search Again")
            GLib.idle_add(win.button1.set_sensitive, True)


def initiateSSDP():
    """
    Initiate SSDP advertisement and
    M-Search for local devices
    """
    global myIP
    myIP = getMyIp()
    global SOC_ID
    SOC_ID = getSOCID()
    cast_thread = Thread(
        target=sendOutSSDPNotification,
        args=[myIP, SOC_ID],
    )
    cast_thread.daemon = True
    cast_thread.start()
    search_thread = Thread(
        target=ssdpSearch,
        args=[myIP, SOC_ID],
    )
    search_thread.daemon = True
    search_thread.start()
    global w2
    w2 = SearchWindow()
    w2.connect("destroy", Gtk.main_quit)
    w2.show_all()
    Gtk.main()


class MessageDialogWindow(Gtk.Window):
    """
    Display error message for user
    """

    def __init__(self):
        super().__init__()
        self.dialog()

    def dialog(self):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Setup Error Message",
        )
        dialog.format_secondary_text(
            "Please connect a valid Camera device for this demo"
        )
        dialog.run()
        dialog.destroy()
        sys.exit(1)


class InitialWindow(Gtk.Window):
    """Initial Window"""

    def __init__(self):
        super().__init__()
        self.set_default_size(100, 150)
        self.set_resizable(False)
        self.set_border_width(10)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.grid = Gtk.Grid(row_spacing=60, column_spacing=30)
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(False)
        self.header.props.title = "2Way Video Streaming"
        self.set_titlebar(self.header)
        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        self.header.pack_end(quit_button)
        quit_button.connect("clicked", Gtk.main_quit)

        self.label1 = Gtk.Label(label="Device Name: ")
        self.entry1 = Gtk.Entry.new()
        self.entry1.set_placeholder_text("Type here...")
        self.entry1.set_activates_default(True)

        self.button1 = Gtk.Button(label="Ok")
        self.button1.connect("clicked", self.next_window)
        self.button2 = Gtk.Button(label="Cancel")
        self.button2.connect("clicked", self.next_window)

        self.grid.attach(self.label1, 0, 0, 2, 1)
        self.grid.attach(self.entry1, 2, 0, 2, 1)
        self.grid.attach(self.button1, 2, 4, 1, 1)
        self.grid.attach(self.button2, 3, 4, 1, 1)
        self.add(self.grid)

    def next_window(self, widget):
        if (widget.get_label()) == "Ok":
            self.name = self.entry1.get_text()
            if self.name:
                global USN
                USN = self.name
                with open(file_location, "w") as f:
                    dict = {"name": self.name}
                    j_object = json.dumps(dict, indent=2)
                    f.write(j_object)
                    f.close()
        w1.hide()
        initiateSSDP()


class ClientWindow(Gtk.Window):
    """Client Window"""

    def __init__(self):
        super().__init__()
        self.set_default_size(300, 150)
        self.set_resizable(False)
        self.set_border_width(10)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.grid = Gtk.Grid(
            row_homogeneous=True,
            column_homogeneous=True,
            row_spacing=15,
            column_spacing=30,
        )
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(False)
        self.header.props.title = "2Way Video Streaming"
        self.set_titlebar(self.header)
        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        self.header.pack_end(quit_button)
        quit_button.connect("clicked", Gtk.main_quit)

        self.label1 = Gtk.Label()
        self.label1.set_markup("Devices Found: ")
        self.button1 = Gtk.Button(label="Search Again")
        self.button1.connect("clicked", self.status_update)
        self.button1.set_focus_on_click(True)
        self.label3 = Gtk.Label(label="Camera Source: ")
        self.source_select = Gtk.ComboBoxText()
        for cam in camera:
            self.source_select.append_text(cam)
        self.source_select.set_active(0)
        self.device_select = Gtk.ComboBoxText()
        self.device_select.connect("changed", self.on_changed)
        for index in participants:
            self.device_select.append_text(index.get("NAME"))
        self.button2 = Gtk.Button(label="Start")
        self.button2.connect("clicked", self.join)
        self.button2.set_sensitive(False)

        self.grid.attach(self.label1, 0, 0, 1, 1)
        self.grid.attach(self.device_select, 1, 0, 1, 1)
        self.grid.attach(self.label3, 0, 2, 1, 1)
        self.grid.attach(self.source_select, 1, 2, 1, 1)
        self.grid.attach(self.button1, 0, 4, 1, 1)
        self.grid.attach(self.button2, 1, 4, 1, 1)
        self.add(self.grid)

    def on_changed(self, widget):
        self.button2.set_sensitive(True)

    def status_update(self, widget):
        global ssdpStatus
        ssdpStatus = "Searching"

    def join(self, select):
        thread = Thread(
            target=self.start_pipeline,
            args=[self],
        )
        thread.daemon = True
        thread.start()

    def start_pipeline(self, widget):
        """Join a call"""
        # Pipeline to start server
        self.dev = self.device_select.get_active_text()
        self.src = self.source_select.get_active_text()
        for index in participants:
            if self.dev == index.get("NAME"):
                self.device_ip = index.get("IP")
            else:
                continue

        # initializes state in background
        Gst.init(None)
        width, height = get_resolution()

        # Handling error, set default display size for 1080p
        if width == 0:
            width = 1920
        if height == 0:
            height = 1080

        # mainloop allows to parse events and run operations in background
        self.main_loop = GLib.MainLoop()

        video_pipeline = (
            "imxcompositor_g2d name=c latency=30000000 min-upstream-latency=30000000 "
        )
        video_pipeline += "sink_1::width={wd} sink_1::height={ht} sink_1::zorder=0 "
        video_pipeline += "sink_0::width={wdd} sink_0::height={htt} sink_0::zorder=1 ! "
        video_pipeline += "waylandsink sync=false "
        video_pipeline += "udpsrc ! application/x-rtp,media=video,clock-rate=90000,"
        video_pipeline += "encoding-name=H264 ! rtpjitterbuffer latency=100 ! queue max-size-buffers=0 ! rtph264depay ! "
        video_pipeline += (
            "h264parse ! queue ! v4l2h264dec ! queue ! imxvideoconvert_g2d ! c.sink_1 "
        )
        video_pipeline += "v4l2src device={sel} ! video/x-raw,width=1920,height=1080,framerate=30/1 ! "
        video_pipeline += (
            "tee allow-not-linked=true name=a a. ! imxvideoconvert_g2d ! c.sink_0 "
        )
        video_pipeline += "a. ! v4l2h264enc ! queue ! rtph264pay ! "
        video_pipeline += "udpsink host={ip} port=5004 sync=false async=false"

        video_pipeline = video_pipeline.format(
            ip=self.device_ip,
            sel=self.src,
            wd=int(width),
            ht=int(height),
            wdd=int(width / 3),
            htt=int(height / 3),
        )
        # creating the pipeline and launching it
        self.pipeline = Gst.parse_launch(video_pipeline)
        # by default pipelines are in NULL state, pipeline suppose to be set in running state
        monitor_status = self.pipeline.set_state(Gst.State.PLAYING)
        # message callback
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)
        if monitor_status == Gst.StateChangeReturn.FAILURE:
            print("ERROR: Unable to set the pipeline to the playing state")
            sys.exit(1)
        try:
            self.main_loop.run()
        except:
            pass

        # disconnecting the pipeline
        self.pipeline.set_state(Gst.State.NULL)
        bus.remove_signal_watch()

    def on_message(self, bus, message):
        """
        Callback for message.
        bus: pipeline bus
        message: message from pipeline
        """
        mtype = message.type
        if mtype == Gst.MessageType.EOS:
            # Handle End of Stream
            print("End of stream")
            self.main_loop.quit()
        elif mtype == Gst.MessageType.ERROR:
            # Handle Errors
            err, debug = message.parse_error()
            print(err, debug)
            self.main_loop.quit()
        elif mtype == Gst.MessageType.WARNING:
            # Handle warnings
            err, debug = message.parse_warning()
            print(err, debug)
        elif mtype == Gst.MessageType.STREAM_START:
            logging.info("received start message")
        elif mtype == Gst.MessageType.QOS:
            data_format, processed, dropped = message.parse_qos_stats()
            format_str = Gst.Format.get_name(data_format)
            logging.debug(
                "[qos] format[%s] processed[%d] dropped[%d]",
                format_str,
                processed,
                dropped,
            )


class SearchWindow(Gtk.Window):
    """Main Window"""

    def __init__(self):
        super().__init__()

        self.set_default_size(230, 180)
        self.set_resizable(False)
        self.set_border_width(20)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.grid_display = Gtk.Grid(
            row_homogeneous=True,
            column_homogeneous=True,
            row_spacing=10,
            column_spacing=10,
        )
        self.grid_display.set_margin_end(10)
        self.grid_display.set_margin_start(10)
        header = Gtk.HeaderBar()
        header.set_show_close_button(False)
        header.set_title("2Way Video Streaming")
        self.set_titlebar(header)
        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        header.pack_end(quit_button)
        quit_button.connect("clicked", Gtk.main_quit)
        self.label1 = Gtk.Label(label="IP: ")
        self.label2 = Gtk.Label()
        global myIP
        self.ip_address = myIP
        self.label2.set_text(self.ip_address)
        self.label3 = Gtk.Label(label="Searching for devices in network...")
        self.progressbar = Gtk.ProgressBar()
        self.timeout_id = GLib.timeout_add(25, self.on_timeout, None)
        self.activity_mode = False

        self.grid_display.attach(self.label1, 0, 0, 1, 1)
        self.grid_display.attach(self.label2, 1, 0, 1, 1)
        self.grid_display.attach(self.label3, 0, 2, 2, 1)
        self.grid_display.attach(self.progressbar, 0, 1, 2, 1)
        self.add(self.grid_display)

    def on_timeout(self, user_data):
        # Update value on the progress bar
        if self.activity_mode:
            self.progressbar.pulse()
        else:
            new_value = self.progressbar.get_fraction() + 0.01
            if new_value > 1:
                new_value = 0
            self.progressbar.set_fraction(new_value)
        return True

    def initiate_client_window(self):
        global win
        win = ClientWindow()
        win.connect("destroy", Gtk.main_quit)
        win.show_all()
        Gtk.main()


if __name__ == "__main__":
    # Prerequisite, host setup checks
    if ssdpy_exists == 1:
        global USN
        USN = getSOCID()
        camera = utils.run_check()
        if not camera:
            # if no camera, exit with message
            w = MessageDialogWindow()
            w.connect("destroy", Gtk.main_quit)
            w.show_all()
            Gtk.main()
        else:
            if not check_file():
                # if no file name, create one
                global w1
                w1 = InitialWindow()
                w1.connect("destroy", Gtk.main_quit)
                w1.show_all()
                Gtk.main()
            elif START:
                # Run SSDP commands if all checks passed
                initiateSSDP()
