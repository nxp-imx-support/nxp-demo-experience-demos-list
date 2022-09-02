#!/usr/bin/env python3

"""
Copyright 2022 NXP

SPDX-License-Identifier: Apache-2.0

This application allows a ML-resource-constraint MCU/MPU systems (clients)
to connect and run inferencing on a ML Gateway system (server) that has very
high-performance ML capabilities.
"""

from threading import Thread
import logging
import os
import socket
import sys
import tflite_runtime.interpreter as tflite
import numpy as np
import gi
import subprocess
from gi.repository import Gtk, Gst, GObject, Gio, GLib
sys.path.append("/home/root/.nxp-demo-experience/scripts/")
import utils
import glob

gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')


def initialize():
    """Initial package installation"""
    dwnwin = DownloadGUI()
    GLib.idle_add(dwnwin.show_all)
    """
    GLib.idle_add(dwnwin.status_label.set_text, "\n\nTesting internet...")
    res = subprocess.getstatusoutput(
                "ping -c 1 8.8.8.8"
            )[0]
    if res != 0:
        GLib.idle_add(
            dwnwin.status_label.set_text, "\n\nInternet connection required!")
        return
    """
    if FIRST_RUN:
        GLib.idle_add(
            dwnwin.status_label.set_text, "\n\nInstalling packages...")
        res = subprocess.getstatusoutput(
                "pip3 --retries 0 install ssdpy"
            )[0]
        if res != 0:
            GLib.idle_add(
                dwnwin.status_label.set_text, "\n\nPackage install failed!")
            return
    win.connect("destroy", Gtk.main_quit)
    GLib.idle_add(win.show_all)
    GLib.idle_add(dwnwin.destroy)
        

FIRST_RUN = False
BOARD = None
try:
    from ssdpy import SSDPServer
except ModuleNotFoundError:
    FIRST_RUN = True

MAX_TRY = 4
SSDP_ADDRESS = "239.255.255.250"
SSDP_PORT = 1900
SSDP_MX = 2
SSDP_ST = "imx-ml-server"
MODEL = "mobilenet_ssd_v2_coco_quant_postprocess.tflite"
DATA_SET = "coco_labels_nonum.txt"
ML_MODEL = utils.download_file(MODEL)


def access_ip():
    """ Returns IP address if found in network.
        SSDP is used to discover devices in local network
        using multicast SSDP address. SSDP uses NOTIFY
        to announce establishment information and M-Search
        to discover devices in network.

        MX : Maximum wait time(in seconds)
        ST : Search Target
    """
    ssdp_request = "M-SEARCH * HTTP/1.1\r\n" + "HOST: {host}:{port}\r\n" \
        + "MAN: \"ssdp:discover\"\r\n" + \
        "MX: {mx}\r\n" + "ST: {st}\r\n" + "\r\n"
    ssdp_request = ssdp_request.format(host=SSDP_ADDRESS,
                                       port=SSDP_PORT, st=SSDP_ST, mx=SSDP_MX)
    # send an m-search request and collect responses
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(ssdp_request.encode("utf-8"), (SSDP_ADDRESS, SSDP_PORT))
    sock.settimeout(1)
    global ssdp_address
    try:
        ssdp_response, ssdp_address = sock.recvfrom(150)
    except socket.timeout as timeout_error:
        erro = timeout_error.args[0]
        # timeout exception is setup
        if erro == "timed out":
            print("Receiver timed out, retry later")
            return False
    else:
        # got a response
        return ssdp_address


def get_my_ip():
    """ Obtaining its own IP address """
    sock_obj = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_obj.connect(("8.8.8.8", 80))
    self_ip = sock_obj.getsockname()[0]
    loopback = socket.gethostbyname(socket.gethostname())
    if self_ip == loopback:
        print("ERROR: Connected to loopback device, try again")
        sys.exit(1)
    else:
        return self_ip


def cast_ip():
    """ Handle incoming m-search request and send a response """
    server = SSDPServer("imx-server", device_type=SSDP_ST)
    server.serve_forever()

class DownloadGUI(Gtk.Window):
    """The main voice GUI application."""

    def __init__(self):
        """Creates the loading window and then shows it"""
        super().__init__()

        self.set_default_size(450, 100)
        self.set_resizable(False)
        self.set_border_width(10)

        header = Gtk.HeaderBar()
        header.set_title("ML Gateway")
        header.set_subtitle("NNStreamer Demo")
        self.set_titlebar(header)

        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        header.pack_end(quit_button)
        quit_button.connect("clicked", Gtk.main_quit)

        self.main_grid = Gtk.Grid(
            row_homogeneous=False, column_homogeneous=True,
            column_spacing=15, row_spacing=15)
        self.main_grid.set_margin_end(10)
        self.main_grid.set_margin_start(10)
        self.status_label = Gtk.Label.new("\n\nSetting up...")
        self.main_grid.attach(self.status_label, 0, 0, 1, 1)
        self.add(self.main_grid)

class ServerWindow(Gtk.Window):
    """ Server Window """

    def __init__(self):
        super().__init__()
        self.set_default_size(300, 200)
        self.set_resizable(False)
        self.set_border_width(15)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True,
                             row_spacing=10, column_spacing=10)
        # obtain Server's IP address
        self.label1 = Gtk.Label()
        self.label1.set_markup(" Server's IP: ")
        self.label2 = Gtk.Label()
        self.ip_address = get_my_ip()
        self.label2.set_text(self.ip_address)
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(False)
        self.header.props.title = "ML Server Setup"
        self.set_titlebar(self.header)
        self.quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        self.quit_button.add(quit_image)
        self.header.pack_end(self.quit_button)
        self.quit_button.connect("clicked", Gtk.main_quit)

        cast_thread = Thread(target=cast_ip)
        cast_thread.daemon = True
        cast_thread.start()

        processors = ["NPU", "CPU"]
        self.processor_select = Gtk.ComboBoxText()
        self.processor_select.set_entry_text_column(0)
        self.processor_select.connect("changed", self.on_changed)
        for processor in processors:
            self.processor_select.append_text(processor)
        self.processor_select.set_active(0)

        self.label3 = Gtk.Label()
        self.label3.set_markup("Select NPU or CPU: ")
        self.button1 = Gtk.Button(label="Start Server")
        button1_label = self.button1.get_child()
        button1_label.set_markup("<b>Start Server</b>")
        self.button1.connect("clicked", self.start_server_thread)
        self.button1.set_focus_on_click(True)
        self.grid.attach(self.label1, 0, 0, 1, 1)
        self.grid.attach(self.label2, 1, 0, 1, 1)
        self.grid.attach(self.label3, 0, 2, 1, 1)
        self.grid.attach(self.processor_select, 1, 2, 1, 1)
        self.grid.attach(self.button1, 0, 6, 2, 1)
        self.add(self.grid)

        def check_file(folder_path):
            file = [f for f in os.listdir(folder_path) if f.endswith(".nb")]
            return True if len(file) else False

        if check_file("/home/root/.cache/demoexperience") is False:
            self.to_reduce_warmup()

    def to_reduce_warmup(self):
        """ To reduce NPU warmup time"""
        ext_delegate = tflite.load_delegate("/usr/lib/libvx_delegate.so")
        # Load the TFLite model and allocate tensors.
        interpreter = tflite.Interpreter(model_path=ML_MODEL, num_threads=4,
                                         experimental_delegates=[ext_delegate])
        interpreter.allocate_tensors()

        # Get input and output tensors.
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()

        # Test the model on random input data.
        input_shape = input_details[0]['shape']
        input_data = np.array(np.random.random_sample(
            input_shape), dtype=np.uint8)
        interpreter.set_tensor(input_details[0]['index'], input_data)
        interpreter.invoke()

        # The function get_tensor() returns a copy of the tensor data.
        # Use tensor() in order to get a pointer to the tensor.
        interpreter.get_tensor(output_details[0]['index'])

    def on_changed(self, widget):
        """Allows user to change processors"""
        pro = widget.get_active_text()
        if pro == "NPU":
            self.custom = "Delegate:External,ExtDelegateLib:libvx_delegate.so"
        elif pro == "CPU":
            self.custom = "NumThreads:4"

    def start_server_thread(self, widget):
        """ Server Thread """
        server_thread = Thread(
            target=ServerWindow.start_server, args=[server_window])
        server_thread.daemon = True
        server_thread.start()

    def start_server(self):
        """ Pipeline to start server """
        self.button1.set_sensitive(False)
        self.processor_select.set_sensitive(False)
        # initializes state in background
        Gst.init(None)
        # mainloop allows to parse events and run operations in background
        self.main_loop = GObject.MainLoop()
        server_pipeline = "tensor_query_serversrc host={ip} ! video/x-raw,format=RGB"
        server_pipeline += ",framerate=0/1 ! tensor_converter ! "
        server_pipeline += "tensor_filter framework=tensorflow-lite model={model} custom={custom} "
        server_pipeline += "! tensor_query_serversink host={ip}"
        server_pipeline = server_pipeline.format(ip=self.ip_address,
                                                 model=ML_MODEL, custom=self.custom)

        # creating the pipeline and launching it
        self.pipeline = Gst.parse_launch(server_pipeline)
        # message callback
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self.on_message)
        # by default pipelines are in NULL state, pipeline suppose to be set in running state
        monitor_status = self.pipeline.set_state(Gst.State.PLAYING)
        if monitor_status == Gst.StateChangeReturn.FAILURE:
            print("ERROR: Unable to set the pipeline to the playing state")
            sys.exit(1)
        self.button1.set_label(" Server is running ")
        button1_label = self.button1.get_child()
        button1_label.set_markup("<b> Server is running </b>")
        self.main_loop.run()
        # disconnecting the pipeline
        self.pipeline.set_state(Gst.State.NULL)
        bus.remove_signal_watch()

    def on_message(self, bus, message):
        """Callback for message.

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
            logging.debug("[qos] format[%s] processed[%d] dropped[%d]",
                          format_str, processed, dropped)


class ClientWindow(Gtk.Window):
    """ Client Window """

    def __init__(self):
        super().__init__()
        self.set_default_size(300, 150)
        self.set_resizable(False)
        self.set_border_width(10)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True,
                             row_spacing=15, column_spacing=30)
        self.label1 = Gtk.Label()
        self.label1.set_markup("Enter or Select Server IP: ")
        self.entry2 = Gtk.Entry.new()
        self.entry2.set_placeholder_text("Type here...")
        self.entry2.set_activates_default(False)
        self.entry2.set_sensitive(False)

        maximum_search = MAX_TRY
        addresses = []
        attempt = 0
        self.devices = []
        for device in glob.glob('/dev/video*'):
            self.devices.append(device)

        source_label = Gtk.Label(
            label="Source"
        )
        self.source_select = Gtk.ComboBoxText()
        for option in self.devices:
            self.source_select.append_text(option)
        self.source_select.set_active(0)

        while maximum_search != 0 and attempt <= 1:
            # write a loop to attempt x times
            if access_ip() is not False:
                if ssdp_address[0] not in addresses:
                    addresses.append(ssdp_address[0])
                maximum_search -= 1
            attempt = attempt + 1
        if len(addresses) !=  0:
            self.server_ip = addresses[0]
        else:
            self.server_ip = "Not found!"
        self.radio_ip = Gtk.RadioButton()
        self.radio_ip.set_label(self.server_ip)
        self.radio_ip.connect("toggled", self.ip_changed)

        self.radio_savedip = Gtk.RadioButton(group=self.radio_ip)
        self.enter_ip = "Type IP address :"
        self.radio_savedip.set_label(self.enter_ip)
        self.radio_savedip.connect("toggled", self.ip_changed)

        self.button3 = Gtk.Button()
        self.button3.set_label("Connect to Server")
        button3_label = self.button3.get_child()
        button3_label.set_markup("<b> Connect to Server </b>")
        self.button3.connect("clicked", self.connect_to_server_thread)
        if len(addresses) != 0:
            self.radio_ip.set_active(True)
        else:
            self.radio_savedip.set_active(True)
            self.radio_ip.set_sensitive(False)
        
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(False)
        self.header.props.title = "ML Client Setup"
        self.set_titlebar(self.header)
        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        self.header.pack_end(quit_button)
        quit_button.connect("clicked", Gtk.main_quit)

        self.grid.attach(source_label, 0, 0, 1, 1)
        self.grid.attach(self.source_select, 1, 0, 1, 1)
        self.grid.attach(self.label1, 0, 1, 1, 1)
        self.grid.attach(self.radio_ip, 0, 2, 1, 1)
        self.grid.attach(self.radio_savedip, 0, 3, 1, 1)
        self.grid.attach(self.entry2, 1, 3, 1, 1)
        self.grid.attach(self.button3, 0, 4, 2, 2)
        self.add(self.grid)

    def ip_changed(self, widget):
        """Check if the client wants to connect to different IP address"""
        if widget.get_active() is True:
            if widget.get_label() == self.enter_ip:
                self.entry2.set_activates_default(True)
                self.entry2.set_sensitive(True)
            else:
                self.entry2.set_activates_default(False)
                self.entry2.set_sensitive(False)

    def connect_to_server_thread(self, widget):
        """ Thread to connect to server"""

        client_thread = Thread(
            target=ClientWindow.connect_to_server, args=[client_window])
        client_thread.daemon = True
        client_thread.start()

    def connect_to_server(self):
        """ To start the connection to server"""
        self.button3.set_sensitive(False)
        # initialises state in background
        Gst.init(None)
        self.main_loop = GObject.MainLoop()
        ml_data_set = utils.download_file(DATA_SET)
        if self.entry2.get_activates_default() is True:
            self.server_ip = self.entry2.get_text()
        src = self.source_select.get_active_text()

        client_pipeline = "v4l2src device={dev} ! "
        client_pipeline += "video/x-raw,width=640,height=480,framerate=30/1 ! tee name=t t. ! "
        client_pipeline += "queue max-size-buffers=2 leaky=2 ! imxvideoconvert_g2d ! "
        client_pipeline += "video/x-raw,width=300,height=300,format=RGBA ! "
        client_pipeline += "videoconvert ! video/x-raw,format=RGB ! tensor_query_client "
        client_pipeline += "sink-host={ip} src-host={ip} ! tensor_decoder"
        client_pipeline += " mode=bounding_boxes option1=tf-ssd option2={label} "
        client_pipeline += "option3=0:1:2:3,50 option4=640:480 option5=300:300 !"
        client_pipeline += " mix. t. ! queue max-size-buffers=2 ! imxcompositor_g2d name=mix"
        client_pipeline += " sink_0::zorder=2 sink_1::zorder=1 ! waylandsink"
        client_pipeline = client_pipeline.format(
            dev=src, ip=self.server_ip, label=ml_data_set)
        # creating the pipeline and launching it
        self.pipeline = Gst.parse_launch(client_pipeline)
        monitor_status = self.pipeline.set_state(Gst.State.PLAYING)
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self.on_message)
        if monitor_status == Gst.StateChangeReturn.FAILURE:
            print("ERROR: Unable to set the pipeline to the playing state")
            sys.exit(1)
        self.button3.set_label("Connected to server")
        button3_label = self.button3.get_child()
        button3_label.set_markup("<b> Connected to server </b>")
        rtn = self.main_loop.run()

        # disconnecting the pipeline
        self.pipeline.set_state(Gst.State.NULL)
        bus.remove_signal_watch()

    def on_message(self, bus, message):
        """Callback for message.

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
            self.button3.set_label("GStreamer crashed!")
            button3_label = self.button3.get_child()
            button3_label.set_markup("<b> GStreamer crashed! </b>")
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
            logging.debug("[qos] format[%s] processed[%d] dropped[%d]",
                          format_str, processed, dropped)


class DisplayWindow(Gtk.Window):
    """ Main Window display"""

    def __init__(self):
        # Main window
        super().__init__()
        self.set_default_size(230, 180)
        self.set_resizable(False)
        self.set_border_width(20)
        self.set_position(Gtk.WindowPosition.CENTER)
        # Create widgets for server and client
        self.grid_display = Gtk.Grid(row_homogeneous=True, column_homogeneous=True,
                                     row_spacing=10, column_spacing=10)
        self.grid_display.set_margin_end(10)
        self.grid_display.set_margin_start(10)
        header = Gtk.HeaderBar()
        header.set_show_close_button(False)
        header.set_title("ML Server using NNStreamer")
        header.set_subtitle("ML Server on i.MX8M Plus")
        self.set_titlebar(header)
        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        header.pack_end(quit_button)
        quit_button.connect("clicked", Gtk.main_quit)
        self.server_button = Gtk.Button(label="Set up a server...")
        self.client_button = Gtk.Button(label="Set up a client...")
        self.server_button.connect("clicked", self.server_initiate)
        self.client_button.connect("clicked", self.client_initiate)
        global BOARD
        print(BOARD)
        if BOARD == "i.MX8MP":
            self.client_button.set_sensitive(False)
        else:
            self.server_button.set_sensitive(False)
        self.grid_display.attach(self.server_button, 0, 0, 1, 1)
        self.grid_display.attach(self.client_button, 0, 2, 1, 1)
        self.add(self.grid_display)

    def server_initiate(self, widget):
        """ Initiate the server """
        global server_window
        server_window = ServerWindow()
        server_window.connect("destroy", Gtk.main_quit)
        server_window.show_all()
        win.hide()

    def client_initiate(self, widget):
        """ Initiate the client"""
        capture_ip_thread = Thread(target=access_ip)
        capture_ip_thread.start()
        global client_window
        client_window = ClientWindow()
        client_window.connect("destroy", Gtk.main_quit)
        client_window.show_all()
        win.hide()


if __name__ == "__main__":
    os.environ["VIV_VX_CACHE_BINARY_GRAPH_DIR"] = ("/home/root/.cache"
            "/demoexperience")
    os.environ["VIV_VX_ENABLE_CACHE_GRAPH_BINARY"] = "1"
    BOARD = subprocess.check_output(
            ['cat', '/sys/devices/soc0/soc_id']
            ).decode('utf-8')[:-1]
    win = DisplayWindow()
    initialize_thread = Thread(target=initialize)
    initialize_thread.start()
    Gtk.main()
