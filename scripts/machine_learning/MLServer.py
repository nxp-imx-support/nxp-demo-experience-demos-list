#!/usr/bin/env python3

import gi
import threading
import socket
import subprocess
import os
import logging
import sys
import numpy as np
import tflite_runtime.interpreter as tflite
from threading import Thread
from ssdpy import SSDPClient
from ssdpy import SSDPServer

gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')
from gi.repository import Gtk, Gst, GObject, Gio, GLib

MAX_TRY = 4
SSDP_ADDRESS = "239.255.255.250"
SSDP_PORT = 1900
SSDP_MX = 2
SSDP_ST = "imx-ml-server"
MODEL = "ssd_mobilenet_v2_coco_quant_postprocess.tflite"
MODEL_LINK = "https://github.com/google-coral/test_data/raw/master/"
MODEL_PATH = os.getcwd() + "/" + MODEL
DATA_SET = "coco_labels.txt"
DATA_SET_LINK = "https://github.com/google-coral/test_data/raw/master/"
DATA_SET_PATH = os.getcwd() + "/" + DATA_SET

def access_ip():
    ssdp_request = "M-SEARCH * HTTP/1.1\r\n" + "HOST: {host}:{port}\r\n" \
        + "MAN: \"ssdp:discover\"\r\n" + "MX: {mx}\r\n" + "ST: {st}\r\n" + "\r\n"
    ssdp_request = ssdp_request.format(host=SSDP_ADDRESS, port=SSDP_PORT, st = SSDP_ST, mx = SSDP_MX)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(ssdp_request.encode("utf-8"), (SSDP_ADDRESS, SSDP_PORT))
    sock.settimeout(1)
    try:
        global address
        ssdp_responce, address = sock.recvfrom(1)
    except socket.timeout as er:
        erro = er.args[0]
        # timeout exception is setup
        if erro == "timed out": 
            print ("receiver timed out, retry later")
            return False
    else:
    # got a message
        return address

def get_ip():
    ss= socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ss.connect(("8.8.8.8", 80))
    self_ip = ss.getsockname()[0]
    ss.close()
    return self_ip

def cast_ip():
    server = SSDPServer("imx-server", device_type=SSDP_ST)
    server.serve_forever()

class ServerWindow(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_default_size(300,200)
        self.set_resizable(False)
        self.set_border_width(15)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True, row_spacing=10, column_spacing=10)
        # get IP address
        self.label1 = Gtk.Label()
        self.label1.set_markup(" SERVER's IP : ")
        self.label2 = Gtk.Label()
        self.ip_address = get_ip()
        self.label2.set_text(self.ip_address)
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(False)
        self.header.props.title = "ML SERVER - iMX8M Plus"
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
        self.processor_select.connect("changed",self.on_changed)
        for processor in processors:
            self.processor_select.append_text(processor)
        self.processor_select.set_active(0)

        self.label3 = Gtk.Label()
        self.label3.set_markup("SELECT NPU or CPU : ")
        self.button1 = Gtk.Button(label=" START SERVER ")
        button1_label = self.button1.get_child()
        button1_label.set_markup("<b> START SERVER </b>")
        self.button1.connect("clicked",self.start_server_thread)
        self.button1.set_focus_on_click(True)
        self.grid.attach(self.label1, 0, 0, 1, 1)
        self.grid.attach(self.label2, 1, 0, 1, 1)
        self.grid.attach(self.label3, 0, 2, 1, 1)
        self.grid.attach(self.processor_select, 1, 2, 1, 1)
        self.grid.attach(self.button1, 0, 6, 2, 1)
        self.add(self.grid)
        self.to_reduce_warmup()
        print(threading.active_count())
    
    def to_reduce_warmup(self):
        # NPU warmup time 
        ml_model = "wget " + MODEL_LINK + MODEL
        out = subprocess.run(ml_model, stdout=subprocess.PIPE, shell= True)
        ext_delegate = tflite.load_delegate("/usr/lib/libvx_delegate.so")
        # Load the TFLite model and allocate tensors.
        interpreter = tflite.Interpreter(model_path=MODEL_PATH, num_threads=4,experimental_delegates=[ext_delegate])
        interpreter.allocate_tensors()

        # Get input and output tensors.
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()

        # Test the model on random input data.
        input_shape = input_details[0]['shape']
        input_data = np.array(np.random.random_sample(input_shape), dtype=np.uint8)
        interpreter.set_tensor(input_details[0]['index'], input_data)

        interpreter.invoke()

        # The function `get_tensor()` returns a copy of the tensor data.
        # Use `tensor()` in order to get a pointer to the tensor.
        output_data = interpreter.get_tensor(output_details[0]['index'])

    def on_changed(self, widget):
        pro = widget.get_active_text()
        if pro == "NPU":
            self.custom = "Delegate:External,ExtDelegateLib:libvx_delegate.so"
        elif pro == "CPU":
            self.custom = "NumThreads:4"

    def start_server_thread(self,widget):
        server_thread = Thread(target=ServerWindow.start_server,args=[sWin])
        server_thread.daemon = True
        server_thread.start()

    # pipeline to start the server
    def start_server(self):
        self.button1.set_sensitive(False)
        self.processor_select.set_sensitive(False)
        # initializes state in background
        Gst.init(None)
        # mainloop allows to parse events and run operations in background
        self.main_loop = GObject.MainLoop()
                
        server_pipeline = "tensor_query_serversrc host={ip} ! video/x-raw,format=RGB,framerate=0/1 ! "
        server_pipeline += "tensor_converter ! tensor_filter framework=tensorflow-lite model={model} custom={custom} "
        server_pipeline += "! tensor_query_serversink host={ip}"
        server_pipeline = server_pipeline.format(ip=self.ip_address,model=MODEL_PATH,custom=self.custom)

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
        self.button1.set_label(" SERVER IS RUNNING ")
        button1_label = self.button1.get_child()
        button1_label.set_markup("<b> SERVER IS RUNNING </b>")
        self.main_loop.run()
        #disconnecting the pipeline
        self.pipeline.set_state(Gst.State.NULL)
        bus.remove_signal_watch()

    def on_message(self,bus, message):   
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
    def __init__(self):
        super().__init__()
        self.set_default_size(300,150)
        self.set_resizable(False)
        self.set_border_width(10)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.grid = Gtk.Grid(row_homogeneous=True, column_homogeneous=True, row_spacing=15, column_spacing=30)
        self.label1 = Gtk.Label()
        self.label1.set_markup(" ENTER or SELECT SERVER IP : ")
        self.entry2 = Gtk.Entry.new()
        self.entry2.set_placeholder_text("Type here...")
        self.entry2.set_activates_default(False)
        self.entry2.set_sensitive(False)

        max = MAX_TRY
        addresses = []

        while max != 0:
            if access_ip() == False:
                data = 0
            #     dialog = Gtk.MessageDialog(
            #     transient_for=self,
            #     flags=0,
            #     message_type=Gtk.MessageType.ERROR,
            #     buttons=Gtk.ButtonsType.CANCEL,
            #     text="Cannot find IP address! \n Please turn on the server",
            # )
            #     dialog.run()
            #     dialog.destroy()
            else:
                if address[0] not in addresses :
                    addresses.append(address[0])
                max-=1

        self.server_ip = addresses[0]
        self.radio_ip = Gtk.RadioButton()
        self.radio_ip.set_label(self.server_ip)
        self.radio_ip.connect("toggled", self.ip_changed)
        self.radio_ip.set_active(True)

        self.radio_savedip = Gtk.RadioButton(group=self.radio_ip)
        self.enter_ip = "Type IP address :"
        self.radio_savedip.set_label(self.enter_ip)
        self.radio_savedip.connect("toggled", self.ip_changed)

        self.button3 = Gtk.Button()
        self.button3.set_label("CONNECT TO SERVER")
        button3_label = self.button3.get_child()
        button3_label.set_markup("<b> CONNECT TO SERVER </b>")
        self.button3.connect("clicked", self.connect_to_server_thread)
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(False)
        self.header.props.title = "ML CLIENT"
        self.set_titlebar(self.header)
        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        self.header.pack_end(quit_button)
        quit_button.connect("clicked", Gtk.main_quit)

        self.grid.attach(self.label1, 0, 0, 1, 1)
        self.grid.attach(self.radio_ip, 0, 1, 1, 1)
        self.grid.attach(self.radio_savedip, 0, 2, 1, 1)
        self.grid.attach(self.entry2, 1, 2, 1, 1)
        self.grid.attach(self.button3, 0, 3, 2, 2)
        self.add(self.grid)

    # def get_remote_server_info(self):
    #     client = SSDPClient()
    #     devices = client.m_search(st="imx-ml-server")
    #     for device in devices:
    #         server_ip_address = device.get("location")
    #     return server_ip_address

    def ip_changed(self, widget):
        if  widget.get_active() == True:
            if widget.get_label() == self.enter_ip:
                self.entry2.set_activates_default(True)
                self.entry2.set_sensitive(True)
            else:
                self.entry2.set_activates_default(False)
                self.entry2.set_sensitive(False)
        
    def connect_to_server_thread(self,widget):
        client_thread = Thread(target=ClientWindow.connect_to_server,args=[cWin])
        client_thread.daemon = True
        client_thread.start()

    def connect_to_server(self):
        self.button3.set_sensitive(False)
        # initialises state in background
        Gst.init(None)
        self.main_loop = GObject.MainLoop()
        ml_data_set = "wget " + DATA_SET_LINK + DATA_SET
        out = subprocess.run(ml_data_set, stdout=subprocess.PIPE, shell= True)
        
        if self.entry2.get_activates_default() == True :
            self.server_ip = self.entry2.get_text()
        # else :
        #     self.server_ip = self.radio_ip2.get_text()

        client_pipeline = "v4l2src device=/dev/video0 ! "
        client_pipeline += "video/x-raw,width=640,height=480,framerate=30/1 ! tee name=t t. ! "
        client_pipeline += "queue max-size-buffers=2 leaky=2 ! imxvideoconvert_g2d ! video/x-raw,width=300,height=300,format=RGBA ! "
        client_pipeline += "videoconvert ! video/x-raw,format=RGB ! tensor_query_client sink-host={ip} src-host={ip} ! "
        client_pipeline += "tensor_decoder mode=bounding_boxes option1=tf-ssd option2={label} option3=0:1:2:3,50 option4=640:480 "
        client_pipeline += "option5=300:300 ! mix. t. ! queue max-size-buffers=2 ! imxcompositor_g2d "
        client_pipeline += "name=mix sink_0::zorder=2 sink_1::zorder=1 ! waylandsink"
        client_pipeline = client_pipeline.format(ip=self.server_ip,label=DATA_SET_PATH)
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
        button3_label.set_markup("<b> CONNECTED TO SERVER </b>")
        try: 
            self.main_loop.run()
        except: 
            self.main_loop.quit()

        #disconnecting the pipeline
        self.pipeline.set_state(Gst.State.NULL)
        bus.remove_signal_watch()

    def on_message(self, bus, message):   
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

class DisplayWindow(Gtk.Window):
    def __init__(self):
        # Main window
        super().__init__()
        self.set_default_size(230,180)
        self.set_resizable(False)
        self.set_border_width(20)
        self.set_position(Gtk.WindowPosition.CENTER)
        
        # Create widgets for server and client
        self.grid_display = Gtk.Grid(row_homogeneous=True, column_homogeneous=True, row_spacing=10, column_spacing=10) 
        self.grid_display.set_margin_end(10)
        self.grid_display.set_margin_start(10) 
        header = Gtk.HeaderBar()
        header.set_show_close_button(False)
        header.set_title("ML Server using NNStreamer")
        header.set_subtitle("ML Server on i.MX8M plus")
        self.set_titlebar(header)
        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        header.pack_end(quit_button)
        quit_button.connect("clicked", Gtk.main_quit)
        self.server_button = Gtk.Button(label="I AM SERVER")
        self.client_button = Gtk.Button(label="I AM CLIENT")
        self.server_button.connect("clicked",self.server_initiate)
        self.client_button.connect("clicked",self.client_initiate)
        self.grid_display.attach(self.server_button, 0, 0, 1, 1)
        self.grid_display.attach(self.client_button, 0, 2, 1, 1)
        self.add(self.grid_display)

    def server_initiate(self, widget):
        global sWin
        sWin = ServerWindow()
        sWin.connect("destroy", Gtk.main_quit)
        sWin.show_all()
        win.hide()

    def client_initiate(self, widget):
        global cWin
        cWin = ClientWindow()
        cWin.connect("destroy", Gtk.main_quit)
        cWin.show_all()
        win.hide()
    
if __name__ == "__main__":
    win = DisplayWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    caching_address = os.getcwd() + "/.cache/demoexperience"
    os.environ["VIV_VX_CACHE_BINARY_GRAPH_DIR"] = caching_address
    os.environ["VIV_VX_ENABLE_CACHE_GRAPH_BINARY"] = "1"
    Gtk.main()    