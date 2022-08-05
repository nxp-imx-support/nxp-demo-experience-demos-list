#!/usr/bin/env python3

"""
Copyright Soonbeen Kim <ksb940925@gmail.com>
Copyright Jongha Jang <jangjongha.sw@gmail.com>
Copyright 2021-2022 NXP

SPDX-License-Identifier: LGPL-2.1-only
Original Source: https://github.com/nnstreamer/nnstreamer-example

This demo shows how you can use the NNStreamer to identify poses.

From the original source, this was modified to better work with the a
GUI and to get better performance on the i.MX 8M Plus.
"""

import os
import sys
import gi
import logging
import math
import numpy as np
import ctypes
import cairo

gi.require_version('Gst', '1.0')
gi.require_foreign('cairo')
from gi.repository import Gst, GObject, GLib

DEBUG = False

class NNStreamerExample:
    def __init__(
        self, platform, device, backend, model, labels, display="Weston",
        callback=None, width=1920, height=1080, r=1, g=0, b=0):
        """Creates an instance of the demo

        Arguments:
        device -- What camera or video file to use
        backend -- Whether to use NPU or CPU
        model -- the path to the model
        labels -- the path to the labels
        display -- Whether to use X11 or Weston
        callback -- Callback to pass stats to
        width -- Width of output
        height -- Height of output
        r -- Red value for labels
        g -- Green value for labels
        b -- Blue value for labels
        """
        self.loop = None
        self.pipeline = None
        self.running = False
        self.video_caps = None
        self.first_frame = True

        self.tflite_model = model
        self.label_path = labels
        self.device = device
        self.backend = backend
        self.display = display
        self.callback = callback
        self.interval_time = -1
        self.reload_time = -1
        self.r = r
        self.b = b
        self.g = g
        self.platform = platform

        self.VIDEO_WIDTH = width
        self.VIDEO_HEIGHT = height

        self.IMAGE_WIDTH = width
        self.IMAGE_HEIGHT = height

        self.MODEL_INPUT_HEIGHT = 225
        self.MODEL_INPUT_WIDTH = 225

        self.KEYPOINT_SIZE = 17
        self.OUTPUT_STRIDE = 16
        self.GRID_XSIZE = (self.MODEL_INPUT_WIDTH // self.OUTPUT_STRIDE) + 1
        self.GRID_YSIZE = (self.MODEL_INPUT_HEIGHT // self.OUTPUT_STRIDE) + 1
        self.CROP_LEFT = (self.VIDEO_WIDTH - self.IMAGE_WIDTH) // 2
        self.CROP_RIGHT = ((self.VIDEO_WIDTH - self.IMAGE_WIDTH) + 1) // 2
        self.CROP_TOP = (self.VIDEO_HEIGHT - self.IMAGE_HEIGHT) // 2
        self.CROP_BOTTOM = ((self.VIDEO_HEIGHT - self.IMAGE_HEIGHT) + 1) // 2

        self.SCORE_THRESHOLD = 0.7

        self.tflite_labels = []
        self.kps = []

        if not self.tflite_init():
            raise Exception

        GObject.threads_init()
        Gst.init(None)

    def run_example(self):
        """Starts pipeline and runs demo"""

        if self.backend == "CPU":
            backend = "true:cpu custom=NumThreads:4"
        elif self.backend == "GPU":
            os.environ["USE_GPU_INFERENCE"] = "1"
            backend = ("true:gpu custom=Delegate:External,"
                       "ExtDelegateLib:libvx_delegate.so")
        else:
            os.environ["USE_GPU_INFERENCE"] = "0"
            backend = ("true:npu custom=Delegate:External,"
                       "ExtDelegateLib:libvx_delegate.so")

        if self.display == "X11":
            display = "ximagesink name=img_tensor"
        elif self.display == "None":
            self.print_time = GLib.get_monotonic_time()
            display = "fakesink  name=img_tensor"
        else:
            display = "waylandsink sync=false name=img_tensor"

        # main loop
        self.loop = GObject.MainLoop()

        self.update_time = GLib.get_monotonic_time()
        self.old_time = GLib.get_monotonic_time()

        if self.platform == "imx8qmmek":
            decoder = "h264parse ! v4l2h264dec ! imxvideoconvert_g2d "
        else:
            decoder = "vpudec "

        if "/dev/video" in self.device:
            gst_launch_cmdline = 'v4l2src name=cam_src device=' + self.device
            gst_launch_cmdline += ' ! imxvideoconvert_g2d ! video/x-raw,width='
            gst_launch_cmdline += str(int(self.VIDEO_WIDTH)) +',height='
            gst_launch_cmdline += str(int(self.VIDEO_HEIGHT))
            gst_launch_cmdline += ',format=BGRx ! tee name=t'
        else:
            gst_launch_cmdline = 'filesrc location=' + self.device
            gst_launch_cmdline += ' ! qtdemux ! ' + decoder + '! tee name=t'

        gst_launch_cmdline += ' t. ! imxvideoconvert_g2d ! video/x-raw,'
        gst_launch_cmdline += 'width={:d},'.format(self.MODEL_INPUT_WIDTH)
        gst_launch_cmdline += 'height={:d},'.format(self.MODEL_INPUT_HEIGHT)
        gst_launch_cmdline += 'format=ARGB ! ' 
        gst_launch_cmdline += 'queue max-size-buffers=2 leaky=2 ! videoconvert'
        gst_launch_cmdline += ' ! video/x-raw,format=RGB ! tensor_converter ! '
        gst_launch_cmdline += ' tensor_filter framework=tensorflow-lite model='
        gst_launch_cmdline += self.tflite_model + ' accelerator=' + backend
        gst_launch_cmdline += ' silent=FALSE name=tensor_filter latency=1 !'
        gst_launch_cmdline += ' tensor_sink name=tensor_sink t.'
        gst_launch_cmdline += ' ! imxvideoconvert_g2d ! '
        gst_launch_cmdline += 'cairooverlay name=tensor_res ! '
        gst_launch_cmdline += 'queue max-size-buffers=2 leaky=2 ! '
        gst_launch_cmdline += display

        # init pipeline
        self.pipeline = Gst.parse_launch(gst_launch_cmdline)

        # bus and message callback
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self.on_bus_message)

        self.tensor_filter = self.pipeline.get_by_name('tensor_filter')

        # tensor sink signal : new data callback
        tensor_sink = self.pipeline.get_by_name('tensor_sink')
        tensor_sink.connect('new-data', self.new_data_cb)

        tensor_res = self.pipeline.get_by_name('tensor_res')
        tensor_res.connect('draw', self.draw_overlay_cb)
        tensor_res.connect('caps-changed', self.prepare_overlay_cb)
        if self.callback is not None:
            GObject.timeout_add(500, self.callback, self)

        # start pipeline
        self.pipeline.set_state(Gst.State.PLAYING)
        self.running = True

        self.set_window_title('img_tensor', 'Single Person Pose Estimation')

        # run main loop
        self.loop.run()

        # quit when received eos or error message
        self.running = False
        self.pipeline.set_state(Gst.State.NULL)

        bus.remove_signal_watch()

    def tflite_init(self):
        """Check tflite model and load labels.

        :return: True if successfully initialized
        """

        if not os.path.exists(self.tflite_model):
            logging.error('cannot find tflite model [%s]', self.tflite_model)
            return False

        try:
            with open(self.label_path, 'r') as label_file:
                for line in label_file.readlines():
                    self.tflite_labels.append(line)
        except FileNotFoundError:
            logging.error('cannot find tflite label [%s]', self.label_path)
            return False

        logging.info(
            'finished to load labels, total [%d]', len(self.tflite_labels))
        return True

    def new_data_cb(self, sink, buffer):
        """Callback for tensor sink signal."""
        if self.running:
            new_time = GLib.get_monotonic_time()
            self.interval_time = new_time - self.old_time
            self.old_time = new_time

            if buffer.n_memory() != 4:
                return False
            #  tensor type is float32.
            #  [0] dim of heatmap := KEY_POINT_NUMBER : height_after_stride :
            #       width_after_stride: 1
            #       (self.KEYPOINT_SIZE:self.GRID_XSIZE:self.GRID_YSIZE:1)
            #  [1] dim of offsets := self.KEYPOINT_SIZE
            #  (concat of y-axis and x-axis of offset vector) :
            #       hegiht_after_stride : width_after_stride :1
            #       (self.KEYPOINT_SIZE * 2:self.GRID_XSIZE:self.GRID_YSIZE:1)
            #  [2] dim of displacement forward
            #  (not used for single person pose estimation)
            #  [3] dim of displacement backward
            #  (not used for single person pose estimation)

            # heatmap
            mem_heatmap = buffer.peek_memory(0)
            result1, info_heatmap = mem_heatmap.map(Gst.MapFlags.READ)
            if result1:
                assert info_heatmap.size == (
                    self.KEYPOINT_SIZE * self.GRID_XSIZE *
                    self.GRID_YSIZE * 1 * 4)
                # decode bytestrings to float list
                decoded_heatmap = list(np.frombuffer(
                    info_heatmap.data, dtype=np.float32))

            # offset
            mem_offset = buffer.peek_memory(1)
            result2, info_offset = mem_offset.map(Gst.MapFlags.READ)
            if result2:
                assert info_offset.size ==  (
                    self.KEYPOINT_SIZE * 2 * self.GRID_XSIZE *
                    self.GRID_YSIZE * 1 * 4)
                # decode bytestrings to float list
                decoded_offset = list(
                    np.frombuffer(info_offset.data, dtype=np.float32))

            self.kps.clear()
            for keyPointIdx in range(0, self.KEYPOINT_SIZE):
                yPosIdx = -1
                xPosIdx = -1
                highestScore = -float("1.0842021724855044e-19")
                currentScore = 0

                # find the index of key point with highestScore in 9 X 9 grid
                for yIdx in range(0, self.GRID_YSIZE):
                    for xIdx in range(0, self.GRID_XSIZE):
                        current = decoded_heatmap[
                            (yIdx * self.GRID_YSIZE + xIdx) *
                            self.KEYPOINT_SIZE + keyPointIdx]
                        currentScore = 1.0 / (1.0 + math.exp(-current))
                        if(currentScore > highestScore):
                            yPosIdx = yIdx
                            xPosIdx = xIdx
                            highestScore = currentScore

                yOffset = decoded_offset[
                    (yPosIdx * self.GRID_YSIZE + xPosIdx) *
                    self.KEYPOINT_SIZE * 2 + keyPointIdx]
                xOffset = decoded_offset[
                    (yPosIdx * self.GRID_YSIZE + xPosIdx) *
                    self.KEYPOINT_SIZE * 2 + self.KEYPOINT_SIZE + keyPointIdx]

                yPosition = (
                    (yPosIdx / (self.GRID_YSIZE - 1)) *
                    self.MODEL_INPUT_HEIGHT + yOffset)
                xPosition = (
                    (xPosIdx / (self.GRID_XSIZE - 1)) *
                    self.MODEL_INPUT_WIDTH + xOffset)

                obj = {
                    'y': yPosition,
                    'x': xPosition,
                    'label': keyPointIdx,
                    'score': highestScore
                }

                self.kps.append(obj)

            mem_heatmap.unmap(info_heatmap)
            mem_offset.unmap(info_offset)

            if self.display == "None":
                if (GLib.get_monotonic_time() - self.print_time) > 1000000:
                    inference = self.tensor_filter.get_property("latency")
                    print(
                        "Inference time: " +
                        str(inference/1000) + " ms (" +
                        "{:5.2f}".format(1/(inference/1000000)) + " IPS)")
                    self.print_time = GLib.get_monotonic_time()

    def prepare_overlay_cb(self, overlay, caps):
        """Store the information from the caps that we are interested in."""
        self.video_caps = caps

    def draw_overlay_cb(self, overlay, context, timestamp, duration):
        """Callback to draw the overlay."""
        scale_height = self.VIDEO_HEIGHT/1080
        scale_width = self.VIDEO_WIDTH/1920
        scale_text = max(scale_height, scale_width)
        if self.first_frame:
            context.select_font_face(
                'Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
            context.set_source_rgb(self.r, self.g, self.b)
            context.move_to(int(400 * scale_width), int(600 * scale_height))
            context.set_font_size(int(200.0 * min(scale_width,scale_height)))
            context.show_text("Loading...")
            self.first_frame = False
            return

        if self.video_caps == None or not self.running:
            return

        # mutex_lock alternative required
        kpts = self.kps
        # mutex_unlock alternative needed

        context.select_font_face(
            'Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        context.set_font_size(35.0)

        # draw body lines
        context.set_source_rgb(self.r, self.g, self.b)
        context.set_line_width(15)

        self.draw_line(overlay, context, kpts, 5, 6)
        self.draw_line(overlay, context, kpts, 5, 7)
        self.draw_line(overlay, context, kpts, 7, 9)
        self.draw_line(overlay, context, kpts, 6, 8)
        self.draw_line(overlay, context, kpts, 8, 10)
        self.draw_line(overlay, context, kpts, 6, 12)
        self.draw_line(overlay, context, kpts, 5, 11)
        self.draw_line(overlay, context, kpts, 11, 13)
        self.draw_line(overlay, context, kpts, 13, 15)
        self.draw_line(overlay, context, kpts, 12, 11)
        self.draw_line(overlay, context, kpts, 12, 14)
        self.draw_line(overlay, context, kpts, 14, 16)

        context.stroke()

    def draw_line(self, overlay, context, kpts, from_key, to_key):
        """Connects pose points"""
        kpts_len = len(kpts)
        if from_key > kpts_len-1 or to_key > kpts_len-1:
            return
        if kpts[from_key]['score'] < self.SCORE_THRESHOLD or (
            kpts[to_key]['score'] < self.SCORE_THRESHOLD):
            return

        context.move_to(
            kpts[from_key]['x'] * self.IMAGE_WIDTH / self.MODEL_INPUT_WIDTH,
            kpts[from_key]['y'] * self.IMAGE_HEIGHT / self.MODEL_INPUT_HEIGHT)
        context.line_to(
            kpts[to_key]['x'] * self.IMAGE_WIDTH / self.MODEL_INPUT_WIDTH,
            kpts[to_key]['y'] * self.IMAGE_HEIGHT / self.MODEL_INPUT_HEIGHT)

    def on_bus_message(self, bus, message):
        """Callback for message.
        :param bus: pipeline bus
        :param message: message from pipeline
        :return: None
        """
        if message.type == Gst.MessageType.EOS:
            logging.info('received eos message')
            self.loop.quit()
        elif message.type == Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            logging.warning('[error] %s : %s', error.message, debug)
            self.loop.quit()
        elif message.type == Gst.MessageType.WARNING:
            error, debug = message.parse_warning()
            logging.warning('[warning] %s : %s', error.message, debug)
        elif message.type == Gst.MessageType.STREAM_START:
            logging.info('received start message')
        elif message.type == Gst.MessageType.QOS:
            data_format, processed, dropped = message.parse_qos_stats()
            format_str = Gst.Format.get_name(data_format)
            logging.debug(
                '[qos] format[%s] processed[%d] dropped[%d]',
                format_str, processed, dropped)

    def set_window_title(self, name, title):
        """Set window title.
        :param name: GstXImageasink element name
        :param title: window title
        :return: None
        """
        element = self.pipeline.get_by_name(name)
        if element is not None:
            pad = element.get_static_pad('sink')
            if pad is not None:
                tags = Gst.TagList.new_empty()
                tags.add_value(Gst.TagMergeMode.APPEND, 'title', title)
                pad.send_event(Gst.Event.new_tag(tags))

if __name__ == '__main__':
    if(len(sys.argv) != 7 and len(sys.argv) != 5 and len(sys.argv) != 6):
        print("Usage: python3 nnpose.py <dev/video*/video file> <NPU/CPU>"+
                " <model file> <label file>")
        exit()
    # Get platform
    platform = os.uname().nodename
    if(len(sys.argv) == 7):
        example = NNStreamerExample(platform, sys.argv[1],sys.argv[2],sys.argv[3],
            sys.argv[4],sys.argv[5],sys.argv[6])
    if(len(sys.argv) == 5):
        example = NNStreamerExample(platform, sys.argv[1],sys.argv[2],sys.argv[3],
            sys.argv[4])
    if(len(sys.argv) == 6):
        example = NNStreamerExample(platform, sys.argv[1],sys.argv[2],sys.argv[3],
            sys.argv[4], sys.argv[5])
    example.run_example()

