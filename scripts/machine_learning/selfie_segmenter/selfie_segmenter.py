#!/usr/bin/env python3

"""
Copyright 2023-2024 NXP
SPDX-License-Identifier: Apache-2.0

Models: MediaPipe's Selfie Segmenter
Models licensed under: Apache-2.0
Original model available at:
https://developers.google.com/mediapipe/solutions/vision/image_segmenter

Model Card:
https://storage.googleapis.com/mediapipe-assets/Model%20Card%20MediaPipe%20Selfie%20Segmentation.pdf

This model was created by:
    Tingbo Hou, Google
    Siargey Pisarchyk, Google
    Karthik Raveendran, Google

This script shows human segmentation from video. Application could be aimed at video conference.
MediaPipe's Selfie Segmenter model was quantized to be accelerated by the NPU on the i.MX8M Plus
and i.MX93 EVKs.
"""

import os
import sys
import subprocess
import threading
import time
import re
import glob
import logging
import cairo
import numpy as np
import gi

from PIL import Image

# Check for correct Gtk and Gst versions
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
gi.require_foreign("cairo")
from gi.repository import Gtk as gtk
from gi.repository import Gst, GLib

# Import utils
sys.path.append("/home/root/.nxp-demo-experience/scripts")
import utils

MODELS_PATH = "/home/root/.cache/gopoint/"


def threaded(fn):
    """Handle threads out of main GTK thread"""

    def wrapper(*args, **kwargs):
        threading.Thread(target=fn, args=args, kwargs=kwargs).start()

    return wrapper


class SelfieSegmenter:
    """Selfie Segmenter GUI launcher and application"""

    def __init__(self):
        # Obtain GUI settings and configurations
        glade_file = (
            "/home/root/.nxp-demo-experience/"
            "scripts/machine_learning/selfie_segmenter/selfie_segmenter.glade"
        )
        self.builder = gtk.Builder()
        self.builder.add_from_file(glade_file)
        self.builder.connect_signals(self)

        # Get main application window and about dialog
        window = self.builder.get_object("main-window")
        self.about_dialog = self.builder.get_object("about-dialog")

        # Create instances of labels
        self.source_label = self.builder.get_object("source-label")
        self.backend_label = self.builder.get_object("backend-label")
        self.demo_label = self.builder.get_object("demo-label")
        self.model_label = self.builder.get_object("version-label")
        self.color_label = self.builder.get_object("color-label")
        self.background_label = self.builder.get_object("background-label")
        self.refresh_label = self.builder.get_object("refresh-label")
        self.inference_label = self.builder.get_object("inference-label")

        # Create instances of labels for performance information
        self.video_ms = self.builder.get_object("video-ms")
        self.video_fps = self.builder.get_object("video-fps")
        self.inference_ms = self.builder.get_object("inference-ms")
        self.inference_ips = self.builder.get_object("inference-ips")

        # Create instances for combo boxes
        self.source_box = self.builder.get_object("combo-box-sources")
        self.backend_box = self.builder.get_object("combo-box-backend")
        self.mode_box = self.builder.get_object("combo-box-mode")
        self.version_box = self.builder.get_object("combo-box-version")
        self.color_box = self.builder.get_object("combo-box-color")

        # Create instances for buttons
        self.file_chooser = self.builder.get_object("chooser-image")
        self.run_button = self.builder.get_object("run-button")
        self.about_button = self.builder.get_object("about-button")
        self.close_button = self.builder.get_object("close-button")

        # Create progress bar
        self.progress_bar = self.builder.get_object("progress-bar")
        self.status_bar = self.builder.get_object("status-bar")

        # Progress bar config
        self.pulsing = False
        self.timeout_id = None
        self.progress_bar.set_show_text(False)

        # General variables
        self.platform = str()
        self.backends = ["NPU", "CPU"]
        self.demo_modes = ["Background substitution", "Segmentation mask"]
        self.model_versions = ["General", "Landscape"]
        self.text_colors = ["Red", "Green", "Blue", "Black", "White"]
        self.nxp_converter = str()
        self.nxp_compositor = str()
        self.version = str()

        # Models variables
        self.backend = str()
        self.tflite_model = str()
        self.general_model = str()
        self.landscape_model = str()
        self.vela_general_model = str()
        self.vela_landscape_model = str()

        # Text color
        self.red = None
        self.green = None
        self.blue = None

        # GStreamer variables
        self.main_loop = None
        self.pipeline = None
        self.video_caps = None
        self.running = False

        self.first_frame = True
        self.number_frames = 0
        self.current_framerate = 1000
        self.threshold = 0.15

        # Segmentation/inference variables
        self.frame = None
        self.segmentation = None
        self.condition_frame = None

        # Background images and paths
        self.general_background = None
        self.landscape_background = None
        self.background = None

        # Default size of video and model
        self.video_width = 480
        self.video_height = 480
        self.model_width = 256
        self.model_height = 256
        self.aspect_ratio = "1/1"

        # Check target (i.MX8M Plus vs i.MX93)
        if os.path.exists("/usr/lib/libvx_delegate.so"):
            self.platform = "i.MX8MP"
            self.cache_enable = (
                "VIV_VX_ENABLE_CACHE_GRAPH_BINARY='1' "
                + "VIV_VX_CACHE_BINARY_GRAPH_DIR=/home/root/.cache/gopoint "
            )
            self.nxp_converter = "imxvideoconvert_g2d"
            self.nxp_compositor = "imxcompositor_g2d"
        elif os.path.exists("/usr/lib/libethosu_delegate.so"):
            self.platform = "i.MX93"
            self.nxp_converter = "imxvideoconvert_pxp"
            self.nxp_compositor = "imxcompositor_pxp"
        else:
            print("Target is not supported!")
            sys.exit()

        # Obtain available devices
        for device in glob.glob("/dev/video*"):
            self.source_box.append_text(device)
        self.source_box.set_active(0)

        # Populate backends
        for backend in self.backends:
            self.backend_box.append_text(backend)
        self.backend_box.set_active(0)

        # Populate demo modes
        for demo_mode in self.demo_modes:
            self.mode_box.append_text(demo_mode)
        self.mode_box.set_active(0)

        # Populate model versions
        for version in self.model_versions:
            self.version_box.append_text(version)
        self.version_box.set_active(0)

        # Populate text colors
        for color in self.text_colors:
            self.color_box.append_text(color)
        self.color_box.set_active(0)

        Gst.init()
        self.main_loop = GLib.MainLoop()

        # Connect signals
        self.close_button.connect("clicked", self.quit_app)
        window.connect("delete-event", gtk.main_quit)
        window.show()

        # Preload model
        preload_thread = threading.Thread(target=self.preload, daemon=True)
        preload_thread.start()

    def quit_app(self, widget):
        """Closes GStreamer pipeline and GTK+3 GUI"""
        self.main_loop.quit()
        gtk.main_quit()

    def about_button_activate(self, widget):
        """
        Function to handle about dialog window
        """
        self.about_dialog.run()
        time.sleep(100 / 1000)
        self.about_dialog.hide()
        return True

    def on_mode_changed(self, widget):
        """Function to change demo mode configurations"""
        if self.mode_box.get_active_text() == "Background substitution":
            self.file_chooser.set_sensitive(True)
        else:
            self.file_chooser.set_sensitive(False)

    def on_version_changed(self, widget):
        """Function to change version configurations"""
        self.version = self.version_box.get_active_text()
        if self.version == "General":
            self.video_width = 480
            self.video_height = 480
            self.model_width = 256
            self.model_height = 256
            self.aspect_ratio = "1/1"
            self.tflite_model = self.general_model
            if self.platform == "i.MX93" and self.backend == "NPU":
                self.tflite_model = self.vela_general_model
            if self.general_background is not None:
                self.background = Image.open(self.general_background)
                self.file_chooser.set_filename(self.general_background)
        else:
            self.video_width = 640
            self.video_height = 360
            self.model_width = 256
            self.model_height = 144
            self.aspect_ratio = "16/9"
            self.tflite_model = self.landscape_model
            if self.platform == "i.MX93" and self.backend == "NPU":
                self.tflite_model = self.vela_landscape_model
            if self.landscape_background is not None:
                self.background = Image.open(self.landscape_background)
                self.file_chooser.set_filename(self.landscape_background)

        # Create frames for segmentation
        self.condition_frame = np.full(
            (self.model_height, self.model_width, 3), fill_value=0, dtype=np.uint8
        )
        self.frame = np.full(
            (self.video_height, self.video_width, 3), fill_value=0, dtype=np.uint8
        )
        self.segmentation = np.full(
            (self.video_height, self.video_width, 3), fill_value=0, dtype=np.uint8
        )

    def resize_background(self, widget):
        """Resize background image"""
        self.background = self.file_chooser.get_filename()
        if self.background is not None:
            self.background = Image.open(self.background)
            if self.background.size != (self.video_width, self.video_height):
                self.background = self.background.resize(
                    (self.video_width, self.video_height)
                )

    def about_dialog_activate(self, widget):
        """Function to handle the about dialog window"""
        self.about_dialog.run()
        self.about_dialog.hide()

    def on_timeout(self):
        """Function to handle progress bar"""
        if self.pulsing:
            self.progress_bar.set_show_text(True)
            self.progress_bar.pulse()
            return True
        self.progress_bar.set_show_text(False)
        self.progress_bar.set_fraction(0.0)
        return False

    def preload(self):
        """Download the models, compile the models and setup default configuration"""

        # Block run button and start progress bar
        self.unblock_buttons(False)
        self.pulsing = True
        self.timeout_id = GLib.timeout_add(50, self.on_timeout)

        GLib.idle_add(self.status_bar.set_text, "Downloading general model...")
        self.general_model = utils.download_file("selfie_segmenter_int8.tflite")

        # Verify if download is successfull
        if self.general_model == -1:
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.general_model == -2:
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.general_model == -3:
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /home/root/.cache/gopoint and try to download again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return

        GLib.idle_add(
            self.status_bar.set_text, "General model successfully downloaded!"
        )

        GLib.idle_add(self.status_bar.set_text, "Downloading general background...")
        self.general_background = utils.download_file("background.jpg")

        # Verify if download is successfull
        if self.general_background == -1:
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.general_background == -2:
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.general_background == -3:
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /home/root/.cache/gopoint and try to download again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return

        GLib.idle_add(
            self.status_bar.set_text, "General background successfully downloaded!"
        )

        GLib.idle_add(self.status_bar.set_text, "Downloading landscape model...")
        self.landscape_model = utils.download_file(
            "selfie_segmenter_landscape_int8.tflite"
        )

        # Verify if download is successfull
        if self.landscape_model == -1:
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.landscape_model == -2:
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.landscape_model == -3:
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /home/root/.cache/gopoint and try to download again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return

        GLib.idle_add(
            self.status_bar.set_text, "Landscape model successfully downloaded!"
        )

        GLib.idle_add(self.status_bar.set_text, "Downloading landscape background...")
        self.landscape_background = utils.download_file("background_landscape.jpg")

        # Verify if download is successfull
        if self.landscape_background == -1:
            GLib.idle_add(
                self.status_bar.set_text,
                "Cannot find files!\n"
                "Make sure required files are available in downloads database!",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.landscape_background == -2:
            GLib.idle_add(
                self.status_bar.set_text,
                "Download failed!\n"
                "Please make sure you have internet connection on the target and try again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return
        if self.landscape_background == -3:
            GLib.idle_add(
                self.status_bar.set_text,
                "Downloaded corrupted file!\n"
                "Please clean /home/root/.cache/gopoint and try to download again.",
            )
            self.pulsing = False
            self.unblock_buttons(True)
            return

        GLib.idle_add(
            self.status_bar.set_text, "Landscape background successfully downloaded!"
        )

        # Compile model using vela tool for i.MX93
        if self.platform == "i.MX93":
            self.compile_vela()

        # Create frames for segmentation
        self.condition_frame = np.full(
            (self.model_height, self.model_width, 3), fill_value=0, dtype=np.uint8
        )
        self.frame = np.full(
            (self.video_height, self.video_width, 3), fill_value=0, dtype=np.uint8
        )
        self.segmentation = np.full(
            (self.video_height, self.video_width, 3), fill_value=0, dtype=np.uint8
        )

        # Set default background image
        self.background = Image.open(self.general_background)
        self.file_chooser.set_filename(self.general_background)
        self.pulsing = False
        GLib.idle_add(self.status_bar.set_text, "Application is ready!")
        self.unblock_buttons(True)

    def unblock_buttons(self, status):
        """Block/unblock buttons"""
        self.source_box.set_sensitive(status)
        self.backend_box.set_sensitive(status)
        self.mode_box.set_sensitive(status)
        self.version_box.set_sensitive(status)
        self.color_box.set_sensitive(status)
        self.file_chooser.set_sensitive(status)
        self.run_button.set_sensitive(status)

    def compile_vela(self):
        """Compile vela models"""
        self.vela_general_model = self.vela_name(self.general_model)
        self.vela_landscape_model = self.vela_name(self.landscape_model)
        if not os.path.exists(self.vela_general_model):
            GLib.idle_add(
                self.status_bar.set_text,
                "Compiling general model with vela and saving to cache...",
            )

            subprocess.run(
                "vela "
                + self.general_model
                + " --output-dir=/home/root/.cache/gopoint/",
                shell=True,
                check=True,
            )

        if not os.path.exists(self.vela_landscape_model):
            GLib.idle_add(
                self.status_bar.set_text,
                "Compiling general model with vela and saving to cache...",
            )

            subprocess.run(
                "vela "
                + self.landscape_model
                + " --output-dir=/home/root/.cache/gopoint/",
                shell=True,
                check=True,
            )

    def vela_name(self, model_name):
        """
        Appends the vela label to model name
        """
        tokens = model_name.split(".tflite")
        return MODELS_PATH + (tokens[-2] + "_vela.tflite").split("/")[-1]

    @threaded
    def start(self, widget):
        """Start the selfie segmenter demo"""
        self.unblock_buttons(False)

        device = self.source_box.get_active_text()
        self.backend = self.backend_box.get_active_text()
        demo_mode = self.mode_box.get_active_text()
        self.version = self.version_box.get_active_text()

        # Set text color
        color = self.color_box.get_active_text()
        self.set_color(color)

        # Set backend and delegates
        if self.backend == "CPU":
            if self.platform == "i.MX8MP":
                backend = "true:CPU custom=NumThreads:4"
            else:
                backend = "true:CPU custom=NumThreads:2"
        else:
            if self.platform == "i.MX8MP":
                os.environ["USE_GPU_INFERENCE"] = "0"
                backend = (
                    "true:npu custom=Delegate:External,ExtDelegateLib:libvx_delegate.so"
                )
            else:
                backend = "true:npu custom=Delegate:External,ExtDelegateLib:libethosu_delegate.so"

        # Configure for general or landscape model
        if self.version == "General":
            self.video_width = 480
            self.video_height = 480
            self.model_width = 256
            self.model_height = 256
            self.aspect_ratio = "1/1"
            self.tflite_model = self.general_model
            if self.platform == "i.MX93" and self.backend == "NPU":
                self.tflite_model = self.vela_general_model
        if self.version == "Landscape":
            self.video_width = 640
            self.video_height = 360
            self.model_width = 256
            self.model_height = 144
            self.aspect_ratio = "16/9"
            self.tflite_model = self.landscape_model
            if self.platform == "i.MX93" and self.backend == "NPU":
                self.tflite_model = self.vela_landscape_model

        # Pipeline for background subtraction
        if demo_mode == "Background substitution":
            gst_launch_cmdline = (
                # Define camera source pipeline
                "v4l2src device="
                + device
                + " ! video/x-raw,width=640,height=480,framerate=30/1 ! "
                + "aspectratiocrop aspect-ratio="
                + self.aspect_ratio
                + " ! "
                + self.nxp_converter
                + " rotation=horizontal-flip ! video/x-raw,width="
                + str(self.video_width)
                + ",height="
                + str(self.video_height)
                # ML processing using tensor_filter
                + " ! tee name=t t. ! queue max-size-buffers=1 leaky=2 ! "
                + self.nxp_converter
                + " ! video/x-raw,width="
                + str(self.model_width)
                + ",height="
                + str(self.model_height)
                + " ! videoconvert ! video/x-raw,format=RGB ! tensor_converter ! "
                + "tensor_transform mode=arithmetic option=typecast:float32,div:255.0 ! "
                + "tensor_filter framework=tensorflow-lite model="
                + self.tflite_model
                + " accelerator="
                + backend
                + " name=tensor_filter latency=1 ! tensor_sink name=tensor_sink "
                # Appsink, sends the frame to be processed outside of pipeline
                + "t. ! queue max-size-buffers=1 leaky=2 ! videoconvert ! video/x-raw,format=RGB ! "
                + "appsink name=frame_sink emit-signals=True "
                # Appsrc, gets the output with background substitution
                + "appsrc name=result_src is-live=True format=GST_FORMAT_TIME ! "
                + "video/x-raw,width="
                + str(self.video_width)
                + ",height="
                + str(self.video_height)
                + ",format=RGB,framerate=30/1 ! videoconvert"
                + " ! cairooverlay name=cairo_text ! queue max-size-buffers=1 leaky=2 ! "
                + "fpsdisplaysink name=wayland_sink text-overlay=false video-sink=waylandsink "
                + "sync=false"
            )

            self.pipeline = Gst.parse_launch(gst_launch_cmdline)

            # Tensor sink signal : new data callback
            tensor_sink = self.pipeline.get_by_name("tensor_sink")
            tensor_sink.connect("new-data", self.new_data)

            # Frame sink signal: new frame callback
            frame_sink = self.pipeline.get_by_name("frame_sink")
            frame_sink.connect("new-sample", self.new_frame, None)

            # Result source signal: on need data callback
            output_src = self.pipeline.get_by_name("result_src")
            output_src.connect("need-data", self.on_need_data)

        # Pipeline for mask segmentation demo
        else:
            # Define compositor that shows input frame and mask segmentation side to side
            gst_launch_cmdline = (
                self.nxp_compositor
                + " latency=33333333 min-upstream-latency=33333333 name=comp sink_1::ypos=0 "
            )
            if self.version == "Landscape":
                gst_launch_cmdline += (
                    "sink_0::ypos="
                    + str(self.video_height)
                    + " sink_0::height=360 sink_0::width=640 sink_1::height=360 sink_0::xpos=0 ! "
                )
            else:
                gst_launch_cmdline += (
                    "sink_0::ypos=0 sink_0::xpos=" + str(self.video_width) + " ! "
                )
            gst_launch_cmdline += (
                "cairooverlay name=cairo_text ! fpsdisplaysink name=wayland_sink "
                + "text-overlay=false video-sink=waylandsink "
                # Define camera source pipeline
                + "v4l2src device="
                + device
                + " ! video/x-raw,width=640,height=480,framerate="
                + "30/1 ! aspectratiocrop aspect-ratio="
                + self.aspect_ratio
                + " ! "
                + self.nxp_converter
                + " rotation=horizontal-flip ! video/x-raw,width="
                + str(self.video_width)
                + ",height="
                + str(self.video_height)
                # ML processing using tensor_filter
                + " ! tee name=t t. ! queue max-size-buffers=1 leaky=2 ! "
                + self.nxp_converter
                + " ! video/x-raw,width="
                + str(self.model_width)
                + ",height="
                + str(self.model_height)
                + " ! videoconvert ! video/x-raw,format=RGB ! tensor_converter ! "
                + "tensor_transform mode=arithmetic option=typecast:float32,div:255.0 ! "
                + "tensor_filter framework=tensorflow-lite model="
                + self.tflite_model
                + " accelerator="
                + backend
                + " name=tensor_filter latency=1 ! "
                + "tensor_decoder mode=image_segment option1=snpe-depth option2=0 ! "
            )
            if self.platform == "i.MX93":
                gst_launch_cmdline += "videoconvert ! videoscale"
            else:
                gst_launch_cmdline += self.nxp_converter
            gst_launch_cmdline += (
                " ! video/x-raw,width="
                + str(self.video_width)
                + ",height="
                + str(self.video_height)
            )
            if self.platform == "i.MX8MP":
                gst_launch_cmdline += ",format=RGBA"
            gst_launch_cmdline += (
                " ! comp.sink_0 "
                # Send input frame to compositor
                + "t. ! queue max-size-buffers=1 leaky=2 ! "
                + "comp.sink_1 "
            )

            self.pipeline = Gst.parse_launch(gst_launch_cmdline)

        self.tensor_filter = self.pipeline.get_by_name("tensor_filter")
        self.wayland_sink = self.pipeline.get_by_name("wayland_sink")

        # Draws text information to display
        cairo_draw = self.pipeline.get_by_name("cairo_text")
        cairo_draw.connect("draw", self.draw_cb)
        cairo_draw.connect("caps-changed", self.prepare_overlay_cb)

        # Bus and message callback
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_bus_message)

        # Start pipeline
        self.running = True
        self.pipeline.set_state(Gst.State.PLAYING)

        self.main_loop.run()

        # Ends pipeline
        self.running = False
        self.pipeline.set_state(Gst.State.NULL)
        bus.remove_signal_watch()

    def set_color(self, color):
        """Set color for text overlay"""
        self.red = self.green = self.blue = 0
        if color == "Red":
            self.red = 1
        if color == "Green":
            self.green = 1
        if color == "Blue":
            self.blue = 1
        if color == "White":
            self.red = self.blue = self.green = 1

    def on_need_data(self, src, length):
        """Function to send output to GStreamer pipeline using appsrc

        :param src: appsink element
        :param length: --
        :return: None
        """

        if self.running:
            data = self.segmentation.tobytes()
            buf = Gst.Buffer.new_allocate(None, len(data), None)
            buf.fill(0, data)
            buf.duration = (1 / 30.0) * Gst.SECOND  # Aim to 30FPS
            timestamp = self.number_frames * buf.duration
            buf.pts = buf.dts = int(timestamp)
            buf.offset = timestamp
            self.number_frames += 1

            # Send buffer to GStreamer pipeline
            retval = src.emit("push-buffer", buf)
            if retval != Gst.FlowReturn.OK:
                print(retval)

    def new_frame(self, sink, buffer):
        """Callback to get frame from appsink

        :param sink: appsink element
        :param buffer: buffer from element
        :return: None
        """

        if self.running:
            sample = sink.emit("pull-sample")
            sample_buf = sample.get_buffer()
            self.frame = np.ndarray(
                (self.video_height, self.video_width, 3),
                buffer=sample_buf.extract_dup(0, sample_buf.get_size()),
                dtype=np.uint8,
            )

    def new_data(self, sink, buffer):
        """Callback to get tensor output from tensor sink

        :param sink: tensor sink element
        :param buffer: buffer from element
        :return: None
        """
        if self.running:
            mask_mem = buffer.peek_memory(0)
            ret, mask = mask_mem.map(Gst.MapFlags.READ)
            if ret:
                decoded_mask = np.frombuffer(mask.data, dtype=np.float32)
                decoded_mask = decoded_mask.reshape(
                    (self.model_height, self.model_width, 1)
                )

                # Interpret segmentation
                condition = decoded_mask > self.threshold
                self.condition_frame[:, :, 0] = condition[:, :, 0]
                self.condition_frame[:, :, 1] = condition[:, :, 0]
                self.condition_frame[:, :, 2] = condition[:, :, 0]

                output = Image.fromarray(np.uint8(self.condition_frame))
                output = output.resize((self.video_width, self.video_height), 0)

                self.segmentation = np.where(
                    np.asarray(output, dtype=np.uint8),
                    np.asarray(self.frame, dtype=np.uint8),
                    np.asarray(self.background, dtype=np.uint8),
                )

                mask_mem.unmap(mask)

    def draw_cb(self, overlay, context, timestamp, duration):
        """Callback to draw text overlay"""

        if self.video_caps is not None and self.running:
            scale_height = self.video_height / 1080
            scale_width = self.video_width / 1920
            scale_text = max(scale_height, scale_width)

            context.select_font_face(
                "Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD
            )
            context.set_source_rgb(self.red, self.green, self.blue)
            context.set_font_size(int(30.0 * scale_text))
            context.move_to(int(30 * scale_width), int(20))
            context.show_text("i.MX NNStreamer - Selfie Segmenter")

            inference = self.tensor_filter.get_property("latency")

            # Get current framerate and avg. framerate
            output_wayland = self.wayland_sink.get_property("last-message")
            if output_wayland:
                got_text = re.findall(r"current:\s[\d]+[.\d]*", output_wayland)
                if got_text:
                    current_text = re.findall(r"current:\s[\d]+[.\d]*", output_wayland)[
                        0
                    ]
                    self.current_framerate = float(
                        re.findall(r"[\d]+[.\d]*", current_text)[0]
                    )

            context.move_to(
                int(30 * scale_width), int(self.video_height - (50 * scale_height))
            )

            if inference == 0:
                context.show_text("FPS: ")
                context.move_to(
                    int(30 * scale_width), int(self.video_height - (20 * scale_height))
                )
                context.show_text("IPS: ")
                GLib.idle_add(self.inference_ms.set_text, "--.-- ms")
                GLib.idle_add(self.inference_ips.set_text, "-- IPS")
            else:
                context.show_text(
                    f"FPS: {self.current_framerate:6.2f} "
                    + f"({(1.0/self.current_framerate * 1000):6.2f} ms)"
                )
                GLib.idle_add(
                    self.video_ms.set_text,
                    f"{(1.0/self.current_framerate * 1000):6.2f} ms",
                )
                GLib.idle_add(
                    self.video_fps.set_text, f"{self.current_framerate:6.2f} FPS"
                )
                context.move_to(
                    int(30 * scale_width), int(self.video_height - (20 * scale_height))
                )
                context.show_text(
                    f"IPS: {(1 / (inference / 1000000)):6.2f} ({(inference/1000):6.2f} ms)"
                )
                GLib.idle_add(
                    self.inference_ms.set_text,
                    f"{(inference/1000):6.2f} ms",
                )
                GLib.idle_add(
                    self.inference_ips.set_text,
                    f"{(1 / (inference / 1000000)):6.2f} IPS",
                )

            if self.first_frame:
                context.move_to(int(400 * scale_width), int(600 * scale_height))
                context.set_font_size(int(200.0 * min(scale_width, scale_height)))
                context.show_text("Loading...")
                self.first_frame = False

            context.fill()

    def prepare_overlay_cb(self, overlay, caps):
        """Store the information from the caps that we are interested in."""
        self.video_caps = caps

    def on_bus_message(self, bus, message):
        """Callback for message.

        :param bus: pipeline bus
        :param message: message from pipeline
        :return: None
        """
        if message.type == Gst.MessageType.EOS:
            logging.info("received eos message")
            self.main_loop.quit()
        elif message.type == Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            logging.warning("[error] %s : %s", error.message, debug)
            if "is not a capture device." in error.message:
                GLib.idle_add(
                    self.status_bar.set_text,
                    "Source device not compatible...\nPlease select another device!",
                )
                self.unblock_buttons(True)
            self.main_loop.quit()
        elif message.type == Gst.MessageType.WARNING:
            error, debug = message.parse_warning()
            logging.warning("[warning] %s : %s", error.message, debug)

            print("Here")
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
    main = SelfieSegmenter()
    gtk.main()
