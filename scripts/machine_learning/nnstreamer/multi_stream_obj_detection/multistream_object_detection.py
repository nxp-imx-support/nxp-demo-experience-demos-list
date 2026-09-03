#!/usr/bin/env python3

"""
Copyright 2025-2026 NXP

SPDX-License-Identifier: BSD-3-Clause

This script launches the Object Detection NNStreamer example using a UI to pick settings.
"""

import os
import sys
import threading
import glob
import subprocess
import time
import gi
import re  # Added for camera detection

# Check for correct Gtk version
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk as gtk
from gi.repository import GLib
from gi.repository import Gst

# Import utils
sys.path.append("/opt/gopoint-apps/scripts/")
import utils

MODELS_PATH = "/opt/gopoint-apps/downloads/"

# Initialize GStreamer
Gst.init(None)

def threaded(fn):
    """
    Handle threads out of main GTK thread
    """

    def wrapper(*args, **kwargs):
        threading.Thread(target=fn, args=args, kwargs=kwargs).start()

    return wrapper


class NNStreamerLauncher:
    """The GUI window for the Object Detection example launcher"""

    def __init__(self):
        """Creates the UI window"""

        # Obtain GUI settings and configurations
        glade_file = (
            "/opt/gopoint-apps/"
            "scripts/machine_learning/nnstreamer/multi_stream_obj_detection/multistream_object_detection.glade"
        )
        self.builder = gtk.Builder()
        self.builder.add_from_file(glade_file)
        self.builder.connect_signals(self)

        # Create instances of widgets
        self.sources_list_1 = self.builder.get_object("sources-list-1")
        self.sources_list_2 = self.builder.get_object("sources-list-2")
        self.sources_list_3 = self.builder.get_object("sources-list-3")
        self.sources_list_4 = self.builder.get_object("sources-list-4")
        self.backend_list = self.builder.get_object("backend-list")
        self.resolution_list = self.builder.get_object("resolution-list")
        self.color_list = self.builder.get_object("color-list")
        self.display_performance = self.builder.get_object("display-performance")
        self.start_button = self.builder.get_object("start-button")
        self.header_bar = self.builder.get_object("header-bar")
        self.status_bar = self.builder.get_object("status-bar")
        self.about_button = self.builder.get_object("about-button")
        self.about_dialog = self.builder.get_object("about-dialog")
        self.progress_bar = self.builder.get_object("progress-bar")
        self.close_button = self.builder.get_object("close-button")

        # General variables
        self.labels = "coco_labels_list.txt"
        self.tflite_model = "ssdlite_mobilenet_v2_coco_no_postprocess.tflite"
        self.npu_tflite_model = (
            "ssdlite_mobilenet_v2_coco_quant_uint8_float32_no_postprocess.tflite"
        )
        self.vela_tflite_model = (
            MODELS_PATH
            + "ssdlite_mobilenet_v2_coco_quant_uint8_float32_no_postprocess_vela.tflite"
        )
        self.boxes_file = "box_priors.txt"

        # Progress bar config
        self.pulsing = False
        self.timeout_id = None
        self.progress_bar.set_show_text(False)

        # Get main application window
        window = self.builder.get_object("main-window")

        # GStreamer pipeline variables
        self.pipeline = None
        self.bus = None
        self.pipeline_running = False
        self.monitor_thread = None

        # Get platform
        self.platform = subprocess.check_output(
            ["cat", "/sys/devices/soc0/soc_id"]
        ).decode("utf-8")[:-1]

        # OpenVX graph caching is not available on i.MX 8QuadMax platform.
        if self.platform == "i.MX8MP":
            os.environ["VIV_VX_CACHE_BINARY_GRAPH_DIR"] = "/opt/gopoint-apps/downloads"
            os.environ["VIV_VX_ENABLE_CACHE_GRAPH_BINARY"] = "1"

        # Set libcamera environment variables
        os.environ["LIBCAMERA_PIPELINES_MATCH_LIST"] = "nxp/neo,imx8-isi"
        os.environ["LIBCAMERA_IPA_MODULE_PATH"] = "/usr/lib/libcamera/ipa-nxp-neo-uguzzi"

        # Obtain available devices - only mx95mbcam cameras
        devices = []
        camera_paths = {}  # Store mapping of camera ID to full path
        
        cam_output = subprocess.check_output(['cam', '-l']).decode('utf-8')
        # Look for mx95mbcam cameras and extract full device paths
        matches = re.findall(r"(\d+): 'mx95mbcam' \((.*?)\)", cam_output)
        for camera_id, device_path in matches:
            device_label = f"Camera {camera_id}"
            camera_paths[camera_id] = device_path
            self.sources_list_1.append_text(device_label)
            self.sources_list_2.append_text(device_label)
            self.sources_list_3.append_text(device_label)
            self.sources_list_4.append_text(device_label)
            devices.append(device_label)
        
        # Store camera paths for later use
        self.camera_paths = camera_paths
        
        if devices:
            # Set different cameras for each source list if available
            self.sources_list_1.set_active(0)  # Camera 1
            if len(devices) > 1:
                self.sources_list_2.set_active(1)  # Camera 2
            else:
                self.sources_list_2.set_active(0)
            if len(devices) > 2:
                self.sources_list_3.set_active(2)  # Camera 3
            else:
                self.sources_list_3.set_active(0)
            if len(devices) > 3:
                self.sources_list_4.set_active(3)  # Camera 4
            else:
                self.sources_list_4.set_active(0)

        # Populate backends - Show only CPU
        backends = []
        # Comment out NPU addition
        # if self.platform in ("i.MX93", "i.MX95", "i.MX8MP"):
        #     backends.append("NPU")
        backends.append("CPU")
        for backend in backends:
            self.backend_list.append_text(backend)
        # Comment out GPU option as well
        # if self.platform in ("i.MX8MP", "i.MX8MN", "i.MX8QM"):
        #     self.backend_list.append_text("GPU")
        self.backend_list.set_active(0)

        # Populate resolution for video
        resolutions = ["1920x1080", "640x480"]
        for resolution in resolutions:
            self.resolution_list.append_text(resolution)
        self.resolution_list.set_active(1)

        colors = ["white", "red", "green", "blue", "black"]
        for color in colors:
            self.color_list.append_text(color)
        self.color_list.set_active(0)

        self.close_button.connect("clicked", self.quit_app)
        window.connect("delete-event", gtk.main_quit)
        window.show()

        # Preload model
        preload_thread = threading.Thread(target=self.preload, daemon=True)
        preload_thread.start()

    def quit_app(self, widget):
        """Closes GTK+3 GUI and kills NNStreamer process"""
        self.pipeline_running = False
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
        gtk.main_quit()

    def about_button_activate(self, widget):
        """
        Function to handle about dialog window
        """
        self.about_dialog.run()
        time.sleep(1)
        self.about_dialog.hide()
        return True

    def on_timeout(self):
        """
        Function to handle progress bar
        """
        if self.pulsing:
            self.progress_bar.set_show_text(True)
            self.progress_bar.pulse()
            return True
        self.progress_bar.set_show_text(False)
        self.progress_bar.set_fraction(0.0)
        return False

    def compile_vela(self):
        """Compile vela models"""
        if not os.path.exists(self.vela_tflite_model):
            GLib.idle_add(
                self.status_bar.set_text,
                "Compiling model with vela and saving to cache...",
            )

            subprocess.run(
                "vela "
                + self.npu_tflite_model
                + " --output-dir=/opt/gopoint-apps/downloads/",
                shell=True,
                check=True,
            )

    def preload(self):
        """Download the models, compile the models and setup default configuration"""

        # Block run button and start progress bar
        self.unblock_buttons(False)
        self.pulsing = True
        self.timeout_id = GLib.timeout_add(50, self.on_timeout)

        GLib.idle_add(self.status_bar.set_text, "Downloading CPU model...")
        self.tflite_model = utils.download_file(self.tflite_model)

        # Verify if download is successfull
        if self.tflite_model == -1:
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.tflite_model == -2:
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.tflite_model == -3:
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /opt/gopoint-apps/downloads and try to download again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return

        GLib.idle_add(self.status_bar.set_text, "CPU model successfully downloaded!")

        GLib.idle_add(self.status_bar.set_text, "Downloading NPU model...")
        self.npu_tflite_model = utils.download_file(self.npu_tflite_model)

        # Verify if download is successfull
        if self.npu_tflite_model == -1:
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.npu_tflite_model == -2:
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.npu_tflite_model == -3:
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /opt/gopoint-apps/downloads and try to download again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return

        GLib.idle_add(self.status_bar.set_text, "NPU model successfully downloaded!")

        GLib.idle_add(self.status_bar.set_text, "Downloading labels...")
        self.labels = utils.download_file(self.labels)

        # Verify if download is successfull
        if self.labels == -1:
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.labels == -2:
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.labels == -3:
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /opt/gopoint-apps/downloads and try to download again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return

        GLib.idle_add(self.status_bar.set_text, "Labels successfully downloaded!")

        GLib.idle_add(self.status_bar.set_text, "Downloading box priors...")
        self.boxes_file = utils.download_file(self.boxes_file)

        # Verify if download is successfull
        if self.boxes_file == -1:
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.boxes_file == -2:
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.boxes_file == -3:
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /opt/gopoint-apps/downloads and try to download again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return

        GLib.idle_add(self.status_bar.set_text, "Box priors successfully downloaded!")

        # Compile model using vela tool for i.MX 93
        if self.platform == "i.MX93":
            self.compile_vela()

        # If i.MX 8M PLus, pre-run model to avoid warmup time during execution
        if self.platform == "i.MX8MP":
            GLib.idle_add(
                self.status_bar.set_text,
                "Warming up model and saving to cache...",
            )

            subprocess.run(
                "/usr/bin/tensorflow-lite-*/examples/benchmark_model "
                "--graph="
                + self.npu_tflite_model
                + " --external_delegate_path=/usr/lib/libvx_delegate.so",
                shell=True,
                check=True,
            )

        self.pulsing = False
        GLib.idle_add(self.status_bar.set_text, "Application is ready!")
        self.unblock_buttons(True)
        self.resolution_list.set_sensitive(False)

    def unblock_buttons(self, status):
        """Block/unblock buttons"""
        self.start_button.set_sensitive(status)
        self.sources_list_1.set_sensitive(status)
        self.sources_list_2.set_sensitive(status)
        self.sources_list_3.set_sensitive(status)
        self.sources_list_4.set_sensitive(status)
        self.backend_list.set_sensitive(status)
        self.resolution_list.set_sensitive(status)
        self.color_list.set_sensitive(status)
        self.display_performance.set_sensitive(status)

    def on_bus_message(self, bus, message):
        """Handle GStreamer bus messages"""
        t = message.type
        if t == Gst.MessageType.EOS:
            print("End-of-stream")
            self.pipeline_running = False
            GLib.idle_add(self.status_bar.set_text, "Pipeline ended normally")
            GLib.idle_add(self.unblock_buttons, True)
            self.pipeline.set_state(Gst.State.NULL)
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            print(f"Error: {err}, {debug}")
            self.pipeline_running = False
            GLib.idle_add(self.status_bar.set_text, f"Pipeline error: {err}")
            GLib.idle_add(self.unblock_buttons, True)
            self.pipeline.set_state(Gst.State.NULL)
        elif t == Gst.MessageType.WARNING:
            warn, debug = message.parse_warning()
            print(f"Warning: {warn}, {debug}")
        elif t == Gst.MessageType.STATE_CHANGED:
            old_state, new_state, pending_state = message.parse_state_changed()
            if message.src == self.pipeline:
                print(f"Pipeline state changed from {old_state.value_nick} to {new_state.value_nick}")
                if new_state == Gst.State.PLAYING:
                    GLib.idle_add(self.status_bar.set_text, "Pipeline is running...")
        return True

    def create_camera_branch(self, camera_name, camera_index, model, labels, boxes, w, h):
        """Create a camera processing branch"""
        dewarp_file = "/opt/gopoint-apps/scripts/machine_learning/nnstreamer/multi_stream_obj_detection/dewarp/Buffer_dewarp_1.bin"
        
        # Camera source
        camera_src = Gst.ElementFactory.make("libcamerasrc", f"camera_src_{camera_index}")
        camera_src.set_property("camera-name", camera_name)
        
        # Dewarp
        dewarp = Gst.ElementFactory.make("imxvideoconvert_ocl", f"dewarp_{camera_index}")
        dewarp.set_property("video-warp-enable", True)
        dewarp.set_property("video-warp-coord-file", dewarp_file)
        
        # Video caps
        video_caps = Gst.Caps.from_string("video/x-raw,format=YUY2,framerate=5/1")
        video_filter = Gst.ElementFactory.make("capsfilter", f"video_caps_{camera_index}")
        video_filter.set_property("caps", video_caps)
        
        # Main queue
        main_queue = Gst.ElementFactory.make("queue", f"main_queue_{camera_index}")
        main_queue.set_property("max-size-buffers", 10)
        main_queue.set_property("leaky", 2)  # downstream
        
        # Tee
        tee = Gst.ElementFactory.make("tee", f"tee_{camera_index}")
        
        # Neural network branch
        nn_queue = Gst.ElementFactory.make("queue", f"nn_queue_{camera_index}")
        nn_queue.set_property("max-size-buffers", 2)
        nn_queue.set_property("leaky", 2)
        
        nn_convert = Gst.ElementFactory.make("imxvideoconvert_g2d", f"nn_convert_{camera_index}")
        
        nn_caps = Gst.Caps.from_string("video/x-raw,width=300,height=300,format=RGBA")
        nn_filter = Gst.ElementFactory.make("capsfilter", f"nn_caps_{camera_index}")
        nn_filter.set_property("caps", nn_caps)
        
        video_convert = Gst.ElementFactory.make("videoconvert", f"video_convert_{camera_index}")
        
        rgb_caps = Gst.Caps.from_string("video/x-raw,format=RGB")
        rgb_filter = Gst.ElementFactory.make("capsfilter", f"rgb_caps_{camera_index}")
        rgb_filter.set_property("caps", rgb_caps)
        
        tensor_converter = Gst.ElementFactory.make("tensor_converter", f"tensor_converter_{camera_index}")
        
        tensor_filter = Gst.ElementFactory.make("tensor_filter", f"tensor_filter_{camera_index}")
        tensor_filter.set_property("framework", "tensorflow-lite")
        tensor_filter.set_property("model", model)
        tensor_filter.set_property("custom", "Delegate:XNNPACK,NumThreads=2")
        
        tensor_decoder = Gst.ElementFactory.make("tensor_decoder", f"tensor_decoder_{camera_index}")
        tensor_decoder.set_property("mode", "bounding_boxes")
        tensor_decoder.set_property("option1", "mobilenet-ssd")
        tensor_decoder.set_property("option2", labels)
        tensor_decoder.set_property("option3", boxes)
        tensor_decoder.set_property("option4", f"{w}:{h}")
        tensor_decoder.set_property("option5", "300:300")
        tensor_decoder.set_property("option6", "0.3")
        
        nn_convert2 = Gst.ElementFactory.make("imxvideoconvert_g2d", f"nn_convert2_{camera_index}")
        
        rgba_caps = Gst.Caps.from_string("video/x-raw,format=RGBA")
        rgba_filter = Gst.ElementFactory.make("capsfilter", f"rgba_caps_{camera_index}")
        rgba_filter.set_property("caps", rgba_caps)
        
        # Image display branch
        img_queue = Gst.ElementFactory.make("queue", f"img_queue_{camera_index}")
        img_queue.set_property("max-size-buffers", 2)
        img_queue.set_property("leaky", 2)
        
        img_convert = Gst.ElementFactory.make("videoconvert", f"img_convert_{camera_index}")
        
        # Dummy branch
        dummy_queue = Gst.ElementFactory.make("queue", f"dummy_queue_{camera_index}")
        dummy_queue.set_property("max-size-buffers", 2)
        dummy_queue.set_property("leaky", 2)
        
        dummy_convert = Gst.ElementFactory.make("videoconvert", f"dummy_convert_{camera_index}")
        
        dummy_sink = Gst.ElementFactory.make("fakesink", f"dummy_sink_{camera_index}")
        dummy_sink.set_property("sync", False)
        
        return {
            'elements': [
                camera_src, dewarp, video_filter, main_queue, tee,
                nn_queue, nn_convert, nn_filter, video_convert, rgb_filter,
                tensor_converter, tensor_filter, tensor_decoder, nn_convert2, rgba_filter,
                img_queue, img_convert, dummy_queue, dummy_convert, dummy_sink
            ],
            'camera_src': camera_src,
            'tee': tee,
            'nn_output': rgba_filter,
            'img_output': img_convert,
            'dummy_sink': dummy_sink
        }

    def start(self, widget):
        """Read UI options on the main thread, then launch the demo in a worker thread.

        GTK is not thread-safe, so widget access must happen on the main GTK
        thread. Only the pipeline build/launch runs in the worker thread.
        """
        self.unblock_buttons(False)

        self.status_bar.set_text("Creating GStreamer pipeline...")

        # Get options from user (must be read on the main thread)
        device1 = self.sources_list_1.get_active_text()
        device2 = self.sources_list_2.get_active_text()
        device3 = self.sources_list_3.get_active_text()
        device4 = self.sources_list_4.get_active_text()
        backend = self.backend_list.get_active_text()
        color = self.color_list.get_active_text()
        performance_display = self.display_performance.get_active()

        self._start_worker(device1, device2, device3, device4, backend, color, performance_display)
        return True

    @threaded
    def _start_worker(self, device1, device2, device3, device4, backend, color, performance_display):
        """Build the GStreamer pipeline and start it off the main thread."""
        # Extract camera paths from device labels
        def get_camera_path(device_label):
            camera_id = device_label.split("Camera ")[1]
            return self.camera_paths.get(camera_id, device_label)

        camera_paths = [
            "/base/soc/bus@42000000/i2c@42530000/max96724@27/i2c-mux/i2c@0/mx95mbcam@40",
            "/base/soc/bus@42000000/i2c@42530000/max96724@27/i2c-mux/i2c@1/mx95mbcam@40",
            "/base/soc/bus@42000000/i2c@42530000/max96724@27/i2c-mux/i2c@2/mx95mbcam@40",
            "/base/soc/bus@42000000/i2c@42530000/max96724@27/i2c-mux/i2c@3/mx95mbcam@40"
        ]

        # Configure arguments
        model = self.npu_tflite_model
        if backend == "GPU":
            model = self.tflite_model
        elif backend == "NPU" and self.platform == "i.MX93":
            model = self.vela_tflite_model

        # Define grid layout
        rows = 1080
        cols = 1920
        w = cols // 2
        h = rows // 2

        try:
            # Create pipeline
            self.pipeline = Gst.Pipeline.new("multistream_pipeline")
            
            # Create compositor
            compositor = Gst.ElementFactory.make("imxcompositor_g2d", "compositor")
            
            # Create sink
            sink = Gst.ElementFactory.make("waylandsink", "sink")
            sink.set_property("sync", False)
            
            # Add compositor and sink to pipeline
            self.pipeline.add(compositor)
            self.pipeline.add(sink)
            
            # Link compositor to sink
            compositor.link(sink)
            
            # Create camera branches
            camera_branches = []
            for i, camera_path in enumerate(camera_paths):
                branch = self.create_camera_branch(camera_path, i, model, self.labels, self.boxes_file, w, h)
                camera_branches.append(branch)
                
                # Add all elements to pipeline
                for element in branch['elements']:
                    self.pipeline.add(element)
            
            # Link elements within each branch and connect to compositor
            for i, branch in enumerate(camera_branches):
                elements = branch['elements']
                
                # Link camera source chain
                elements[0].link(elements[1])  # camera_src -> dewarp
                elements[1].link(elements[2])  # dewarp -> video_filter
                elements[2].link(elements[3])  # video_filter -> main_queue
                elements[3].link(elements[4])  # main_queue -> tee
                
                # Link neural network branch
                tee = elements[4]
                nn_queue = elements[5]
                tee.link(nn_queue)
                
                # Link NN processing chain
                for j in range(5, 14):
                    elements[j].link(elements[j + 1])
                
                # Link image display branch
                img_queue = elements[15]
                tee.link(img_queue)
                elements[15].link(elements[16])  # img_queue -> img_convert
                
                # Link dummy branch
                dummy_queue = elements[17]
                tee.link(dummy_queue)
                elements[17].link(elements[18])  # dummy_queue -> dummy_convert
                elements[18].link(elements[19])  # dummy_convert -> dummy_sink
                
                # Connect to compositor
                # Get compositor sink pads
                img_pad = compositor.get_request_pad(f"sink_{i}")
                nn_pad = compositor.get_request_pad(f"sink_{i + 4}")
                
                # Set compositor pad properties
                img_pad.set_property("xpos", (i % 2) * w)
                img_pad.set_property("ypos", (i // 2) * h)
                img_pad.set_property("width", w)
                img_pad.set_property("height", h)
                img_pad.set_property("zorder", 1)
                
                nn_pad.set_property("xpos", (i % 2) * w)
                nn_pad.set_property("ypos", (i // 2) * h)
                nn_pad.set_property("width", w)
                nn_pad.set_property("height", h)
                nn_pad.set_property("zorder", 2)
                
                # Link to compositor
                branch['img_output'].get_static_pad("src").link(img_pad)
                branch['nn_output'].get_static_pad("src").link(nn_pad)
            
            # Set up bus
            self.bus = self.pipeline.get_bus()
            self.bus.add_signal_watch()
            self.bus.connect("message", self.on_bus_message)
            
            # Start pipeline
            GLib.idle_add(self.status_bar.set_text, "Starting pipeline...")
            
            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                GLib.idle_add(self.status_bar.set_text, "Failed to start pipeline")
                GLib.idle_add(self.unblock_buttons, True)
                return False
            
            self.pipeline_running = True
            print("Pipeline started successfully")
            
        except Exception as e:
            print(f"Error creating pipeline: {e}")
            GLib.idle_add(self.status_bar.set_text, f"Error: {str(e)}")
            GLib.idle_add(self.unblock_buttons, True)
            return False

        return True


if __name__ == "__main__":
    win = NNStreamerLauncher()
    gtk.main()
