#!/usr/bin/env python3

"""
Copyright Jaeyun Jung <jy1210.jung@samsung.com>
Copyright 2021-2022 NXP

SPDX-License-Identifier: LGPL-2.1-only
Original Source: https://github.com/nnstreamer/nnstreamer-example

This demo shows how you can use the NNStreamer to identify brands.

From the original source, this was modified to better work with the a
GUI and to get better performance on the i.MX 8M Plus.
"""

import os
import sys
import logging
import gi
import cairo

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject, GLib

class NNStreamerExample:
    """The class that manages the demo"""
    def __init__(self, platform, device, backend,
        model, labels, display="Weston", callback=None, width=1920,
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
        self.current_label_index = -1
        self.new_label_index = -1
        self.tflite_model = model
        self.label_path = labels
        self.device = device
        self.backend = backend
        self.display = display
        self.callback = callback
        self.tflite_labels = []
        self.VIDEO_WIDTH = width
        self.VIDEO_HEIGHT = height
        self.label = "Loading..."
        self.first_frame = True
        self.refresh_time = -1
        self.r = r
        self.b = b
        self.g = g
        self.platform = platform

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
            display = "fakesink"
        else:
            display = "waylandsink sync=false name=img_tensor"

        self.past_time = GLib.get_monotonic_time()
        self.interval_time = -1
        self.label_time = GLib.get_monotonic_time()

        if self.platform == "imx8qmmek":
            decoder = "h264parse ! v4l2h264dec ! imxvideoconvert_g2d "
        else:
            decoder = "vpudec "

        if "/dev/video" in self.device:
            pipeline = 'v4l2src name=cam_src device=' + self.device
            pipeline += ' ! imxvideoconvert_g2d ! video/x-raw,width='
            pipeline += str(int(self.VIDEO_WIDTH)) +',height='
            pipeline += str(int(self.VIDEO_HEIGHT))
            pipeline += ',format=BGRx ! tee name=t_raw'
        else:
            pipeline = 'filesrc location=' + self.device  + ' ! qtdemux'
            pipeline += ' ! ' + decoder + '! tee name=t_raw'
        # main loop
        self.loop = GObject.MainLoop()
        pipeline += ' t_raw. ! imxvideoconvert_g2d ! cairooverlay '
        pipeline += 'name=tensor_res ! '
        pipeline += 'queue max-size-buffers=2 leaky=2 ! '
        pipeline += display + ' t_raw. ! '
        pipeline += 'imxvideoconvert_g2d ! '
        pipeline += 'video/x-raw,width=224,height=224,format=RGBA ! '
        pipeline += 'queue max-size-buffers=2 leaky=2 ! '
        pipeline += 'videoconvert ! video/x-raw,format=RGB ! '
        pipeline += 'tensor_converter ! '
        pipeline += 'tensor_filter name=tensor_filter framework='
        pipeline += 'tensorflow-lite model=' + self.tflite_model
        pipeline +=  ' accelerator=' + backend
        pipeline += ' silent=FALSE latency=1 ! tensor_sink name=tensor_sink'

        # init pipeline
        self.pipeline = Gst.parse_launch(pipeline)

        # bus and message callback
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self.on_bus_message)

        self.tensor_filter = self.pipeline.get_by_name('tensor_filter')

        # tensor sink signal : new data callback
        tensor_sink = self.pipeline.get_by_name('tensor_sink')
        tensor_sink.connect('new-data', self.on_new_data)

        self.reload_time = GLib.get_monotonic_time()
        tensor_res = self.pipeline.get_by_name('tensor_res')
        tensor_res.connect('draw', self.draw_overlay_cb)
        tensor_res.connect('caps-changed', self.prepare_overlay_cb)

        # start pipeline
        self.pipeline.set_state(Gst.State.PLAYING)
        self.running = True

        self.data = -1
        self.data_size = -1
        if self.callback is not None:
            GObject.timeout_add(500, self.callback, self)

        GObject.timeout_add(250, self.update_top_label_index)

        # set window title
        self.set_window_title('img_tensor', 'NNStreamer Classification')

        # run main loop
        self.loop.run()

        # quit when received eos or error message
        self.running = False
        self.pipeline.set_state(Gst.State.NULL)

        bus.remove_signal_watch()

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
            logging.debug('[qos] format[%s] processed[%d] dropped[%d]',
                format_str, processed, dropped)

    def on_new_data(self, sink, buffer):
        """Callback for tensor sink signal.

        :param sink: tensor sink element
        :param buffer: buffer from element
        :return: None
        """
        if self.running:
            new_time = GLib.get_monotonic_time()
            self.interval_time = new_time - self.past_time
            self.past_time = new_time

            for idx in range(buffer.n_memory()):
                mem = buffer.peek_memory(idx)
                result, mapinfo = mem.map(Gst.MapFlags.READ)
                if result:
                    # update label index with max score
                    self.data = mapinfo.data
                    self.data_size = mapinfo.size
                    mem.unmap(mapinfo)
            
            if self.display == "None":
                if (GLib.get_monotonic_time() - self.print_time) > 1000000:
                    inference = self.tensor_filter.get_property("latency")
                    print(
                        "Item: " + self.label + " Inference time: " +
                        str(inference/1000) + " ms (" +
                        "{:5.2f}".format(1/(inference/1000000)) + " IPS)")
                    self.print_time = GLib.get_monotonic_time()


    def set_window_title(self, name, title):
        """Set window title if using X11.

        :param name: GstXImageSink element name
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

    
    def tflite_init(self):
        """Check tflite model and load labels.

        :return: True if successfully initialized
        """

        # check model file exists
        if not os.path.exists(self.tflite_model):
            logging.error('cannot find tflite model [%s]', self.tflite_model)
            return False

        # load labels
        label_path = self.label_path
        try:
            with open(label_path, 'r') as label_file:
                for line in label_file.readlines():
                    self.tflite_labels.append(line[line.find(',')+1:])
        except FileNotFoundError:
            logging.error('cannot find tflite label [%s]', label_path)
            return False
        del self.tflite_labels[0]

        logging.info(
            'finished to load labels, total [%d]', len(self.tflite_labels))
        return True

    def tflite_get_label(self, index):
        """Get label string with given index.

        :param index: index for label
        :return: label string
        """
        try:
            label = self.tflite_labels[index]
        except IndexError:
            label = ''
        return label

    def update_top_label_index(self):
        """Update tflite label index with max score.

        :param data: array of scores
        :param data_size: data size
        :return: None
        """
        # -1 if failed to get max score index
        self.new_label_index = -1
        if self.data_size == -1:
            return True
        if self.data_size == len(self.tflite_labels):
            scores = [self.data[i] for i in range(self.data_size)]
            max_score = max(scores)
            if max_score > 0:
                self.new_label_index = scores.index(max_score)
                self.label = self.tflite_get_label(self.new_label_index)[:-1]
            
        else:
            logging.error('unexpected data size [%d]', self.data_size)
        return True

    def draw_overlay_cb(self, overlay, context, timestamp, duration):
        """Draws the results onto the video frame"""
        scale_height = self.VIDEO_HEIGHT/1080
        scale_width = self.VIDEO_WIDTH/1920
        scale_text = max(scale_height, scale_width)
        inference = self.tensor_filter.get_property("latency")
        context.select_font_face(
            'Sans', cairo.FONT_SLANT_NORMAL,
            cairo.FONT_WEIGHT_BOLD)
        context.set_source_rgb(self.r, self.g, self.b)
        
        context.set_font_size(int(25.0 * scale_text))
        context.move_to(
            int(50 * scale_width),
            int(self.VIDEO_HEIGHT-(100*scale_height)))
        context.show_text("i.MX NNStreamer Brand Demo")
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
        context.move_to(int(50 * scale_width), int(100 * scale_height))
        context.set_font_size(int(30.0 * scale_text))
        context.show_text(self.label)
        if(self.first_frame):
            context.move_to(int(400 * scale_width), int(600 * scale_height))
            context.set_font_size(int(200.0 * min(scale_width,scale_height)))
            context.show_text("Loading...")
            self.first_frame = False
        context.set_operator(cairo.Operator.SOURCE)

    def prepare_overlay_cb(self, overlay, caps):
        self.video_caps = caps

if __name__ == '__main__':
    if(
        len(sys.argv) != 7 and len(sys.argv) != 5
        and len(sys.argv) != 9 and len(sys.argv) != 12
        and len(sys.argv) != 6):
        print("Usage: python3 nnbrand.py </dev/video*/video file> <NPU/CPU>"+
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
    if(len(sys.argv) == 9):
        example = NNStreamerExample(platform, sys.argv[1],sys.argv[2],sys.argv[3],
            sys.argv[4],sys.argv[5],sys.argv[6],sys.argv[7],sys.argv[8])
    if(len(sys.argv) == 12):
        example = NNStreamerExample(platform, sys.argv[1],sys.argv[2],sys.argv[3],
            sys.argv[4],sys.argv[5],sys.argv[6],sys.argv[7],sys.argv[8],
            sys.argv[9],sys.argv[10],sys.argv[11])
    example.run_example()
