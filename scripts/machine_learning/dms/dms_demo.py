"""
Copyright 2022 NXP

SPDX-License-Identifier: Apache-2.0

The following demo shows how to create a video pipeline
with GStreamer and detects if the user is distracted or
not present.
"""

import cairo
import gi
import cv2
import time
import numpy as np
import os
import tflite_runtime.interpreter as tflite
import math
import glob
import sys

from face_detection import YoloFace
from eye import Eye
from mouth import Mouth

gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gst, Gio, GLib, Gdk

sys.path.append("/home/root/.nxp-demo-experience/scripts/")
import utils

FACE_MODEL = ""

LANDMARK_MODEL = ""

VIDEO = "/dev/video0"
''' Camera to use '''

FRAME_WIDTH = 1280
''' Width of incoming video '''

FRAME_HEIGHT = 720
''' Height of incoming video '''

BAD_FACE_PENALTY = 0.01
''' % to remove for far away face '''

NO_FACE_PENALTY = 0.01
''' % to remove for no faces in frame '''

YAWN_PENALTY = 0.02
''' % to remove for yawning '''

DISTRACT_PENALTY = 0.02
''' % to remove for looking away '''

SLEEP_PENALTY = 0.03
''' % to remove for sleeping '''

RESTORE_CREDIT = -0.01
''' % to restore for doing everything right '''

FACE_THRESHOLD = 0.7
''' The threshold value for face detection '''

LEFT_EYE_THRESHOLD = 50
''' if the left_eye ratio is greater then this value, then left eye will be
    considered as open, otherwise be considered as closed. '''

RIGHT_EYE_THRESHOLD = 50
""" if the right_eye ratio is greater then this value, then right eye will be
    considered as open, otherwise be considered as closed. """

MOUTH_THRESHOLD = 0.4
""" if the mouth ratio is greater then this value, then mouth will be
    considered as open, otherwise be considered as closed. """

FACING_LEFT_THRESHOLD = 0.5
""" if the mouth_face_ratio is less then this value then face will be
    considered as turning left """

FACING_RIGHT_THRESHOLD = 2
""" if the mouth_face_ratio is greater then this value, then face will be
    considered as turning right"""

LEFT_W = 3

RIGHT_W = 3

LEFT_EYE_STATUS = np.zeros(LEFT_W)
""" To filter status glitch, 0 means closed, 1 means open """

RIGHT_EYE_STATUS = np.zeros(RIGHT_W)
""" to filter status glitch, 0 means closed, 1 means open """

class MLVideoDemo(Gtk.Window):
    """A class that contains the UI and camera elements."""

    def __init__(self):
        """Create the UI and start the video feed."""

        # Class variables
        super().__init__()
        self.face_cords = []
        self.marks = []
        self.attention = True
        self.sleep = True
        self.yawn = True
        self.sample = None

        # Window Set-up
        self.setup_inference()
        self.set_default_size(300+FRAME_WIDTH, FRAME_HEIGHT)
        self.set_resizable(False)

        self.overall_status = Gtk.Label.new("")
        self.overall_status.set_markup(
            "<span size=\"x-large\" foreground=\"darkgreen\">Driver is OK" +
            "</span>")

        self.attention_bar = Gtk.LevelBar.new()
        self.attention_bar.set_value(0.0)
        self.attention_bar.set_size_request(300, 30)
        css = b'''
                levelbar block.low {
                    background-color: #00FF00;
                }

                levelbar block.high {
                    background-color: #FFFF00;
                }

                levelbar block.full {
                    background-color: #FF0000;
                }
        '''
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(css)
        context = Gtk.StyleContext()
        screen = Gdk.Screen.get_default()
        context.add_provider_for_screen(
            screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        div = Gtk.Separator.new(Gtk.Orientation(0))

        attention_label = Gtk.Label.new("Attention: ")
        attention_label.set_markup("<span size=\"large\">Attention: </span>")
        self.attention_status = Gtk.Label.new("OK")
        self.attention_status.set_markup(
            "<span size=\"large\" foreground=\"darkgreen\">OK</span>")

        sleep_label = Gtk.Label.new("Drowsy: ")
        sleep_label.set_markup("<span size=\"large\">Drowsy: </span>")
        self.sleep_status = Gtk.Label.new("OK")
        self.sleep_status.set_markup(
            "<span size=\"large\" foreground=\"darkgreen\">OK</span>")

        yawn_label = Gtk.Label.new("Yawn: ")
        yawn_label.set_markup("<span size=\"large\">Yawn: </span>")
        self.yawn_status = Gtk.Label.new("OK")
        self.yawn_status.set_markup(
            "<span size=\"large\" foreground=\"darkgreen\">OK</span>")

        sep = Gtk.Label.new(" ")
        sep.set_size_request(300, 350)

        #self.fps_label = Gtk.Label.new("N/A IPS for Face Detection")
        #self.ips_label = Gtk.Label.new("N/A IPS for Mask Detection")

        # Create a custom header
        header = Gtk.HeaderBar()
        header.set_title("Driver Monitoring System Demo")
        header.set_subtitle("i.MX 93 Demos")
        self.set_titlebar(header)

        # Button to quit
        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="application-exit-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        header.pack_end(quit_button)
        quit_button.connect("clicked", Gtk.main_quit)

        # Settings button
        settings_button = Gtk.Button()
        settings_icon = Gio.ThemedIcon(name="applications-system-symbolic")
        settings_image = Gtk.Image.new_from_gicon(
            settings_icon, Gtk.IconSize.BUTTON)
        settings_button.add(settings_image)
        header.pack_start(settings_button)
        self.settings = SettingsWindow()
        settings_button.connect("clicked", self.open_settings)

        # Area to display video
        self.draw_area = Gtk.DrawingArea.new()
        self.draw_area.set_hexpand(True)
        self.draw_area.set_size_request(FRAME_WIDTH, FRAME_HEIGHT)

        # Tell GTK what function to use to draw
        self.draw_area.connect("draw", self.draw_cb)

        # Add video and label to window
        main_grid = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        side_grid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        side_grid.set_margin_start(30)
        side_grid.set_margin_end(30)
        side_grid.set_margin_top(30)
        side_grid.set_margin_bottom(30)
        attention_grid = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        sleep_grid = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        yawn_grid = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)


        side_grid.pack_start(self.overall_status, False, True, 0)
        side_grid.pack_start(self.attention_bar, False, True, 0)
        side_grid.pack_start(div, False, True, 0)

        side_grid.pack_start(attention_grid, True, True, 0)
        attention_grid.pack_start(attention_label, True, True, 0)
        attention_grid.pack_start(self.attention_status, True, True, 0)

        side_grid.pack_start(sleep_grid, True, True, 0)
        sleep_grid.pack_start(sleep_label, True, True, 0)
        sleep_grid.pack_start(self.sleep_status, True, True, 0)

        side_grid.pack_start(yawn_grid, True, True, 0)
        yawn_grid.pack_start(yawn_label, True, True, 0)
        yawn_grid.pack_start(self.yawn_status, True, True, 0)

        side_grid.pack_start(sleep_label, False, True, 0)
        side_grid.pack_start(yawn_label, False, True, 0)
        side_grid.pack_start(sep, True, True, 0)
        #side_grid.pack_start(self.ips_label, False, True, 0)
        #side_grid.pack_start(self.fps_label, False, True, 0)

        main_grid.pack_start(side_grid, True, True, 0)
        main_grid.pack_start(self.draw_area, True, True, 0)
        self.add(main_grid)

        # GStreamer pipeline to use. Note that the format is in RGB16. I'm
        # not sure if this is the only format that can be used, but it seems
        # the most straight forward
        cam_pipeline = (
            "v4l2src device=" + VIDEO + " ! imxvideoconvert_pxp " +
            " ! video/x-raw,format=RGB16,width=" + str(int(FRAME_WIDTH)) +
            ",height=" + str(int(FRAME_HEIGHT)) + "! " +
            "tee name=t t. ! queue max-size-buffers=2 leaky=2 ! " +
            "appsink emit-signals=true name=sink t. ! queue " +
            "max-size-buffers=2 leaky=2 ! videoconvert ! " +
            "video/x-raw,format=RGB ! appsink " +
            "emit-signals=true name=sink2")
        self.refresh_clock = time.perf_counter()

        # Parse the above pipeline
        self.pipeline = Gst.parse_launch(cam_pipeline)

        # Set a callback function to get the frame
        tensor_sink = self.pipeline.get_by_name('sink')
        tensor_sink2 = self.pipeline.get_by_name('sink2')
        tensor_sink.connect('new-sample', self.on_new_data)
        tensor_sink2.connect('new-sample', self.on_new_data2)

        # Run the pipeline
        self.frame_count = 0
        self.timer = time.perf_counter()
        self.pipeline.set_state(Gst.State.PLAYING)

    def setup_inference(self):
        """Sets up inference"""
        self.tflite_labels = []
        os.system("echo 4 > /proc/sys/kernel/printk")
        self.detector = YoloFace(FACE_MODEL, FACE_THRESHOLD)
        self.eye = Eye()
        self.mouth = Mouth()

        # Restore the model.
        self.interpreter = tflite.Interpreter(model_path=LANDMARK_MODEL)
        self.interpreter.allocate_tensors()
        self.input_index = self.interpreter.get_input_details()[0]['index']
        self.input_shape = self.interpreter.get_input_details()[0]['shape']
        self.face_landmarks = self.interpreter.get_output_details()[0]['index']
        self.face_scores = self.interpreter.get_output_details()[1]['index']


    def on_new_data(self, element):
        """Get the new frame and signal a redraw."""
        # Get the new frame and save it
        self.sample = element.emit('pull-sample')
        # Notify the draw area to redraw itself
        self.draw_area.queue_draw()
        return 0

    def on_new_data2(self, element):
        """Get the new frame and Run inference."""
        vision_time = time.monotonic()
        self.sample2 = element.emit('pull-sample')
        if self.sample2 is None:
            return
        # Get frame details
        buffer = self.sample2.get_buffer()
        caps = self.sample2.get_caps()
        ret, mem_buf = buffer.map(Gst.MapFlags.READ)
        height = caps.get_structure(0).get_value("height")
        width = caps.get_structure(0).get_value("width")
        frame_org = np.ndarray(
            shape=(height,width,3), dtype=np.uint8, buffer=mem_buf.data)
        frame = frame_org[...,::-1].copy()
        boxes = self.detector.detect(frame)
        self.face_cords = []
        if np.size(boxes,0) > 0:
            for i in range(np.size(boxes,0)):
                boxes[i][[0,2]] *= FRAME_WIDTH
                boxes[i][[1,3]] *= FRAME_HEIGHT

            # Transform the boxes into squares.
            boxes = self.transform_to_square(boxes, scale=1.26, offset=(0, 0.0))

            # Clip the boxes if they cross the image boundaries.
            boxes, _ = self.clip_boxes(boxes, (0, 0, FRAME_WIDTH, FRAME_HEIGHT))
            boxes = boxes.astype(np.int32)

            # only do landmark for one face closest to the center
            face_in_center = 0
            distance_to_center = math.hypot(FRAME_WIDTH / 2, FRAME_HEIGHT / 2)
            for i in range(np.size(boxes,0)):
                x1, y1, x2, y2 = boxes[i]
                #print(x1, y1, x2, y2)
                mid_to_center = math.hypot(
                    (x2 + x1 - FRAME_WIDTH) / 2, (y2 + y1 - FRAME_HEIGHT) / 2)
                #print(i, mid_to_center)
                if mid_to_center < distance_to_center:
                    face_in_center = i
                    distance_to_center = mid_to_center

            #print(face_in_center)
            x1, y1, x2, y2 = boxes[face_in_center]
            self.face_cords.append([x1, y1, x2, y2])

            # Preprocess it.
            face_image = frame[y1:y2, x1:x2]
            face_image = cv2.resize(face_image, (192, 192))
            face_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)

            # Do prediction.
            face = np.expand_dims(face_image, 0)
            face = 2 * ((face / 255.0) - 0.5).astype('float32')
            # print(face)
            
            # input quantization
            # face = face / 0.01865844801068306 - 14
            # face = face.astype(np.int8)

            self.interpreter.set_tensor(self.input_index, face)
            self.interpreter.invoke()
            self.landmarks = self.interpreter.get_tensor(self.face_landmarks)[0]
            self.face_flag_socres = self.interpreter.get_tensor(self.face_scores)[0]

            
            # output dequantization
            self.landmarks = self.landmarks.astype(np.float32)
            self.landmarks = np.reshape(self.landmarks, (468, 3))

            facebox = boxes[face_in_center]
            mark_group = []
            left, top, right, bottom = facebox
            width = height = (bottom - top)
            #print(width)

            face_landmark_x = self.landmarks[:, 0:1] / 192.0
            face_landmark_y = self.landmarks[:, 1:2] / 192.0

            marks = []
            for i in range(0, face_landmark_x.shape[0]):
                x = int(face_landmark_x[i] * width)
                y = int(face_landmark_y[i] * height)
                marks.append((x, y))

            marks = np.array(marks)
            # print(marks)

            #marks, heatmap_grid = parse_heatmaps(heatmap, (width, height))

            # Convert the marks locations from local CNN to global image.
            marks[:, 0] += left
            marks[:, 1] += top
            mark_group.append(marks)

            self.marks = mark_group

            # process landmarks for eyes
            left_eye_ratio = self.eye.blinking_ratio(frame, marks, 0)
            right_eye_ratio = self.eye.blinking_ratio(frame, marks, 1)
            #print(left_eye_ratio, right_eye_ratio)

            # average the left eye status in a window of LEFT_W frames
            for i in range(LEFT_W - 1):
                LEFT_EYE_STATUS[i] = LEFT_EYE_STATUS[i+1]

            if left_eye_ratio > LEFT_EYE_THRESHOLD:
                LEFT_EYE_STATUS[LEFT_W - 1] = 1
            else:
                LEFT_EYE_STATUS[LEFT_W - 1] = 0

            # average the right eye status in a window of RIGHT_W frames
            for i in range(RIGHT_W - 1):
                RIGHT_EYE_STATUS[i] = RIGHT_EYE_STATUS[i+1]

            if right_eye_ratio > RIGHT_EYE_THRESHOLD:
                RIGHT_EYE_STATUS[RIGHT_W - 1] = 1
            else:
                RIGHT_EYE_STATUS[RIGHT_W - 1] = 0
            
            if (np.mean(LEFT_EYE_STATUS) < 0.5 and
                np.mean(RIGHT_EYE_STATUS) < 0.5):
                self.sleep = False
            else:
                self.sleep = True
            
            mouth_ratio = self.mouth.yawning_ratio(marks)
            #print(mouth_ratio)
            if mouth_ratio > MOUTH_THRESHOLD:
                self.yawn = False
            else:
                self.yawn = True
            
            mouth_face_ratio = self.mouth.mouth_face_ratio(marks)
            if (mouth_face_ratio < FACING_LEFT_THRESHOLD or
                mouth_face_ratio > FACING_RIGHT_THRESHOLD):
                self.attention = False
            else:
                self.attention = True
        else:
            self.face_cords = []
        buffer.unmap(mem_buf)
        #GLib.idle_add(
        # self.fps_label.set_text, "Vision FPS: " +
        # str(round((time.monotonic() - vision_time)*1000,2)))
        return 0

    def draw_cb(self, widget, context):
        """Draw the frame in the GUI."""
        # Protect against empty frames at the beginning
        # Draw a black background if there is nothing
        #video_time = time.monotonic()
        if self.sample is None:
            context.set_source_rgb(0,0,0)
            context.paint()
            return
        # Get frame details
        buffer = self.sample.get_buffer()
        caps = self.sample.get_caps()
        ret, mem_buf = buffer.map(Gst.MapFlags.READ)
        height = caps.get_structure(0).get_value("height")
        width = caps.get_structure(0).get_value("width")

        # While GStreamer provides a buffer, it is read only even if write
        # flags are set above. Cairo requires the buffer to be writable so the
        # two cannot interface with each other. The workaround is to use Numpy
        # to create a writable copy of the buffer.
        frame = np.ndarray(
            shape=(height,width), dtype=np.uint16, buffer=mem_buf.data)
        frame = frame.copy()
        surface = cairo.ImageSurface.create_for_data(
            frame, cairo.Format.RGB16_565, width, height)
        context.set_source_surface(surface)
        context.paint()
        context.set_source_rgb(255, 0, 0)
        face_in_center = -1
        distance_to_center = math.hypot(FRAME_WIDTH / 2, FRAME_HEIGHT / 2)
        ok = True
        if(len(self.face_cords) != 0):
            for face in self.face_cords:
                if((face[2]-face[0]) < 250):
                    context.set_source_rgb(255, 0, 0)
                    GLib.idle_add(self.change_meter, BAD_FACE_PENALTY)
                    ok = False
                else:
                    context.set_source_rgb(0, 255, 0)
                context.rectangle(
                    face[0], face[1], (face[2]-face[0]), (face[3]-face[1]))
                context.stroke()
            for m in self.marks:
                for mark in m:
                    point = (tuple(mark.astype(int)))
                    context.arc(point[0],point[1],1,0,1)
                    context.stroke()
            GLib.idle_add(self.update_status, True)
        else:
            GLib.idle_add(self.update_status, False)
        # Clean up
        buffer.unmap(mem_buf)
        #GLib.idle_add(self.fps_label.set_text, "Video FPS: " +
        # str(round(1/(time.monotonic() - video_time),2)))

    def update_status(self, face_here):
        """Update the current status"""
        if(face_here):
            ok = True
            if(self.attention):
                self.attention_status.set_markup(
                    "<span size=\"large\" foreground=\"darkgreen\">OK</span>")
            else:
                self.attention_status.set_markup(
                    "<span size=\"large\" foreground=\"#340808\">"
                    "Distracted!</span>")
                self.change_meter(DISTRACT_PENALTY)
                ok = False

            if(self.sleep):
                self.sleep_status.set_markup(
                    "<span size=\"large\" foreground=\"darkgreen\">OK</span>")
            else:
                self.sleep_status.set_markup(
                    "<span size=\"large\" foreground=\"#340808\">"
                    "Detected!</span>")
                self.change_meter(SLEEP_PENALTY)
                ok = False

            if(self.yawn):
                self.yawn_status.set_markup(
                    "<span size=\"large\" foreground=\"darkgreen\">OK</span>")
            else:
                self.yawn_status.set_markup(
                    "<span size=\"large\" foreground=\"#340808\">"
                    "Detected!</span>")
                self.change_meter(YAWN_PENALTY)
                ok = False
            if(ok):
                self.change_meter(RESTORE_CREDIT)
        else:
            self.attention_status.set_markup(
                "<span size=\"large\" foreground=\"black\">Unknown</span>")
            self.sleep_status.set_markup(
                "<span size=\"large\" foreground=\"black\">Unknown</span>")
            self.yawn_status.set_markup(
                "<span size=\"large\" foreground=\"black\">Unknown</span>")
            self.change_meter(NO_FACE_PENALTY)
        
    def change_meter(self, change):
        """Change the meter"""
        cur_val = self.attention_bar.get_value()
        new_val = cur_val + change
        if(new_val > 1.0):
            new_val = 1.0
        if (new_val < 0.0):
            new_val = 0.0
        self.attention_bar.set_value(new_val)
        if new_val < 0.25:
            self.overall_status.set_markup(
                "<span size=\"x-large\" foreground=\"darkgreen\">"
                "Driver is OK</span>")
        if new_val >= 0.25 and new_val <= 0.75:
            self.overall_status.set_markup(
                "<span size=\"x-large\" foreground=\"#7f802d\">"
                "Warning!</span>")
        if new_val > 0.75:
            self.overall_status.set_markup(
                "<span size=\"x-large\" foreground=\"#340808\">Danger!</span>")
    
    def transform_to_square(self, boxes, scale=1.0, offset=(0, 0)):
        """Get the square bounding boxes.

        Args:
            boxes: input boxes [[xmin, ymin, xmax, ymax], ...]
            scale: ratio to scale the boxes
            offset: a tuple of offset ratio to move the boxes (x, y)

        Returns:
            boxes: square boxes.
        """
        xmins, ymins, xmaxs, ymaxs = np.split(boxes, 4, 1)
        width = xmaxs - xmins
        height = ymaxs - ymins

        # How much to move.
        offset_x = offset[0] * width
        offset_y = offset[1] * height

        # Where is the center location.
        center_x = np.floor_divide(xmins + xmaxs, 2) + offset_x
        center_y = np.floor_divide(ymins + ymaxs, 2) + offset_y

        # Make them squares.
        margin = np.floor_divide(np.maximum(height, width) * scale, 2)
        boxes = np.concatenate((center_x-margin, center_y-margin,
                                center_x+margin, center_y+margin), axis=1)

        return boxes

    def clip_boxes(self, boxes, margins):
        """Clip the boxes to the safe margins.

        Args:
            boxes: input boxes [[xmin, ymin, xmax, ymax], ...].
            margins: a tuple of 4 int (left, top, right, bottom)
            as safe margins.

        Returns:
            boxes: clipped boxes.
            clip_mark: the mark of clipped sides, like [[True,
            False, False, False], ...]
        """
        left, top, right, bottom = margins

        clip_mark = (boxes[:, 1] < top, boxes[:, 0] < left,
                    boxes[:, 3] > bottom, boxes[:, 2] > right)

        boxes[:, 1] = np.maximum(boxes[:, 1], top)
        boxes[:, 0] = np.maximum(boxes[:, 0], left)
        boxes[:, 3] = np.minimum(boxes[:, 3], bottom)
        boxes[:, 2] = np.minimum(boxes[:, 2], right)

        return boxes, clip_mark

    def draw_marks(self, image, marks):
        """Draw the dots on face"""
        for m in marks:
            for mark in m:
                cv2.circle(image, tuple(mark.astype(int)), 2, (0, 255, 0), -1)

    def open_settings(self, unused):
         GLib.idle_add(self.settings.show_all)

class SettingsWindow(Gtk.Window):
    """A class that contains the UI and camera elements."""

    def __init__(self):
        """Create the UI for settings."""
        super().__init__()
        self.set_default_size(300, 100)
        self.set_resizable(False)

        header = Gtk.HeaderBar()
        header.set_title("Settings")
        header.set_subtitle("Driver Monitoring System Demo")
        self.set_titlebar(header)

        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="application-exit-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        header.pack_end(quit_button)
        quit_button.connect("clicked", self.close_window)

        bad_label = Gtk.Label.new("Penalty for far face: ")
        no_label = Gtk.Label.new("Penalty for no face: ")
        attention_label = Gtk.Label.new("Penalty for being distracted: ")
        sleepy_label = Gtk.Label.new("Penalty for drowsiness: ")
        yawn_label = Gtk.Label.new("Penalty for yawning: ")
        restore_label = Gtk.Label.new("Healing rate: ")

        self.bad_spin = Gtk.SpinButton.new_with_range(0.00, 1.00, 0.01)
        self.bad_spin.set_value(BAD_FACE_PENALTY)
        self.no_spin = Gtk.SpinButton.new_with_range(0.00, 1.00, 0.01)
        self.no_spin.set_value(NO_FACE_PENALTY)
        self.attention_spin = Gtk.SpinButton.new_with_range(0.00, 1.00, 0.01)
        self.attention_spin.set_value(DISTRACT_PENALTY)
        self.sleepy_spin = Gtk.SpinButton.new_with_range(0.00, 1.00, 0.01)
        self.sleepy_spin.set_value(SLEEP_PENALTY)
        self.yawn_spin = Gtk.SpinButton.new_with_range(0.00, 1.00, 0.01)
        self.yawn_spin.set_value(YAWN_PENALTY)
        self.restore_spin = Gtk.SpinButton.new_with_range(0.00, 1.00, 0.01)
        self.restore_spin.set_value(-1.0 * RESTORE_CREDIT)
        button = Gtk.Button.new_with_label("Apply")
        button.connect("clicked", self.save)

        grid = Gtk.Grid.new()
        grid.attach(bad_label, 0, 0, 1, 1)
        grid.attach(self.bad_spin, 1, 0, 1, 1)
        grid.attach(no_label, 0, 1, 1, 1)
        grid.attach(self.no_spin, 1, 1, 1, 1)
        grid.attach(attention_label, 0, 2, 1, 1)
        grid.attach(self.attention_spin, 1, 2, 1, 1)
        grid.attach(sleepy_label, 0, 3, 1, 1)
        grid.attach(self.sleepy_spin, 1, 3, 1, 1)
        grid.attach(yawn_label, 0, 4, 1, 1)
        grid.attach(self.yawn_spin, 1, 4, 1, 1)
        grid.attach(restore_label, 0, 5, 1, 1)
        grid.attach(self.restore_spin, 1, 5, 1, 1)
        grid.attach(button, 0, 6, 2, 1)
        grid.props.margin = 30
        grid.set_column_spacing(30)
        grid.set_row_spacing(30)

        self.add(grid)

    def save(self, unused):
        """Save selections"""
        global BAD_FACE_PENALTY
        global NO_FACE_PENALTY
        global YAWN_PENALTY
        global DISTRACT_PENALTY
        global SLEEP_PENALTY
        global RESTORE_CREDIT
        BAD_FACE_PENALTY = self.bad_spin.get_value()
        NO_FACE_PENALTY = self.no_spin.get_value()
        YAWN_PENALTY = self.yawn_spin.get_value()
        DISTRACT_PENALTY = self.attention_spin.get_value()
        SLEEP_PENALTY = self.sleepy_spin.get_value()
        RESTORE_CREDIT = -1.0 * self.restore_spin.get_value()
        self.close_window(None)
    
    def close_window(self, unused):
        self.hide()

class StartWindow(Gtk.Window):
    """A window that lets a user select the camera."""

    def __init__(self):
        """Create the UI to selct camera."""
        super().__init__()
        self.set_default_size(500, 300)
        self.set_resizable(False)

        header = Gtk.HeaderBar()
        header.set_title("Driver Monitoring System Demo")
        header.set_subtitle("i.MX 93 Demos")
        self.set_titlebar(header)

        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="application-exit-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        header.pack_end(quit_button)
        quit_button.connect("clicked", Gtk.main_quit)

        vid_label = Gtk.Label.new("Video device: ")
        height_label = Gtk.Label.new("Height: ")
        width_label = Gtk.Label.new("Width: ")
        self.status_label = Gtk.Label.new("")

        devices = []
        for device in glob.glob('/dev/video*'):
            devices.append(device)
        self.source_select = Gtk.ComboBoxText()
        self.source_select.set_entry_text_column(0)
        self.source_select.set_hexpand(True)
        for option in devices:
            self.source_select.append_text(option)
        self.source_select.set_active(0)
        self.height_spin = Gtk.SpinButton.new_with_range(0, 1080, 10)
        self.height_spin.set_value(FRAME_HEIGHT)
        self.width_spin = Gtk.SpinButton.new_with_range(0, 1920, 10)
        self.width_spin.set_value(FRAME_WIDTH)
        self.button = Gtk.Button.new_with_label("Start")
        self.button.connect("clicked", self.start)
        self.width_spin.set_sensitive(False)
        self.height_spin.set_sensitive(False)

        grid = Gtk.Grid.new()
        grid.attach(vid_label, 0, 0, 1, 1)
        grid.attach(self.source_select, 1, 0, 1, 1)
        grid.attach(height_label, 0, 1, 1, 1)
        grid.attach(self.height_spin, 1, 1, 1, 1)
        grid.attach(width_label, 0, 2, 1, 1)
        grid.attach(self.width_spin, 1, 2, 1, 1)
        grid.attach(self.status_label, 0, 3, 2, 1)
        grid.attach(self.button, 0, 4, 2, 1)
        grid.props.margin = 30
        grid.set_column_spacing(30)
        grid.set_row_spacing(30)

        self.add(grid)

    def start(self, unused):
        """Start the video feed"""
        global VIDEO
        global FRAME_WIDTH
        global FRAME_HEIGHT
        global LANDMARK_MODEL
        global FACE_MODEL
        VIDEO = self.source_select.get_active_text()
        FRAME_WIDTH = self.width_spin.get_value()
        FRAME_HEIGHT = self.height_spin.get_value()
        self.button.set_sensitive(False)
        self.width_spin.set_sensitive(False)
        self.height_spin.set_sensitive(False)
        GLib.idle_add(
                self.status_label.set_text, "Downloading landmark model...")
        LANDMARK_MODEL = utils.download_file(
            "face_landmark_192_integer_quant_vela.tflite")
        if (LANDMARK_MODEL == -1 or LANDMARK_MODEL == -2 or
            LANDMARK_MODEL == -3):
            GLib.idle_add(
                self.status_label.set_text, "Download failed! " +
                "Restart demo and try again!")
        else:
            GLib.idle_add(
                self.status_label.set_text, "Downloading face model...")
            FACE_MODEL = utils.download_file("yoloface_int8_vela.tflite")
            if FACE_MODEL == -1 or FACE_MODEL == -2 or FACE_MODEL == -3:
                GLib.idle_add(
                    self.status_label.set_text, "Download failed! " +
                    "Restart demo and try again!")
            else:
                GLib.idle_add(self.launch)

    def launch(self):
        """Launch demo"""
        window = MLVideoDemo()
        window.show_all()
        self.close()



if __name__ == "__main__":
    # Start GStreamer engine
    Gst.init(None)
    # Display window
    window = StartWindow()
    window.show_all()
    # Run GTK loop
    Gtk.main()
