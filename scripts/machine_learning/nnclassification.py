#!/usr/bin/env python3

"""
@file		nnstreamer_example_image_classification_tflite.py
@date		18 July 2018
@brief		Tensor stream example with filter
@see		https://github.com/nnsuite/nnstreamer
@author		Jaeyun Jung <jy1210.jung@samsung.com>
@bug		No known bugs.

NNStreamer example for image classification using tensorflow-lite.

Pipeline :
v4l2src -- tee -- textoverlay -- videoconvert -- ximagesink
            |
            --- videoscale -- tensor_converter -- tensor_filter -- tensor_sink

This app displays video sink.

'tensor_filter' for image classification.
Get model by
$ cd $NNST_ROOT/bin
$ bash get-model.sh image-classification-tflite

'tensor_sink' updates classification result to display in textoverlay.

Run example :
Before running this example, GST_PLUGIN_PATH should be updated for nnstreamer plugin.
$ export GST_PLUGIN_PATH=$GST_PLUGIN_PATH:<nnstreamer plugin path>
$ python nnstreamer_example_image_classification_tflite.py

See https://lazka.github.io/pgi-docs/#Gst-1.0 for Gst API details.

Under GNU Lesser General Public License v2.1
"""

import os
import sys
import logging
import gi

gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject

class NNStreamerExample:
    """NNStreamer example for image classification."""

    def __init__(self, device, backend, display, model, labels):
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
        self.tflite_labels = []

        if not self.tflite_init():
            raise Exception

        GObject.threads_init()
        Gst.init(None)
    # Modified: Specified camera to use and to use NPU
    def run_example(self):
        """Init pipeline and run example.

        :return: None
        """

        if self.backend == "CPU":
            backend = "false"
        elif self.backend == "GPU":
            backend = "true:gpu"
        else:
            backend = "true:npu"

        if self.display == "X11":
            display = "ximagesink name=img_tensor"
        else:
            display = "waylandsink name=img_tensor"

        # main loop
        self.loop = GObject.MainLoop()

        # init pipeline
        self.pipeline = Gst.parse_launch(
            'v4l2src name=cam_src device="' + self.device + '" ! videoconvert ! videoscale ! '
            'video/x-raw,width=640,height=480,format=RGB ! tee name=t_raw '
            't_raw. ! queue ! textoverlay name=tensor_res font-desc=Sans,24 ! '
            'videoconvert ! ' + display + ' '
            't_raw. ! queue leaky=2 max-size-buffers=2 ! videoscale ! tensor_converter ! '
            'tensor_filter framework=tensorflow-lite model=' + self.tflite_model + ' accelerator=' + backend + ' silent=FALSE ! '
            'tensor_sink name=tensor_sink'
        )

        # bus and message callback
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self.on_bus_message)

        # tensor sink signal : new data callback
        tensor_sink = self.pipeline.get_by_name('tensor_sink')
        tensor_sink.connect('new-data', self.on_new_data)

        # timer to update result
        GObject.timeout_add(500, self.on_timer_update_result)

        # start pipeline
        self.pipeline.set_state(Gst.State.PLAYING)
        self.running = True

        # set window title
        self.set_window_title('img_tensor', 'NNStreamer Example')

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
            logging.debug('[qos] format[%s] processed[%d] dropped[%d]', format_str, processed, dropped)

    def on_new_data(self, sink, buffer):
        """Callback for tensor sink signal.

        :param sink: tensor sink element
        :param buffer: buffer from element
        :return: None
        """
        if self.running:
            for idx in range(buffer.n_memory()):
                mem = buffer.peek_memory(idx)
                result, mapinfo = mem.map(Gst.MapFlags.READ)
                if result:
                    # update label index with max score
                    self.update_top_label_index(mapinfo.data, mapinfo.size)
                    mem.unmap(mapinfo)

    def on_timer_update_result(self):
        """Timer callback for textoverlay.

        :return: True to ensure the timer continues
        """
        if self.running:
            if self.current_label_index != self.new_label_index:
                # update textoverlay
                self.current_label_index = self.new_label_index
                label = self.tflite_get_label(self.current_label_index)
                textoverlay = self.pipeline.get_by_name('tensor_res')
                textoverlay.set_property('text', label)
        return True

    def set_window_title(self, name, title):
        """Set window title.

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

    
    # Modified: Changed filepath to point to model and lables on board.
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
                    self.tflite_labels.append(line)
        except FileNotFoundError:
            logging.error('cannot find tflite label [%s]', label_path)
            return False

        logging.info('finished to load labels, total [%d]', len(self.tflite_labels))
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

    def update_top_label_index(self, data, data_size):
        """Update tflite label index with max score.

        :param data: array of scores
        :param data_size: data size
        :return: None
        """
        # -1 if failed to get max score index
        self.new_label_index = -1

        if data_size == len(self.tflite_labels):
            scores = [data[i] for i in range(data_size)]
            max_score = max(scores)
            if max_score > 0:
                self.new_label_index = scores.index(max_score)
        else:
            logging.error('unexpected data size [%d]', data_size)


if __name__ == '__main__':
    example = NNStreamerExample(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5])
    example.run_example()
