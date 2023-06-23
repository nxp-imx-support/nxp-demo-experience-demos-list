#!/usr/bin/env python3

"""
Copyright Jaeyun Jung <jy1210.jung@samsung.com>
Copyright 2023 NXP

SPDX-License-Identifier: LGPL-2.1-only
Original Source: https://github.com/nnstreamer/nnstreamer-example

Model: MediaPipe's Selfie Segmenter
Model licensed under Apache-2.0 License

Original model available at: https://developers.google.com/mediapipe/solutions/vision/image_segmenter
Model Card: https://storage.googleapis.com/mediapipe-assets/Model%20Card%20MediaPipe%20Selfie%20Segmentation.pdf
This model was created by: Tingbo Hou, Google; Siargey Pisarchyk, Google; Karthik Raveendran, Google.

This script shows human segmentation from video. Application could be aimed at video conference.
MediaPipe's Selfie Segmenter model was quantized to be accelerated by the NPU on the i.MX8M Plus EVK.
"""

import gi
import os
import sys
import logging
import cairo
import numpy as np

from PIL import Image
from gi.repository import Gst, GLib, GObject

gi.require_version("Gst", "1.0")
gi.require_foreign("cairo")


class SelfieSegmenter:
    """The class that manages the Selfie Segmenter demo"""

    def __init__(
        self,
        platform,
        device,
        backend,
        model,
        background,
        callback=None,
        demo_mode=0,
        r=1,
        g=0,
        b=0,
    ):
        """Creates an instance of the demo

        Arguments:
        device     -- What camera or video file to use
        backend    -- Whether to use NPU or CPU
        model      -- Path to the *.tflite model
        background -- Path to the background image
        callback   -- Callback to pass stats to
        demo_mode  -- Which demo mode to run
        r          -- Red value for text
        g          -- Green value for text
        b          -- Blue value for text
        """

        self.main_loop = None
        self.pipeline = None
        self.video_caps = None
        self.running = False
        self.first_frame = True

        self.platform = platform
        self.tflite_model = model
        self.backend = backend
        self.device = device
        self.callback = callback
        self.demo_mode = demo_mode
        self.r = r
        self.b = b
        self.g = g

        self.condition_frame = np.full((256, 256, 3), fill_value=0, dtype=np.uint8)
        self.frame = np.full((480, 480, 3), fill_value=0, dtype=np.uint8)
        self.segmentation = np.full((480, 480, 3), fill_value=0, dtype=np.uint8)
        self.background_path = background
        self.background = Image.open(self.background_path)
        self.number_frames = 0

        self.VIDEO_WIDTH = 480
        self.VIDEO_HEIGHT = 480
        self.MODEL_WIDTH = 256
        self.MODEL_HEIGHT = 256
        self.THRESHOLD = 0.1

        if not self.tflite_init():
            raise Exception

        Gst.init()

    def on_need_data(self, src, length):
        """Function to send output to GStreamer pipeline using appsrc

        :param src: appsink element
        :param length: --
        :return: None
        """

        if self.running:
            new_time = GLib.get_monotonic_time()
            self.interval_time = new_time - self.old_time
            self.old_time = new_time

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
                (self.VIDEO_WIDTH, self.VIDEO_HEIGHT, 3),
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
                    (self.MODEL_WIDTH, self.MODEL_HEIGHT, 1)
                )

                # Interpret segmentation
                condition = decoded_mask > self.THRESHOLD
                self.condition_frame[:, :, 0] = condition[:, :, 0]
                self.condition_frame[:, :, 1] = condition[:, :, 0]
                self.condition_frame[:, :, 2] = condition[:, :, 0]

                output = Image.fromarray(np.uint8(self.condition_frame))
                output = output.resize((self.VIDEO_WIDTH, self.VIDEO_HEIGHT), 0)

                self.segmentation = np.where(
                    np.asarray(output, dtype=np.uint8),
                    self.frame,
                    np.asarray(self.background, dtype=np.uint8),
                )
            mask_mem.unmap(mask)

    def draw_cb(self, overlay, context, timestamp, duration):
        """Callback to draw text overlay"""

        if self.video_caps is None or not self.running:
            return

        if self.demo_mode == 1:
            new_time = GLib.get_monotonic_time()
            self.interval_time = new_time - self.old_time
            self.old_time = new_time

        scale_height = self.VIDEO_HEIGHT / 1080
        scale_width = self.VIDEO_WIDTH / 1920
        scale_text = max(scale_height, scale_width)

        context.select_font_face(
            "Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD
        )
        context.set_source_rgb(self.r, self.g, self.b)
        context.set_font_size(int(30.0 * scale_text))
        context.move_to(int(30 * scale_width), int(20))
        context.show_text("i.MX NNStreamer - Selfie Segmenter Demo")

        inference = self.tensor_filter.get_property("latency")
        if inference == 0:
            context.move_to(
                int(30 * scale_width), int(self.VIDEO_HEIGHT - (50 * scale_height))
            )
            context.show_text("FPS: ")
            context.move_to(
                int(30 * scale_width), int(self.VIDEO_HEIGHT - (25 * scale_height))
            )
            context.show_text("IPS: ")
        elif (
            GLib.get_monotonic_time() - self.reload_time
        ) < 100000 and self.refresh_time != -1:
            context.move_to(
                int(30 * scale_width), int(self.VIDEO_HEIGHT - (50 * scale_height))
            )
            if self.demo_mode == 0:
                context.show_text(
                    "FPS: "
                    + "{:12.2f}".format(1 / (self.refresh_time / 1000000))
                    + " ("
                    + str(self.refresh_time / 1000)
                    + " ms)"
                )
            context.move_to(
                int(30 * scale_width), int(self.VIDEO_HEIGHT - (25 * scale_height))
            )
            context.show_text(
                "IPS: "
                + "{:12.2f}".format(1 / (self.inference / 1000000))
                + " ("
                + str(self.inference / 1000)
                + " ms)"
            )
        else:
            self.reload_time = GLib.get_monotonic_time()
            self.refresh_time = self.interval_time
            self.inference = self.tensor_filter.get_property("latency")
            context.move_to(
                int(30 * scale_width), int(self.VIDEO_HEIGHT - (50 * scale_height))
            )
            if self.demo_mode == 0:
                context.show_text(
                    "FPS: "
                    + "{:12.2f}".format(1 / (self.refresh_time / 1000000))
                    + " ("
                    + str(self.refresh_time / 1000)
                    + " ms)"
                )
            context.move_to(
                int(30 * scale_width), int(self.VIDEO_HEIGHT - (25 * scale_height))
            )
            context.show_text(
                "IPS: "
                + "{:12.2f}".format(1 / (self.inference / 1000000))
                + " ("
                + str(self.inference / 1000)
                + " ms)"
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

    def run(self):
        """Starts pipeline and run demo"""

        if self.backend == "CPU":
            backend = "true:CPU custom=NumThreads:4"
        else:
            os.environ["USE_GPU_INFERENCE"] = "0"
            backend = (
                "true:npu custom=Delegate:External," "ExtDelegateLib:libvx_delegate.so"
            )

        self.main_loop = GLib.MainLoop()
        self.old_time = GLib.get_monotonic_time()
        self.update_time = GLib.get_monotonic_time()
        self.reload_time = -1
        self.interval_time = 999999

        # Pipeline for background subtraction
        if self.demo_mode == 0:
            # Define camera source pipeline
            gst_launch_cmdline = "v4l2src device=" + self.device
            gst_launch_cmdline += (
                " ! video/x-raw,width=640,height=480,framerate=30/1 ! "
            )
            gst_launch_cmdline += "aspectratiocrop aspect-ratio=1/1 ! "
            gst_launch_cmdline += "imxvideoconvert_g2d rotation=horizontal-flip ! "
            gst_launch_cmdline += (
                "imxvideoconvert_g2d ! video/x-raw,width="
                + str(self.VIDEO_WIDTH)
                + ",height="
                + str(self.VIDEO_HEIGHT)
            )

            # ML processing using tensor_filter
            gst_launch_cmdline += (
                " ! tee name=t t. ! queue max-size-buffers=2 leaky=2 ! "
            )
            gst_launch_cmdline += (
                "imxvideoconvert_g2d ! video/x-raw,width="
                + str(self.MODEL_WIDTH)
                + ",height="
                + str(self.MODEL_HEIGHT)
            )
            gst_launch_cmdline += " ! videoconvert ! video/x-raw,format=RGB ! "
            gst_launch_cmdline += "tensor_converter ! "
            gst_launch_cmdline += (
                "tensor_transform mode=arithmetic option=typecast:float32,div:255.0 ! "
            )
            gst_launch_cmdline += (
                "tensor_filter framework=tensorflow-lite model=" + self.tflite_model
            )
            gst_launch_cmdline += " accelerator=" + backend
            gst_launch_cmdline += " silent=FALSE name=tensor_filter latency=1 ! "
            gst_launch_cmdline += "tensor_sink name=tensor_sink "

            # Appsinik, sends the frame to be processed outside of pipeline
            gst_launch_cmdline += "t. ! queue max-size-buffers=2 ! videoconvert ! video/x-raw,format=RGB ! "
            gst_launch_cmdline += "appsink name=frame_sink emit-signals=True "

            # Appsrc, gets the output with background substitution
            gst_launch_cmdline += "appsrc name=result_src is-live=true block=true format=GST_FORMAT_TIME ! "
            gst_launch_cmdline += (
                "video/x-raw,format=RGB,framerate=30/1 ! videoconvert "
            )
            gst_launch_cmdline += (
                "! video/x-raw,width="
                + str(self.VIDEO_WIDTH)
                + ",height="
                + str(self.VIDEO_HEIGHT)
            )
            gst_launch_cmdline += " ! cairooverlay name=cairo_text ! "
            gst_launch_cmdline += "queue max-size-buffers=2 ! "
            gst_launch_cmdline += "waylandsink sync=false"

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
                "imxcompositor_g2d latency=150000000 min-upstream-latency=150000000 "
            )
            gst_launch_cmdline += "name=comp sink_1::ypos=0 "
            gst_launch_cmdline += "sink_0::ypos=0 sink_0::xpos=480 ! "
            gst_launch_cmdline += "cairooverlay name=cairo_text ! "
            gst_launch_cmdline += "waylandsink sync=false "

            # Define camera source pipeline
            gst_launch_cmdline += "v4l2src device=" + self.device
            gst_launch_cmdline += (
                " ! video/x-raw,width=640,height=480,framerate=30/1 ! "
            )
            gst_launch_cmdline += "aspectratiocrop aspect-ratio=1/1 ! "
            gst_launch_cmdline += "imxvideoconvert_g2d rotation=horizontal-flip ! "
            gst_launch_cmdline += (
                "imxvideoconvert_g2d ! video/x-raw,width="
                + str(self.VIDEO_WIDTH)
                + ",height="
                + str(self.VIDEO_HEIGHT)
            )
            # ML processing using tensor_filter

            gst_launch_cmdline += (
                " ! tee name=t t. ! queue max-size-buffers=2 leaky=2 ! "
            )
            gst_launch_cmdline += (
                "imxvideoconvert_g2d ! video/x-raw,width="
                + str(self.MODEL_WIDTH)
                + ",height="
                + str(self.MODEL_HEIGHT)
            )
            gst_launch_cmdline += " ! videoconvert ! video/x-raw,format=RGB ! "
            gst_launch_cmdline += "tensor_converter ! "
            gst_launch_cmdline += (
                "tensor_transform mode=arithmetic option=typecast:float32,div:255.0 ! "
            )
            gst_launch_cmdline += (
                "tensor_filter framework=tensorflow-lite model=" + self.tflite_model
            )
            gst_launch_cmdline += " accelerator=" + backend
            gst_launch_cmdline += " name=tensor_filter latency=1 ! "
            gst_launch_cmdline += (
                "tensor_decoder mode=image_segment option1=snpe-depth option2=0 ! "
            )
            gst_launch_cmdline += (
                "imxvideoconvert_g2d ! video/x-raw,width="
                + str(self.VIDEO_WIDTH)
                + ",height="
                + str(self.VIDEO_HEIGHT)
                + ",format=RGBA"
            )
            gst_launch_cmdline += " ! comp.sink_0 "

            # Send input frame to compositor
            gst_launch_cmdline += "t. ! queue max-size-buffers=2 leaky=2 ! "
            gst_launch_cmdline += "comp.sink_1 "

            self.pipeline = Gst.parse_launch(gst_launch_cmdline)

        self.tensor_filter = self.pipeline.get_by_name("tensor_filter")

        # Draws text information to display
        cairo_draw = self.pipeline.get_by_name("cairo_text")
        cairo_draw.connect("draw", self.draw_cb)
        cairo_draw.connect("caps-changed", self.prepare_overlay_cb)

        # Timer to update result
        if self.callback is not None:
            GLib.timeout_add(500, self.callback, self)

        # Bus and message callback
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self.on_bus_message)

        # Start pipeline
        self.running = True
        self.pipeline.set_state(Gst.State.PLAYING)
        self.set_window_title("selfie-segmenter", "Selfie Segmenter Demo")

        self.main_loop.run()

        # Ends pipeline
        self.running = False
        self.pipeline.set_state(Gst.State.NULL)
        bus.remove_signal_watch()

    def tflite_init(self):
        """Check tflite model and load background image.

        :return: True if successfully initialized
        """

        # Check model file exists
        if not os.path.exists(self.tflite_model):
            logging.error("cannot find tflite model [%s]", self.tflite_model)
            return False

        # Check background image exists
        if not os.path.exists(self.background_path):
            logging.error("cannot find background image [%s]", self.background_path)
            return False
        return True

    def set_window_title(self, name, title):
        """Set window title.

        :param name: GstXImageasink element name
        :param title: window title
        :return: None
        """
        element = self.pipeline.get_by_name(name)
        if element is not None:
            pad = element.get_static_pad("sink")
            if pad is not None:
                tags = Gst.TagList.new_empty()
                tags.add_value(Gst.TagMergeMode.APPEND, "title", title)
                pad.send_event(Gst.Event.new_tag(tags))


if __name__ == "__main__":
    if len(sys.argv) != 9:
        print(
            "Usage: python3 selfie_segmenter.py <dev/video*/video file>"
            + " <NPU/CPU> <model file> <background file>"
        )
        exit()

    # Get platform
    platform = os.uname().nodename

    if len(sys.argv) == 9:
        demo = SelfieSegmenter(
            platform,
            sys.argv[1],
            sys.argv[2],
            sys.argv[3],
            sys.argv[4],
            sys.argv[5],
            int(sys.argv[6]),
            int(sys.argv[7]),
            int(sys.argv[8]),
            int(sys.argv[9]),
        )
        demo.run()
