#!/usr/bin/env python3

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
    """NNStreamer example for Object Detection."""

    def __init__(self, device, backend, display, model, labels, callback):
        self.loop = None
        self.pipeline = None
        self.running = False
        self.video_caps = None

        self.BOX_SIZE = 4
        self.LABEL_SIZE = 91
        self.DETECTION_MAX = 20
        self.MAX_OBJECT_DETECTION = 10

        self.Y_SCALE = 10.0
        self.X_SCALE = 10.0
        self.H_SCALE = 5.0
        self.W_SCALE = 5.0

        self.VIDEO_WIDTH = 640
        self.VIDEO_HEIGHT = 360
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

        if not self.tflite_init():
            raise Exception

        GObject.threads_init()
        Gst.init(None)

    def run(self):
        """Init pipeline and run example.
        :return: None
        """

        print("Run: NNStreamer example for object detection.")

        if self.backend == "CPU":
            backend = "true:CPU"
        elif self.backend == "GPU":
            backend = "true:gpu custom=Delegate:GPU"
        else:
            backend = "true:npu custom=Delegate:NNAPI"

        if self.display == "X11":
            display = "ximagesink name=img_tensor "
        else:
            display = "waylandsink name=img_tensor "

        # main loop
        self.loop = GObject.MainLoop()
        self.oldtime = GLib.get_monotonic_time()
        self.updateTime = GLib.get_monotonic_time()

        gst_launch_cmdline = ' v4l2src device="' + self.device  + '" ! imxvideoconvert_g2d !'
        gst_launch_cmdline += '  video/x-raw,width={:d},height={:d} ! tee name=t '.format(self.VIDEO_WIDTH, self.VIDEO_HEIGHT)
        gst_launch_cmdline += ' t. ! queue name=thread-nn max-size-buffers=2 leaky=2 !'
        gst_launch_cmdline += '  imxvideoconvert_g2d !'
        gst_launch_cmdline += '  video/x-raw,width={:d},height={:d},format=RGBA !'.format(self.MODEL_WIDTH, self.MODEL_HEIGHT)
        gst_launch_cmdline += '  videoconvert ! video/x-raw,format=RGB !'
        gst_launch_cmdline += '  tensor_converter !'
        gst_launch_cmdline += '  tensor_filter framework=tensorflow2-lite model=' + self.tflite_model  + ' accelerator=' + backend + ' silent=FALSE ! '
        gst_launch_cmdline += '  tensor_sink name=tensor_sink'
        gst_launch_cmdline += ' t. ! queue name=thread-img max-size-buffers=2 !'
        gst_launch_cmdline += '  videoconvert ! cairooverlay name=tensor_res ! ' + display
        print(gst_launch_cmdline)
        self.pipeline = Gst.parse_launch(gst_launch_cmdline);

        # bus and message callback
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self.on_bus_message)

        # tensor sink signal : new data callback
        tensor_sink = self.pipeline.get_by_name('tensor_sink')
        tensor_sink.connect('new-data', self.new_data_cb)

        tensor_res = self.pipeline.get_by_name('tensor_res')
        tensor_res.connect('draw', self.draw_overlay_cb)
        tensor_res.connect('caps-changed', self.prepare_overlay_cb)

        # start pipeline
        self.pipeline.set_state(Gst.State.PLAYING)
        self.running = True

        self.set_window_title('img_tensor', 'NNStreamer Object Detection Example')

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
            logging.error('cannot find tflite model [%s]', self.tflite_model)
            return False

        label_path = self.label_path
        try:
            with open(label_path, 'r') as label_file:
                for line in label_file.readlines():
                    while str(len(self.tflite_labels)) not in line:
                        self.tflite_labels.append("Invalid")
                    self.tflite_labels.append(line)
        except FileNotFoundError:
            logging.error('cannot find tflite label [%s]', label_path)
            return False

        logging.info('finished to load labels, total [%d]', len(self.tflite_labels))
        return True

    # @brief Callback for tensor sink signal.
    def new_data_cb(self, sink, buffer):
        if self.running:
            newtime = GLib.get_monotonic_time()
            self.intime = newtime - self.oldtime
            self.oldtime = newtime
            interTime = (GLib.get_monotonic_time() - self.updateTime)/1000000
            if interTime > 1:
                self.callback(self.intime)
                self.updateTime = GLib.get_monotonic_time()

            if buffer.n_memory() != 4:
                return False

            #  tensor type is float32.
            # LOCATIONS_IDX:CLASSES_IDX:SCORES_IDX:NUM_DETECTION_IDX
            # 4:20:1:1\,20:1:1:1\,20:1:1:1\,1:1:1:1
            # [0] detection_boxes (default 4th tensor). BOX_SIZE : #MaxDetection, ANY-TYPE¬
            # [1] detection_classes (default 2nd tensor). #MaxDetection, ANY-TYPE¬
            # [2] detection_scores (default 3rd tensor). #MaxDetection, ANY-TYPE¬
            # [3] num_detection (default 1st tensor). 1, ANY-TYPE¬

            # bytestrings that are based on float32 must be decoded into float list.

            # boxes
            mem_boxes = buffer.peek_memory(0)
            ret, info_boxes = mem_boxes.map(Gst.MapFlags.READ)
            if ret:
                assert info_boxes.size == self.BOX_SIZE * self.DETECTION_MAX * 4, "Invalid info_box size"
                decoded_boxes = list(np.frombuffer(info_boxes.data, dtype=np.float32))  # decode bytestrings to float list

            # detections
            mem_detections = buffer.peek_memory(1)
            ret, info_detections = mem_detections.map(Gst.MapFlags.READ)
            if ret:
                assert info_detections.size == self.DETECTION_MAX * 4, "Invalid info_detection size"
                decoded_detections = list(np.frombuffer(info_detections.data, dtype=np.float32)) # decode bytestrings to float list

            # scores
            mem_scores = buffer.peek_memory(2)
            ret, info_scores = mem_scores.map(Gst.MapFlags.READ)
            if ret:
                assert info_scores.size == self.DETECTION_MAX * 4, "Invalid info_score size"
                decoded_scores = list(np.frombuffer(info_scores.data, dtype=np.float32)) # decode bytestrings to float list

            # num detection
            mem_num = buffer.peek_memory(3)
            ret, info_num = mem_num.map(Gst.MapFlags.READ)
            if ret:
                assert info_num.size == 4, "Invalid info_num size"
                decoded_num = list(np.frombuffer(info_num.data, dtype=np.float32)) # decode bytestrings to float list

            self.get_detected_objects(decoded_boxes, decoded_detections, decoded_scores, int(decoded_num[0]))

            mem_boxes.unmap(info_boxes)
            mem_detections.unmap(info_detections)
            mem_scores.unmap(info_scores)
            mem_num.unmap(info_num)


    def get_detected_objects(self, boxes, detections, scores, num):
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
                print("LABEL           : {}".format(self.tflite_labels[d["class_id"]]))
                print("x               : {}".format(d["x"]))
                print("y               : {}".format(d["y"]))
                print("width           : {}".format(d["width"]))
                print("height          : {}".format(d["height"]))
                print("Confidence Score: {}".format(d["prob"]))

    # @brief Store the information from the caps that we are interested in.
    def prepare_overlay_cb(self, overlay, caps):
        self.video_caps = caps

    # @brief Callback to draw the overlay.
    def draw_overlay_cb(self, overlay, context, timestamp, duration):
        if self.video_caps == None or not self.running:
            return

        # mutex_lock alternative required
        detected = self.detected_objects
        # mutex_unlock alternative needed

        drawed = 0
        context.select_font_face('Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        context.set_font_size(20.0)

        for obj in detected:
            label = self.tflite_labels[obj['class_id']][:-1]
            x = obj['x'] * self.VIDEO_WIDTH // self.MODEL_WIDTH
            y = obj['y'] * self.VIDEO_HEIGHT // self.MODEL_HEIGHT
            width = obj['width'] * self.VIDEO_WIDTH // self.MODEL_WIDTH
            height = obj['height'] * self.VIDEO_HEIGHT // self.MODEL_HEIGHT

            # draw rectangle
            context.rectangle(x, y, width, height)
            context.set_source_rgb(1, 0, 0)
            context.set_line_width(1.5)
            context.stroke()
            context.fill_preserve()

            # draw title
            context.move_to(x + 5, y + 25)
            context.text_path(label)
            context.set_source_rgb(1, 0, 0)
            context.fill_preserve()
            context.set_source_rgb(1, 1, 1)
            context.set_line_width(0.3)
            context.stroke()
            context.fill_preserve()

            drawed += 1
            if drawed >= self.MAX_OBJECT_DETECTION:
                break

    def on_bus_message(self, bus, message):
        """
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
            logging.debug('[qos] format[%s] processed[%d] dropped[%d]', format_str, processed, dropped)


    def set_window_title(self, name, title):
        """
        Set window title.
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
    example = ObjectDetection(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5])
    example.run()

