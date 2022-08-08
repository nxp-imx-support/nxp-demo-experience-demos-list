#!/usr/bin/env python3

"""
Copyright SSAFY Team 1 <jangjongha.sw@gmail.com>
Copyright 2021-2022 NXP

SPDX-License-Identifier: LGPL-2.1-only
Original Source: https://github.com/nnstreamer/nnstreamer-example

This demo shows how you can use the NNStreamer to detect objects.

From the original source, this was modified to better work with the a
GUI and to get better performance on the i.MX 8M Plus.
"""

import os
import sys
import gi
import logging
import math
import numpy as np
import cairo

gi.require_version('Gst', '1.0')
gi.require_foreign('cairo')
from gi.repository import Gst, GObject, GLib

DEBUG = False

class ObjectDetection:
    """The class that manages the demo"""
    def __init__(
        self, platform, device, backend, model, labels,
        display="Weston", callback=None, width=1920,
        height=1080, r=1, g=0, b=0):
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

        self.BOX_SIZE = 4
        self.LABEL_SIZE = 91
        self.DETECTION_MAX = 20
        self.MAX_OBJECT_DETECTION = 20

        self.Y_SCALE = 10.0
        self.X_SCALE = 10.0
        self.H_SCALE = 5.0
        self.W_SCALE = 5.0

        self.VIDEO_WIDTH = width
        self.VIDEO_HEIGHT = height
        self.MODEL_WIDTH = 300
        self.MODEL_HEIGHT = 300

        self.tflite_model = model
        self.label_path = labels
        self.device = device
        self.backend = backend
        self.display = display
        self.tflite_labels = []
        self.detected_objects = []
        self.callback = callback
        self.r = r
        self.b = b
        self.g = g
        self.platform = platform

        if not self.tflite_init():
            raise Exception
        GObject.threads_init()
        Gst.init(None)

    def run(self):
        """Starts pipeline and run demo"""

        if self.backend == "CPU":
            backend = "true:CPU custom=NumThreads:4"
        elif self.backend == "GPU":
            os.environ["USE_GPU_INFERENCE"] = "1"
            backend = ("true:gpu custom=Delegate:External,"
                       "ExtDelegateLib:libvx_delegate.so")
        else:
            os.environ["USE_GPU_INFERENCE"] = "0"
            backend = ("true:npu custom=Delegate:External,"
                       "ExtDelegateLib:libvx_delegate.so")

        if self.display == "X11":
            display = "ximagesink name=img_tensor "
        elif self.display == "None":
            self.print_time = GLib.get_monotonic_time()
            display = "fakesink "
        else:
            display = "waylandsink sync=false name=img_tensor "

        # main loop
        self.loop = GObject.MainLoop()
        self.old_time = GLib.get_monotonic_time()
        self.update_time = GLib.get_monotonic_time()
        self.reload_time = -1
        self.interval_time = 999999

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

        gst_launch_cmdline += ' t. ! imxvideoconvert_g2d !  video/x-raw,'
        gst_launch_cmdline += 'width={:d},'.format(self.MODEL_WIDTH)
        gst_launch_cmdline += 'height={:d},'.format(self.MODEL_HEIGHT)
        gst_launch_cmdline += 'format=ARGB ! imxvideoconvert_g2d ! '
        gst_launch_cmdline += 'queue max-size-buffers=2 leaky=2 ! '
        gst_launch_cmdline += 'videoconvert ! video/x-raw,format=RGB !'
        gst_launch_cmdline += ' tensor_converter ! tensor_filter'
        gst_launch_cmdline += ' framework=tensorflow2-lite model='
        gst_launch_cmdline += self.tflite_model +' accelerator=' + backend
        gst_launch_cmdline += ' silent=FALSE name=tensor_filter latency=1 ! '
        gst_launch_cmdline += 'tensor_sink name=tensor_sink t. ! '
        gst_launch_cmdline += ' imxvideoconvert_g2d !'
        gst_launch_cmdline += ' cairooverlay name=tensor_res ! '
        gst_launch_cmdline += 'queue max-size-buffers=2 leaky=2 ! '
        gst_launch_cmdline += display

        self.pipeline = Gst.parse_launch(gst_launch_cmdline)

        # bus and message callback
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self.on_bus_message)

        self.tensor_filter = self.pipeline.get_by_name('tensor_filter')

        # tensor sink signal : new data callback

        tensor_filter = self.pipeline.get_by_name('tensor_filter')

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

        self.set_window_title(
            'img_tensor', 'NNStreamer Object Detection Example')

        # run main loop
        self.loop.run()

        # quit when received eos or error message
        self.running = False
        self.pipeline.set_state(Gst.State.NULL)

        bus.remove_signal_watch()

    def tflite_init(self):
        """
        :return: True if successfully initialized
        """

        if not os.path.exists(self.tflite_model):
            logging.error(
                'cannot find tflite model [%s]', self.tflite_model)
            return False

        label_path = self.label_path
        try:
            with open(label_path, 'r') as label_file:
                for line in label_file.readlines():
                    if line[0].isdigit():
                        while str(len(self.tflite_labels)) not in line:
                            self.tflite_labels.append("Invalid")
                        self.tflite_labels.append(line[line.find(' ')+1:])
                    else:
                        self.tflite_labels.append(line)
        except FileNotFoundError:
            logging.error('cannot find tflite label [%s]', label_path)
            return False

        logging.info(
            'finished to load labels, total [%d]', len(self.tflite_labels))
        return True

    # @brief Callback for tensor sink signal.
    def new_data_cb(self, sink, buffer):
        """Callback for tensor sink signal.

        :param sink: tensor sink element
        :param buffer: buffer from element
        :return: None
        """
        if self.running:
            new_time = GLib.get_monotonic_time()
            self.interval_time = new_time - self.old_time
            self.old_time = new_time
            if buffer.n_memory() != 4:
                return False

            #  tensor type is float32.
            # LOCATIONS_IDX:CLASSES_IDX:SCORES_IDX:NUM_DETECTION_IDX
            # 4:20:1:1\,20:1:1:1\,20:1:1:1\,1:1:1:1
            # [0] detection_boxes (default 4th tensor). BOX_SIZE :
            # #MaxDetection, ANY-TYPE
            # [1] detection_classes (default 2nd tensor).
            # #MaxDetection, ANY-TYPE
            # [2] detection_scores (default 3rd tensor)
            # #MaxDetection, ANY-TYPE
            # [3] num_detection (default 1st tensor). 1, ANY-TYPE

            # bytestrings that are based on float32 must be
            # decoded into float list.

            # boxes
            mem_boxes = buffer.peek_memory(0)
            ret, info_boxes = mem_boxes.map(Gst.MapFlags.READ)
            if ret:
                assert info_boxes.size == (
                    self.BOX_SIZE * self.DETECTION_MAX
                    * 4),"Invalid info_box size"
                decoded_boxes = list(
                    np.frombuffer(info_boxes.data,
                    dtype=np.float32))  # decode bytestrings to float list

            # detections
            mem_detections = buffer.peek_memory(1)
            ret, info_detections = mem_detections.map(Gst.MapFlags.READ)
            if ret:
                assert info_detections.size == (
                    self.DETECTION_MAX * 4), "Invalid info_detection size"
                decoded_detections = list(np.frombuffer(
                    info_detections.data,
                    dtype=np.float32)) # decode bytestrings to float list

            # scores
            mem_scores = buffer.peek_memory(2)
            ret, info_scores = mem_scores.map(Gst.MapFlags.READ)
            if ret:
                assert info_scores.size == (
                    self.DETECTION_MAX * 4), "Invalid info_score size"
                decoded_scores = list(np.frombuffer(
                    info_scores.data,
                    dtype=np.float32)) # decode bytestrings to float list

            # num detection
            mem_num = buffer.peek_memory(3)
            ret, info_num = mem_num.map(Gst.MapFlags.READ)
            if ret:
                assert info_num.size == 4, "Invalid info_num size"
                decoded_num = list(np.frombuffer(
                    info_num.data,
                    dtype=np.float32)) # decode bytestrings to float list

            self.get_detected_objects(
                decoded_boxes, decoded_detections, decoded_scores,
                int(decoded_num[0]))

            mem_boxes.unmap(info_boxes)
            mem_detections.unmap(info_detections)
            mem_scores.unmap(info_scores)
            mem_num.unmap(info_num)

            if self.display == "None":
                if (GLib.get_monotonic_time() - self.print_time) > 1000000:
                    inference = self.tensor_filter.get_property("latency")
                    print("Inference time: " + str(inference/1000) + " ms (" + "{:5.2f}".format(1/(inference/1000000)) + " IPS)")
                    self.print_time = GLib.get_monotonic_time()


    def get_detected_objects(self, boxes, detections, scores, num):
        """Pairs boxes with dectected objects"""
        threshold_score = 0.5
        detected = list()

        for i in range(num):
            score = scores[i]
            if score < threshold_score:
                continue

            c = detections[i]

            box_offset = self.BOX_SIZE * i
            ymin = boxes[box_offset + 0]
            xmin = boxes[box_offset + 1]
            ymax = boxes[box_offset + 2]
            xmax = boxes[box_offset + 3]

            x = xmin * self.MODEL_WIDTH
            y = ymin * self.MODEL_HEIGHT
            width = (xmax - xmin) * self.MODEL_WIDTH
            height = (ymax - ymin) * self.MODEL_HEIGHT

            obj = {
                'class_id': int(c),
                'x': x,
                'y': y,
                'width': width,
                'height': height,
                'prob': score
            }

            detected.append(obj)

        # update result
        self.detected_objects.clear()

        for d in detected:
            self.detected_objects.append(d)
            if DEBUG:
                print("==============================")
                print("LABEL           : {}".format(
                    self.tflite_labels[d["class_id"]]))
                print("x               : {}".format(d["x"]))
                print("y               : {}".format(d["y"]))
                print("width           : {}".format(d["width"]))
                print("height          : {}".format(d["height"]))
                print("Confidence Score: {}".format(d["prob"]))

    def prepare_overlay_cb(self, overlay, caps):
        """Store the information from the caps that we are interested in."""
        self.video_caps = caps

    def draw_overlay_cb(self, overlay, context, timestamp, duration):
        """Callback to draw the overlay."""
        if self.video_caps == None or not self.running:
            return
        scale_height = self.VIDEO_HEIGHT/1080
        scale_width = self.VIDEO_WIDTH/1920
        scale_text = max(scale_height, scale_width)

        # mutex_lock alternative required
        detected = self.detected_objects
        # mutex_unlock alternative needed

        drawed = 0
        context.select_font_face(
            'Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        context.set_font_size(int(50.0 * scale_text))
        context.set_source_rgb(self.r, self.g, self.b)

        for obj in detected:
            label = self.tflite_labels[obj['class_id']][:-1]
            x = obj['x'] * self.VIDEO_WIDTH // self.MODEL_WIDTH
            y = obj['y'] * self.VIDEO_HEIGHT // self.MODEL_HEIGHT
            width = obj['width'] * self.VIDEO_WIDTH // self.MODEL_WIDTH
            height = obj['height'] * self.VIDEO_HEIGHT // self.MODEL_HEIGHT

            # draw rectangle
            context.rectangle(x, y, width, height)
            context.set_line_width(3)
            context.stroke()

            # draw title
            context.move_to(x + 5, y + int(50.0 * scale_text))
            context.show_text(label)

            drawed += 1
            if drawed >= self.MAX_OBJECT_DETECTION:
                break

        inference = self.tensor_filter.get_property("latency")
        context.set_font_size(int(25.0 * scale_text))
        context.move_to(
            int(50 * scale_width),
            int(self.VIDEO_HEIGHT-(100*scale_height)))
        context.show_text("i.MX NNStreamer Detection Demo")
        if inference == 0:
            context.move_to(
                int(50 * scale_width),
                int(self.VIDEO_HEIGHT-(75*scale_height)))
            context.show_text("FPS: ")
            context.move_to(
                int(50 * scale_width),
                int(self.VIDEO_HEIGHT-(50*scale_height)))
            context.show_text("IPS: ")
        elif (
            (GLib.get_monotonic_time() - self.reload_time) < 100000
            and self.refresh_time != -1):
            context.move_to(
                int(50 * scale_width),
                int(self.VIDEO_HEIGHT-(75*scale_height)))
            context.show_text(
                "FPS: " + "{:12.2f}".format(1/(self.refresh_time/1000000)) +
                " (" + str(self.refresh_time/1000) + " ms)")
            context.move_to(
                int(50 * scale_width),
                int(self.VIDEO_HEIGHT-(50*scale_height)))
            context.show_text(
                "IPS: " + "{:12.2f}".format(1/(self.inference/1000000)) +
                " (" + str(self.inference/1000) + " ms)")
        else:
            self.reload_time = GLib.get_monotonic_time()
            self.refresh_time = self.interval_time
            self.inference = self.tensor_filter.get_property("latency")
            context.move_to(
                int(50 * scale_width),
                int(self.VIDEO_HEIGHT-(75*scale_height)))
            context.show_text(
                "FPS: " + "{:12.2f}".format(1/(self.refresh_time/1000000)) +
                " (" + str(self.refresh_time/1000) + " ms)")
            context.move_to(
                int(50 * scale_width),
                int(self.VIDEO_HEIGHT-(50*scale_height)))
            context.show_text(
                "IPS: " + "{:12.2f}".format(1/(self.inference/1000000)) +
                " (" + str(self.inference/1000) + " ms)")
        if(self.first_frame):
            context.move_to(int(400 * scale_width), int(600 * scale_height))
            context.set_font_size(int(200.0 * min(scale_width,scale_height)))
            context.show_text("Loading...")
            self.first_frame = False
        context.fill()


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
        """Set window title for X11.

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
    if(
        len(sys.argv) != 7 and len(sys.argv) != 5
        and len(sys.argv) != 9 and len(sys.argv) != 12 and len(sys.argv) != 6):
        print(
            "Usage: python3 nndetection.py <dev/video*/video file>" +
            " <NPU/CPU> <model file> <label file>")
        exit()
    # Get platform
    platform = os.uname().nodename
    if(len(sys.argv) == 7):
        example = ObjectDetection(platform, sys.argv[1],sys.argv[2],sys.argv[3],
            sys.argv[4],sys.argv[5],sys.argv[6])
    if(len(sys.argv) == 5):
        example = ObjectDetection(platform, sys.argv[1],sys.argv[2],sys.argv[3],
            sys.argv[4])
    if(len(sys.argv) == 6):
        example = ObjectDetection(platform, sys.argv[1],sys.argv[2],sys.argv[3],
            sys.argv[4], sys.argv[5])
    if(len(sys.argv) == 9):
        example = ObjectDetection(platform, sys.argv[1],sys.argv[2],sys.argv[3],
            sys.argv[4],sys.argv[5],sys.argv[6],sys.argv[7],sys.argv[8])
    if(len(sys.argv) == 12):
        example = ObjectDetection(platform, sys.argv[1],sys.argv[2],sys.argv[3],
            sys.argv[4],sys.argv[5],sys.argv[6],sys.argv[7],sys.argv[8],
            sys.argv[9],sys.argv[10],sys.argv[11])
    example.run()

