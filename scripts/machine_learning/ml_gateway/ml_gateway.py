#!/usr/bin/env python3

"""
Copyright 2022-2024 NXP
SPDX-License-Identifier: Apache-2.0

This application allows ML-resource-constraint MPU systems (clients) to connect and run inferencing
on an ML Gateway system (server) that has very high-performance ML capabilities.
"""

from threading import Thread
import logging
import os
import socket
import time
import sys
import subprocess
import glob
import gi
import numpy as np
import tflite_runtime.interpreter as tflite

sys.path.append("/home/root/.nxp-demo-experience/scripts/")
import utils

gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gst, GLib


def threaded(fn):
    """
    Handle threads out of main GTK thread
    """

    def wrapper(*args, **kwargs):
        Thread(target=fn, args=args, kwargs=kwargs).start()

    return wrapper


def get_my_ip():
    """Obtaining its own IP address"""
    socket_object = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    socket_object.connect(("8.8.8.8", 80))
    ip_address = socket_object.getsockname()[0]
    loopback = socket.gethostbyname(socket.gethostname())
    if ip_address == loopback:
        print("ERROR: Connected to loopback device, try again")
        sys.exit(1)
    else:
        return ip_address


class ServerWindow:
    """Server Window"""

    def __init__(self):
        # Detect platform inside class
        self.platform = subprocess.check_output(
            ["cat", "/sys/devices/soc0/soc_id"]
        ).decode("utf-8")[:-1]

        # Obtain GUI settings and configurations
        glade_file = (
            "/home/root/.nxp-demo-experience/"
            "scripts/machine_learning/ml_gateway/ml_gateway.glade"
        )
        self.builder = Gtk.Builder()
        self.builder.add_from_file(glade_file)
        self.builder.connect_signals(self)

        # Get main application window
        window = self.builder.get_object("server-window")

        # Get about dialog windonw
        self.about_dialog = self.builder.get_object("about-dialog")

        # Get widgets
        self.ip_address_label = self.builder.get_object("ip-label")
        self.backend_select = self.builder.get_object("backend-box")
        self.status_bar = self.builder.get_object("status-bar-server")
        self.progress_bar = self.builder.get_object("progress-bar-server")
        self.run_server = self.builder.get_object("start-button")
        self.about_button = self.builder.get_object("about-button")
        self.close_button = self.builder.get_object("close-button")

        # Needed variables
        self.custom = None
        self.main_loop = None
        self.pipeline = None
        self.timeout_id = None
        self.pulsing = False

        # Model variables
        self.model = None
        self.cpu_model = None
        self.vela_model = None

        # obtain Server's IP address
        self.ip_address = get_my_ip()
        self.ip_address_label.set_text(self.ip_address)

        # Populate backends
        backends = ["NPU", "CPU"]
        for backend in backends:
            self.backend_select.append_text(backend)
        self.backend_select.set_active(0)

        Gst.init()
        self.main_loop = GLib.MainLoop()

        # Connect signals
        self.backend_select.connect("changed", self.on_changed)
        self.run_server.connect("clicked", self.start_server)
        self.close_button.connect("clicked", self.quit_app)
        window.connect("delete-event", Gtk.main_quit)
        window.show()

        # Preload default model
        preload_thread = Thread(target=self.preload, daemon=True)
        preload_thread.start()

        # Start IP cast
        cast_thread = Thread(target=self.cast_ip, daemon=True)
        cast_thread.start()

    def quit_app(self, widget):
        """Closes GStreamer pipeline and GTK+3 GUI"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)

        if self.main_loop:
            self.main_loop.quit()

        Gtk.main_quit()

    def preload(self):
        """Download the default model and set up server"""

        # Block run button and start progress bar
        self.run_server.set_sensitive(False)
        self.backend_select.set_sensitive(False)
        self.pulsing = True
        self.timeout_id = GLib.timeout_add(50, self.on_timeout)

        GLib.idle_add(self.status_bar.set_text, "Downloading model...")
        self.model = self.cpu_model = utils.download_file(
            "mobilenet_ssd_v2_coco_quant_postprocess.tflite"
        )

        # Verify if download is successfull
        if self.model == -1:
            GLib.idle_add(self.status_bar.set_text, "Cannot find files!")
            self.pulsing = False
            self.run_server.set_sensitive(True)
            self.backend_select.set_sensitive(True)
            return
        if self.model == -2:
            GLib.idle_add(self.status_bar.set_text, "Download failed!")
            self.pulsing = False
            self.run_server.set_sensitive(True)
            self.backend_select.set_sensitive(True)
            return
        if self.model == -3:
            GLib.idle_add(self.status_bar.set_text, "Corrupted file!")
            self.pulsing = False
            self.run_server.set_sensitive(True)
            self.backend_select.set_sensitive(True)
            return

        GLib.idle_add(self.status_bar.set_text, "Model successfully downloaded!")

        # Wait one second to show message to user
        time.sleep(1)

        # Compile model using vela tool for i.MX93
        if self.platform == "i.MX93":
            self.compile_vela()
        else:
            os.environ["VIV_VX_CACHE_BINARY_GRAPH_DIR"] = "/home/root/.cache/gopoint"
            os.environ["VIV_VX_ENABLE_CACHE_GRAPH_BINARY"] = "1"

            if not any(
                f.endswith(".nb") for f in os.listdir("/home/root/.cache/gopoint")
            ):
                GLib.idle_add(self.status_bar.set_text, "Warmup time...")
                self.to_reduce_warmup()

        backend = self.backend_select.get_active_text()
        if self.platform == "i.MX8MP":
            if backend == "NPU":
                self.custom = "Delegate:External,ExtDelegateLib:libvx_delegate.so"
            if backend == "CPU":
                self.custom = "NumThreads:4"
        if self.platform == "i.MX93":
            if backend == "NPU":
                self.custom = "Delegate:External,ExtDelegateLib:libethosu_delegate.so"
                self.model = self.vela_model
            if backend == "CPU":
                self.custom = "NumThreads:2"
                self.model = self.cpu_model

        GLib.idle_add(self.status_bar.set_text, "Model is ready for inference!")

        self.run_server.set_sensitive(True)
        self.backend_select.set_sensitive(True)
        self.pulsing = False

    def cast_ip(self):
        """Handle incoming m-search request and send a response"""

        try:
            from ssdpy import SSDPServer
        except ModuleNotFoundError:
            GLib.idle_add(self.status_bar.set_text, "Installing packages...")
            res = subprocess.run(
                ["pip3", "install", "--retries", "0", "ssdpy"],
                capture_output=True,
                check=False,
            )
            if res.returncode != 0:
                GLib.idle_add(self.status_bar.set_text, "Package install failed!")
                return
            from ssdpy import SSDPServer

        SSDPServer("imx-server", device_type="imx-ml-server").serve_forever()

    def to_reduce_warmup(self):
        """To reduce NPU warmup time on i.MX8M Plus"""
        # Load the TFLite model and allocate tensors.
        ext_delegate = tflite.load_delegate("/usr/lib/libvx_delegate.so")
        interpreter = tflite.Interpreter(
            model_path=self.model,
            num_threads=4,
            experimental_delegates=[ext_delegate],
        )
        interpreter.allocate_tensors()

        # Get input and output tensors.
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()

        # Test the model on random input data.
        input_shape = input_details[0]["shape"]
        input_data = np.array(np.random.random_sample(input_shape), dtype=np.uint8)
        interpreter.set_tensor(input_details[0]["index"], input_data)
        interpreter.invoke()

        # The function get_tensor() returns a copy of the tensor data.
        # Use tensor() in order to get a pointer to the tensor.
        interpreter.get_tensor(output_details[0]["index"])

    def on_timeout(self):
        """Function to handle progress bar"""
        if self.pulsing:
            self.progress_bar.set_show_text(True)
            self.progress_bar.pulse()
            return True
        self.progress_bar.set_show_text(False)
        self.progress_bar.set_fraction(0.0)
        return False

    def compile_vela(self):
        """Compile vela model"""
        self.vela_model = self.vela_name(self.model)
        if not os.path.exists(self.vela_model):
            GLib.idle_add(
                self.status_bar.set_text,
                "Compiling model with vela and saving to cache...",
            )

            subprocess.run(
                "vela " + self.model + " --output-dir=/home/root/.cache/gopoint/",
                shell=True,
                check=True,
            )

    def vela_name(self, model_name):
        """
        Appends the vela label to model name
        """
        tokens = model_name.split(".tflite")
        return (
            "/home/root/.cache/gopoint/" + (tokens[-2] + "_vela.tflite").split("/")[-1]
        )

    def about_button_activate(self, widget):
        """
        Function to handle about dialog window
        """
        self.about_dialog.run()
        time.sleep(100 / 1000)
        self.about_dialog.hide()
        return True

    def on_changed(self, widget):
        """Allows user to change backends"""
        backend = widget.get_active_text()
        if self.platform == "i.MX8MP":
            if backend == "NPU":
                self.custom = "Delegate:External,ExtDelegateLib:libvx_delegate.so"
            if backend == "CPU":
                self.custom = "NumThreads:4"
        if self.platform == "i.MX93":
            if backend == "NPU":
                self.custom = "Delegate:External,ExtDelegateLib:libethosu_delegate.so"
                self.model = self.vela_model
            if backend == "CPU":
                self.custom = "NumThreads:2"
                self.model = self.cpu_model

    @threaded
    def start_server(self, widget):
        """Pipeline to start server"""
        self.run_server.set_sensitive(False)
        self.backend_select.set_sensitive(False)
        self.close_button.set_sensitive(False)

        server_pipeline = (
            f"tensor_query_serversrc host={self.ip_address} ! "
            "video/x-raw,width=300,height=300,format=RGB"
        )
        server_pipeline += ",framerate=0/1 ! tensor_converter ! "
        server_pipeline += "tensor_filter framework=tensorflow-lite "
        server_pipeline += f"model={self.model} custom={self.custom} "
        server_pipeline += "! tensor_query_serversink"

        # creating the pipeline and launching it
        self.pipeline = Gst.parse_launch(server_pipeline)

        # message callback
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)

        # by default pipelines are in NULL state, pipeline suppose to be set in running state
        monitor_status = self.pipeline.set_state(Gst.State.PLAYING)
        if monitor_status == Gst.StateChangeReturn.FAILURE:
            print("ERROR: Unable to set the pipeline to the playing state")
            sys.exit(1)

        self.run_server.set_label("Server is running")
        self.main_loop.run()

        # disconnecting the pipeline
        self.pipeline.set_state(Gst.State.NULL)
        bus.remove_signal_watch()

    def on_message(self, bus, message):
        """Callback for message.

        bus: pipeline bus
        message: message from pipeline
        """
        if message.type == Gst.MessageType.EOS:
            logging.info("received eos message")
            self.main_loop.quit()
        elif message.type == Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            logging.warning("[error] %s : %s", error.message, debug)
            self.main_loop.quit()
        elif message.type == Gst.MessageType.WARNING:
            error, debug = message.parse_warning()
            logging.warning("[warning] %s : %s", error.message, debug)
        elif message.type == Gst.MessageType.STREAM_START:
            logging.info("received start message")
        elif message.type == Gst.MessageType.QOS:
            data_format, processed, dropped = message.parse_qos_stats()
            format_str = Gst.Format.get_name(data_format)
            logging.debug(
                "[qos] format[%s] processed[%d] dropped[%d]",
                format_str,
                processed,
                dropped,
            )


class ClientWindow:
    """Client Window"""

    def __init__(self):
        # Obtain GUI settings and configurations
        glade_file = (
            "/home/root/.nxp-demo-experience/"
            "scripts/machine_learning/ml_gateway/ml_gateway.glade"
        )
        self.builder = Gtk.Builder()
        self.builder.add_from_file(glade_file)
        self.builder.connect_signals(self)

        # Get main application window
        window = self.builder.get_object("client-window")

        # Get about dialog windonw
        self.about_dialog = self.builder.get_object("about-dialog")

        # Get widgets
        self.source_select = self.builder.get_object("source-box")
        self.found_ip_address = self.builder.get_object("ip-obtained-button")
        self.type_address_button = self.builder.get_object("type-button")
        self.entry_text_box = self.builder.get_object("entry-text-box")
        self.connect_server = self.builder.get_object("client-button")
        self.progress_bar = self.builder.get_object("progress-bar-client")
        self.status_bar = self.builder.get_object("status-bar-client")
        self.about_button = self.builder.get_object("about-button-client")
        close_button = self.builder.get_object("close-button-client")

        # Needed variables
        self.main_loop = None
        self.pipeline = None
        self.server_ip = None
        self.labels = None
        self.timeout_id = None
        self.pulsing = False

        # Populate source devices
        for device in glob.glob("/dev/video*"):
            self.source_select.append_text(device)
        self.source_select.set_active(0)

        Gst.init()
        self.main_loop = GLib.MainLoop()

        # Connect signals
        self.found_ip_address.connect("toggled", self.ip_changed)
        self.type_address_button.connect("toggled", self.ip_changed)
        self.connect_server.connect("clicked", self.connect_to_server)
        close_button.connect("clicked", self.quit_app)
        window.connect("delete-event", Gtk.main_quit)
        window.show()

        # Get ip address
        capture_ip_thread = Thread(target=self.access_ip, daemon=True)
        capture_ip_thread.start()

        # Set up client
        preload_thread = Thread(target=self.preload, daemon=True)
        preload_thread.start()

    def quit_app(self, widget):
        """Closes GStreamer pipeline and GTK+3 GUI"""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)

        self.main_loop.quit()
        Gtk.main_quit()

    def preload(self):
        """Setup client"""

        # Block run button and start progress bar
        self.unblock_buttons(False)

        self.pulsing = True
        self.timeout_id = GLib.timeout_add(50, self.on_timeout)

        GLib.idle_add(self.status_bar.set_text, "Downloading labels...")
        self.labels = utils.download_file("coco_labels.txt")

        # Verify if download is successfull
        if self.labels == -1:
            GLib.idle_add(self.status_bar.set_text, "Cannot find files!")
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.labels == -2:
            GLib.idle_add(self.status_bar.set_text, "Download failed!")
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.labels == -3:
            GLib.idle_add(self.status_bar.set_text, "Corrupted file!")
            self.pulsing = False
            self.unblock_buttons(True)
            return

        GLib.idle_add(self.status_bar.set_text, "Labels successfully downloaded!")

        # Wait one second to show message to user
        time.sleep(1)

        GLib.idle_add(self.status_bar.set_text, "Looking for server IPs...")

        maximum_search = 4
        addresses = []
        attempt = 0
        while maximum_search != 0 and attempt <= 1:
            # write a loop to attempt x times
            client_ssdp_address = self.access_ip()
            if client_ssdp_address is not False:
                if client_ssdp_address[0] not in addresses:
                    addresses.append(client_ssdp_address[0])
                maximum_search -= 1
            attempt = attempt + 1
        if len(addresses) != 0:
            self.server_ip = addresses[0]
            self.found_ip_address.set_active(True)
            self.entry_text_box.set_activates_default(False)
            self.entry_text_box.set_sensitive(False)
        else:
            self.type_address_button.set_active(True)
            self.found_ip_address.set_sensitive(False)
            self.server_ip = "Not found!"
        self.found_ip_address.set_label(self.server_ip)

        GLib.idle_add(self.status_bar.set_text, "Client ready for connection!")

        self.unblock_buttons(True)
        self.pulsing = False

    def unblock_buttons(self, status):
        """Block/unblock buttons"""
        self.connect_server.set_sensitive(status)
        self.source_select.set_sensitive(status)
        self.type_address_button.set_sensitive(status)

    def on_timeout(self):
        """Function to handle progress bar"""
        if self.pulsing:
            self.progress_bar.set_show_text(True)
            self.progress_bar.pulse()
            return True
        self.progress_bar.set_show_text(False)
        self.progress_bar.set_fraction(0.0)
        return False

    def access_ip(self):
        """Returns IP address if found in network.
        SSDP is used to discover devices in local network
        using multicast SSDP address. SSDP uses NOTIFY
        to announce establishment information and M-Search
        to discover devices in network.

        MX : Maximum wait time(in seconds)
        ST : Search Target
        """

        ssdp_address = "239.255.255.250"
        ssdp_port = 1900
        ssdp_mx = 2
        ssdp_st = "imx-ml-server"

        ssdp_request = (
            "M-SEARCH * HTTP/1.1\r\n"
            + f"HOST: {ssdp_address}:{ssdp_port}\r\n"
            + 'MAN: "ssdp:discover"\r\n'
            + f"MX: {ssdp_mx}\r\n"
            + f"ST: {ssdp_st}\r\n"
            + "\r\n"
        )

        # send an m-search request and collect responses
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(ssdp_request.encode("utf-8"), (ssdp_address, ssdp_port))
        sock.settimeout(1)

        try:
            _, ssdp_address = sock.recvfrom(150)
        except socket.timeout as timeout_error:
            erro = timeout_error.args[0]
            # timeout exception is setup
            if erro == "timed out":
                print("Receiver timed out, retry later")
                return False
        else:
            # got a response
            return ssdp_address
        return False

    def about_button_activate(self, widget):
        """
        Function to handle about dialog window
        """
        self.about_dialog.run()
        time.sleep(100 / 1000)
        self.about_dialog.hide()
        return True

    def ip_changed(self, widget):
        """Check if the client wants to connect to different IP address"""
        if widget.get_active() is True:
            if widget.get_label() == "Type IP address:":
                self.entry_text_box.set_activates_default(True)
                self.entry_text_box.set_sensitive(True)
            else:
                self.entry_text_box.set_activates_default(False)
                self.entry_text_box.set_sensitive(False)

    @threaded
    def connect_to_server(self, widget):
        """To start the connection to server"""
        self.connect_server.set_sensitive(False)

        if self.entry_text_box.get_activates_default() is True:
            self.server_ip = self.entry_text_box.get_text()
        src = self.source_select.get_active_text()

        client_pipeline = (
            f"v4l2src device={src} ! video/x-raw,width=640,height=480,framerate=30/1 "
        )
        client_pipeline += "! tee name=t t. ! "
        client_pipeline += "queue max-size-buffers=2 leaky=2 ! imxvideoconvert_g2d ! "
        client_pipeline += "video/x-raw,width=300,height=300,format=RGBA ! "
        client_pipeline += (
            "videoconvert ! video/x-raw,format=RGB ! tensor_query_client "
        )
        client_pipeline += (
            f"host={get_my_ip()} dest-host={self.server_ip} ! tensor_decoder"
        )
        client_pipeline += f" mode=bounding_boxes option1=tf-ssd option2={self.labels} "
        client_pipeline += "option3=0:1:2:3,50 option4=640:480 option5=300:300 !"
        client_pipeline += " mix. t. ! queue max-size-buffers=2 !"
        client_pipeline += (
            " imxcompositor_g2d name=mix latency=33333333 min-upstream-latency=33333333"
        )
        client_pipeline += " sink_0::zorder=2 sink_1::zorder=1 ! "
        client_pipeline += "fpsdisplaysink video-sink=waylandsink sync=false"

        # creating the pipeline and launching it
        self.pipeline = Gst.parse_launch(client_pipeline)
        monitor_status = self.pipeline.set_state(Gst.State.PLAYING)

        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_message)
        if monitor_status == Gst.StateChangeReturn.FAILURE:
            print("ERROR: Unable to set the pipeline to the playing state")
            sys.exit(1)

        self.connect_server.set_label("Connected to server")
        self.main_loop.run()

        # disconnecting the pipeline
        self.pipeline.set_state(Gst.State.NULL)
        bus.remove_signal_watch()

    def on_message(self, bus, message):
        """Callback for message.

        bus: pipeline bus
        message: message from pipeline
        """
        if message.type == Gst.MessageType.EOS:
            logging.info("received eos message")
            self.main_loop.quit()
        elif message.type == Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            logging.warning("[error] %s : %s", error.message, debug)
            GLib.idle_add(self.status_bar.set_text, "Internal data stream error!")
            self.unblock_buttons(True)
            self.connect_server.set_label("Retry connecting to server!")
            self.main_loop.quit()
        elif message.type == Gst.MessageType.WARNING:
            error, debug = message.parse_warning()
            logging.warning("[warning] %s : %s", error.message, debug)
        elif message.type == Gst.MessageType.STREAM_START:
            logging.info("received start message")
        elif message.type == Gst.MessageType.QOS:
            data_format, processed, dropped = message.parse_qos_stats()
            format_str = Gst.Format.get_name(data_format)
            logging.debug(
                "[qos] format[%s] processed[%d] dropped[%d]",
                format_str,
                processed,
                dropped,
            )


if __name__ == "__main__":
    PLATFORM = subprocess.check_output(["cat", "/sys/devices/soc0/soc_id"]).decode(
        "utf-8"
    )[:-1]

    if PLATFORM in ("i.MX8MP", "i.MX93"):
        server_application = ServerWindow()
    else:
        client_application = ClientWindow()

    Gtk.main()
