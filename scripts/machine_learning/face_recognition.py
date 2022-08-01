#!/usr/bin/env python3

"""
Copyright 2022 NXP

SPDX-License-Identifier: Apache-2.0

The following is a demo to show how to recognize faces using
a machine learning application. The models used in this demo are demo
quality only, and should not be used in production software.
"""

import os
import glob
from typing import NamedTuple
import cv2
import time
import tflite_runtime.interpreter as tflite
import numpy as np
import threading
import sys
import argparse
import json

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
from gi.repository import Gtk, Gst, GLib, Gio

sys.path.append("/home/root/.nxp-demo-experience/scripts/")
import utils

DEFAULT_DETECTION_ACCURACY = 0.3
"""The default setting for the detection accuracy cutoff"""

DEFAULT_RECOGNITION_ACCURACY = 0.2
"""The default setting for the recognition accuracy cutoff"""

COUNTDOWN_TIME = 5
"""The time to count down from before taking a photo"""

FACE_DEMO = None
"""Holds the demo thread to be accessed by the GUI."""

class FaceDemo():
    """Run the video and inference part of the application."""

    def start(self, backend, cam):
        """Starts the camera and sets up the inference engine"""
        self.face_models = []
        self.setup_inferences(backend)
        if GUI:
            self.width = 1280
            self.height = 720
        else:
            self.width = 1920
            self.height = 1080
        if GUI:
            GLib.idle_add(
                main_window.status_bar.set_text, "Starting cameras...")
        if cam == "fake":
            cam_pipeline = cv2.VideoCapture(
                "videotestsrc ! imxvideoconvert_g2d ! "
                "video/x-raw,format=RGBA,width=" + str(self.width) + 
                ",height=" + str(self.height) + " ! " +
                "videoconvert ! appsink")
        else:
            cam_pipeline = cv2.VideoCapture(
                "v4l2src device=" + cam + " ! imxvideoconvert_g2d ! "
                "video/x-raw,format=RGBA,width=" + str(self.width) + 
                ",height=" + str(self.height) + " ! " +
                "videoconvert ! appsink")
        if GUI:
            GLib.idle_add(main_window.destroy)
            self.options_window = OptionsWindow()
            GLib.idle_add(self.options_window.show_all)
            GLib.idle_add(cv2.namedWindow, "i.MX Face Recognition Demo")
        elif OUTPUT:
            cv2.namedWindow(
                "i.MX Face Recognition Demo", cv2.WND_PROP_FULLSCREEN)
            cv2.setWindowProperty(
                "i.MX Face Recognition Demo", cv2.WND_PROP_FULLSCREEN,
                cv2.WINDOW_FULLSCREEN)
        status, org_img = cam_pipeline.read()
        self.mode = 0
        self.countdown = None
        self.registered_faces = []
        self.detect_time = None
        self.recog_time = None
        self.write_time = False
        while status:
            mod_img = self.process_frame(org_img)
            if self.write_time:
                overall_time = time.perf_counter() - overall_time
                times = self.get_timings(overall_time)
            else:
                times = ["N/A", "N/A"]
            cv2.putText(
                    mod_img, "Overall time: " + times[0] + " IPS (" +
                    times[1] + " ms)", (5,self.height-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255,255,255), 2)
            if GUI:
                GLib.idle_add(
                    cv2.imshow,"i.MX Face Recognition Demo", mod_img)
            else:
                if OUTPUT:
                    cv2.imshow("i.MX Face Recognition Demo", mod_img)
                    cv2.waitKey(1)
            status, org_img = cam_pipeline.read()
            self.write_time = True
            overall_time = time.perf_counter()

    def setup_inferences(self, backend):
        """Sets up the inference engines"""
        self.face_models.append(self.setup_model(
            "ssd_mobilenet_v2_face_quant_postprocess.tflite", backend))
        self.face_models.append(self.setup_model(
            "facenet_int_quantized.tflite", backend))

    def setup_model(self, name, backend):
        """Gets the model from the server and enables it for use"""
        if GUI:
            GLib.idle_add(
                main_window.status_bar.set_text, "Downloading " + name + "...")
        path = utils.download_file(name)
        if path == -1 or path == -2 or path == -3:
            GLib.idle_add(
                main_window.status_bar.set_text, "Download failed! " +
                "Restart demo and try again!")
            while True:
                time.sleep(9999)
        if GUI:
            GLib.idle_add(
                main_window.status_bar.set_text, "Creating TFLite Engine...")
        if backend == "NPU":
            ext_delegate = tflite.load_delegate("/usr/lib/libvx_delegate.so")
            interpreter = tflite.Interpreter(
                model_path=path, num_threads=4,
                experimental_delegates=[ext_delegate])
        else:
            interpreter = tflite.Interpreter(model_path=path, num_threads=4)
        interpreter.allocate_tensors()
        input_info = interpreter.get_input_details()
        output_info = interpreter.get_output_details()
        input_size_w = input_info[0]['shape'][1]
        input_size_h = input_info[0]['shape'][2]
        if GUI:
            GLib.idle_add(
                main_window.status_bar.set_text, "Warming up backend... (can take a couple minutes)")
        dummy_data = np.zeros((1, input_size_w, input_size_h, 3), dtype=input_info[0]['dtype'])
        interpreter.set_tensor(input_info[0]['index'], dummy_data)
        interpreter.invoke()
        return Model(
            path, interpreter, input_size_w, input_size_h,
            input_info, output_info)

    def process_frame(self, frame):
        """Analyzes the frame and then annotates it"""
        self.recog_time = []
        faces = self.find_faces(frame)
        if self.mode == 1:
            if self.countdown == None:
                self.countdown = time.perf_counter()
            if (time.perf_counter() - self.countdown) < COUNTDOWN_TIME:
                time_left = round(
                    COUNTDOWN_TIME - 
                    (time.perf_counter() - self.countdown), 2)
                cv2.putText(
                    frame, "Taking picture in " + str(time_left) +
                    " seconds...", (50,50), cv2.FONT_HERSHEY_SIMPLEX, 1,
                    (255, 0 , 0), 4)
            else:
                self.countdown = None
                self.mode = 2
        for face in faces:
            face_img = frame[
                int(face[0]*self.height):int(face[2]*self.height),
                int(face[1]*self.width):int(face[3]*self.width)]
            face_info = self.id_face(face_img)
            if self.mode == 0 or self.mode == 1:
                if face_info[0] == "Not found":
                    color = (0, 0, 225)
                else:
                    color = (0, 225, 0)
                cv2.rectangle(
                    frame, ((int(face[1]*self.width)),
                    (int(face[0]*self.height))), ((int(face[3]*self.width)),
                    (int(face[2]*self.height))), color, 2)
                cv2.putText(
                    frame, face_info[0] + " " + str(face_info[1]) + "%",
                    ((int(face[1]*self.width)),
                    (int(face[0]*self.height-10))), cv2.FONT_HERSHEY_SIMPLEX,
                    1.0, color, 4)
            if self.mode == 2:
                blank_frame = frame.copy()
                cv2.rectangle(
                    blank_frame, ((int(face[1]*self.width)),
                    (int(face[0]*self.height))), ((int(face[3]*self.width)),
                    (int(face[2]*self.height))), (225, 0, 0), 2)

                if GUI:
                    GLib.idle_add(
                        cv2.imshow,"i.MX Face Recognition Demo", blank_frame)
                    self.register_face(face_info[2])
                elif OUTPUT:
                    cv2.imshow("i.MX Face Recognition Demo", blank_frame)
                    cv2.waitKey(1)
                if not GUI:    
                    self.register_face_cli(face_info[2])
        if self.mode == 2:
            self.mode = 0
            self.write_time = False
            if GUI:
                self.options_window.unlock_controls()
        detect_time = self.get_timings(self.detect_time)
        cv2.putText(
                        frame, "Detection time: " + detect_time[0] + " IPS (" +
                        detect_time[1] + " ms)", (5,self.height - 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255,255,255), 2)
        recog_time = 0
        for times in self.recog_time:
            recog_time = times + recog_time
        if len(self.recog_time) != 0:
            recog_time = recog_time / len(self.recog_time)
            recog_time = self.get_timings(recog_time)
        else:
            recog_time = ["N/A", "N/A"]
        cv2.putText(
                        frame, "Recognition time: " + recog_time[0] +
                        " IPS (" + recog_time[1] + " ms - " +
                        str(len(self.recog_time)) + " face(s))",
                        (5,self.height - 60), cv2.FONT_HERSHEY_SIMPLEX,
                        0.75, (255,255,255), 2)
        cv2.putText(
                        frame, "i.MX Face Recognition Demo",
                        (5,self.height - 85), cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                        (255,255,255), 2)
        return frame

    def find_faces(self, frame):
        """Find the faces in a frame"""
        self.detect_time = self.run_inference(frame, self.face_models[0])
        face_boxes = self.face_models[0].interpreter.get_tensor(
            self.face_models[0].output_info[0]['index'])[0]
        face_scores = self.face_models[0].interpreter.get_tensor(
            self.face_models[0].output_info[2]['index'])[0]
        face_total = self.face_models[0].interpreter.get_tensor(
            self.face_models[0].output_info[3]['index'])[0]
        face_output = []
        for face in range(int(face_total)):
            if (
                face_scores[face] > DEFAULT_DETECTION_ACCURACY and
                self.valid_face(face_boxes[face])):
                face_output.append(face_boxes[face])
        return face_output

    def id_face(self, face):
        """Try to find matches for face"""
        self.recog_time.append(self.run_inference(face, self.face_models[1]))
        face_map = self.face_models[1].interpreter.get_tensor(
            self.face_models[1].output_info[0]['index'])[0]
        match = ["Not found", 1.00]
        unmatched = True
        for maps in self.registered_faces:
            sim = self.get_similarity(face_map, maps[1])
            if unmatched and sim > DEFAULT_RECOGNITION_ACCURACY:
                unmatched = False
                match = [maps[0],sim]
            elif sim > match[1] and sim > DEFAULT_RECOGNITION_ACCURACY:
                match = [maps[0],sim]
            elif unmatched:
                cert = 1 - sim
                if cert < match[1]:
                    match[1] = cert
        match[1] = round(match[1]*100, 2)
        match.append(face_map)
        return match

    def valid_face(self, face):
        """Checks if the give face bounding box falls outside the image"""
        for cord in range(4):
            if face[cord] < 0:
                return False
        return True

    def get_similarity(self, face_a, face_b):
        """Finds the similarity between two masks
        This is done by taking the vectors in the face mask and finding the
        cosine similarity between them. The formula to find this is:

                                  f(a[n] * b[n])
        sim (a[],b[]) = -----------------------------------
                         sqrt(f(a[n]^2)) * sqrt(f(b[n]^2))

        where:
        - a[] and b[] both represent the array of values of a single face mask
        - f(n) is the sum of values where n is 0 through the length of a[]
          minus 1
        - a[] and b[] have equal lengths and equal indexes map to the same
          points on the face mask

        The idea behind this method is that vectors that have smaller
        vectors between them (independent of magnitude) should in theory be
        similar.
        """
        dot = 0
        a_sum = 0
        b_sum = 0
        for count in range(128):
            dot = dot + (face_a[count]*face_b[count])
            a_sum = a_sum + (face_a[count] * face_a[count])
            b_sum = b_sum + (face_b[count] * face_b[count])
        sim = dot/(np.sqrt(a_sum) * np.sqrt(b_sum))
        return sim

    def run_inference(self, frame, model):
        """Runs an inference on a model"""
        input_img = cv2.resize(
            frame, [model.input_size_w, model.input_size_h])
        input_img = np.expand_dims(input_img, axis=0)
        if (model.input_info[0]['dtype'] == np.float32):
            input_img = np.float32(input_img) / 255
        model.interpreter.set_tensor(model.input_info[0]['index'], input_img)
        start = time.perf_counter()
        model.interpreter.invoke()
        return time.perf_counter() - start

    def register_face(self, face_mask):
        """Registers a new face"""
        face_window = FaceWindow()
        GLib.idle_add(face_window.show_all)
        while face_window.working:
            time.sleep(0.1)
        if face_window.named_face is not None:
            self.registered_faces.append([face_window.named_face, face_mask])
        GLib.idle_add(face_window.destroy)

    def register_face_cli(self, face_mask):
        """Registers a new face with command line"""
        name = input("Name the face in the blue box: ")
        self.registered_faces.append([name, face_mask])

    def get_timings(self, time):
        """Get timings to display"""
        fps = str(round(1/time, 2))
        ms = str(round(time*1000, 2))
        return [fps, ms]

    def export_database(self):
        """Exports database"""
        out = []
        for face in self.registered_faces:
            obj = {"name":face[0], "mask":face[1].tolist()}
            out.append(obj)
        data = json.dumps(out)
        file = open("/home/root/face.json", "w")
        file.write(data)
        file.close()
        print("File written to /home/root/face.json")

    def import_database(self, path):
        """Imports database"""
        file = open(path, 'r')
        data = json.load(file)
        file.close()
        n = 0
        for face in data:
            self.registered_faces.append(
                [face['name'], np.array(face['mask'], dtype=np.float32)])
            n = n + 1
        print(str(int(n)) + " faces imported")


    
class Model(NamedTuple):
    """Represents a model and the information to run it"""
    path: str
    interpreter: tflite.Interpreter
    input_size_w: int
    input_size_h: int
    input_info: list
    output_info: list

class MainWindow(Gtk.Window):
    """Main GUI window that starts the demo"""

    def __init__(self):
        """Sets up the first window to do preroll setup"""
        super().__init__()
        self.set_default_size(450, 200)
        self.set_resizable(False)
        self.set_border_width(10)
        devices = []
        for device in glob.glob('/dev/video*'):
            devices.append(device)
        if os.path.exists("/usr/lib/libneuralnetworks.so"):
            backends_available = ["NPU", "CPU"]
        else:
            backends_available = ["CPU"]
        
        main_grid = Gtk.Grid(
            row_homogeneous=True, column_spacing=15, row_spacing=15)
        main_grid.set_margin_end(10)
        main_grid.set_margin_start(10)

        header = Gtk.HeaderBar()
        header.set_title("i.MX Face Recognition Demo")
        header.set_subtitle("i.MX Machine Learning Demos")
        self.set_titlebar(header)

        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        header.pack_end(quit_button)
        quit_button.connect("clicked", Gtk.main_quit)

        source_label = Gtk.Label.new("Source")
        source_label.set_halign(1)

        self.source_select = Gtk.ComboBoxText()
        self.source_select.set_entry_text_column(0)
        for option in devices:
            self.source_select.append_text(option)
        self.source_select.set_active(0)
        self.source_select.set_hexpand(True)

        backend_label = Gtk.Label.new("Backend")
        backend_label.set_halign(1)

        self.backend_select = Gtk.ComboBoxText()
        self.backend_select.set_entry_text_column(0)
        for option in backends_available:
            self.backend_select.append_text(option)
        self.backend_select.set_active(0)
        self.backend_select.set_hexpand(True)

        self.launch_button = Gtk.Button.new_with_label("Run")
        self.launch_button.connect("clicked",self.on_change_start)

        self.status_bar = Gtk.Label.new()

        main_grid.attach(source_label, 0, 1, 1, 1)
        main_grid.attach(backend_label, 0, 2, 1, 1)

        main_grid.attach(self.source_select, 1, 1, 1, 1)
        main_grid.attach(self.backend_select, 1, 2, 1, 1)

        main_grid.attach(self.launch_button, 0, 3, 2, 1)
        main_grid.attach(self.status_bar, 0, 4, 2, 1)

        self.add(main_grid)

    def on_change_start(self, widget):
        """Starts the video stream"""
        self.status_bar.set_text("Starting demo...")
        widget.set_sensitive(False)
        self.backend_select.set_sensitive(False)
        self.source_select.set_sensitive(False)
        global FACE_DEMO
        FACE_DEMO = FaceDemo()
        cam_thread = threading.Thread(
            target=FaceDemo.start,
            args=(FACE_DEMO, self.backend_select.get_active_text(),
            self.source_select.get_active_text()))
        cam_thread.daemon =True
        cam_thread.start()

class OptionsWindow(Gtk.Window):
    """GUI for during play opperations"""

    def __init__(self):
        """Creates GUI elements for window"""
        super().__init__()
        self.set_default_size(450, 200)
        self.set_resizable(False)
        self.set_border_width(10)

        main_grid = Gtk.Grid(
            row_homogeneous=True, column_spacing=15, row_spacing=15)
        main_grid.set_margin_end(10)
        main_grid.set_margin_start(10)

        header = Gtk.HeaderBar()
        header.set_title("i.MX Face Recognition Demo")
        header.set_subtitle("i.MX Machine Learning Demos")
        self.set_titlebar(header)

        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        header.pack_end(quit_button)
        quit_button.connect("clicked", Gtk.main_quit)

        face_det_label = Gtk.Label.new("Detection Cutoff (%)")

        face_reg_label = Gtk.Label.new("Recognition Cutoff (%)")

        self.face_det_entry = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 1, 100, 1)
        self.face_det_entry.set_value(DEFAULT_DETECTION_ACCURACY*100)
        self.face_det_entry.set_hexpand(True)
        self.face_det_entry.connect('value-changed', self.change_det_acc)

        self.face_reg_entry = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL, 1, 100, 1)
        self.face_reg_entry.set_value(DEFAULT_RECOGNITION_ACCURACY*100)
        self.face_reg_entry.connect('value-changed', self.change_rec_acc)

        self.launch_button = Gtk.Button.new_with_label("Register Face")
        self.launch_button.connect("clicked", self.register_faces)
        self.launch_button.set_hexpand(True)

        main_grid.attach(face_det_label, 0, 0, 1, 1)
        main_grid.attach(self.face_det_entry, 1, 0, 1, 1)
        main_grid.attach(face_reg_label, 0, 1, 1, 1)
        main_grid.attach(self.face_reg_entry, 1, 1, 1, 1)
        main_grid.attach(self.launch_button, 0, 2, 2, 1)

        self.add(main_grid)

    def register_faces(self, widget):
        """Changes mode to register faces"""
        self.lock_controls()
        FACE_DEMO.mode = 1

    def lock_controls(self):
        """Locks controls"""
        self.launch_button.set_sensitive(False)
        self.face_reg_entry.set_sensitive(False)
        self.face_det_entry.set_sensitive(False)

    def unlock_controls(self):
        """Unlocks controls"""
        self.launch_button.set_sensitive(True)
        self.face_reg_entry.set_sensitive(True)
        self.face_det_entry.set_sensitive(True)

    def change_det_acc(self, widget):
        """Changes detection accuracy"""
        global DEFAULT_DETECTION_ACCURACY
        DEFAULT_DETECTION_ACCURACY = widget.get_value()/100
    
    def change_rec_acc(self, widget):
        """Changes recognition accuracy"""
        global DEFAULT_RECOGNITION_ACCURACY
        DEFAULT_RECOGNITION_ACCURACY = widget.get_value()/100

class FaceWindow(Gtk.Window):
    """GUI for users to register face"""

    def __init__(self):
        """Creates GUI elements for window"""
        super().__init__()
        self.named_face = None
        self.working = True
        self.set_default_size(450, 200)
        self.set_resizable(False)
        self.set_border_width(10)

        main_grid = Gtk.Grid(
            row_homogeneous=True, column_spacing=15, row_spacing=15)
        main_grid.set_margin_end(10)
        main_grid.set_margin_start(10)

        header = Gtk.HeaderBar()
        header.set_title("i.MX Face Recognition Demo")
        header.set_subtitle("i.MX Machine Learning Demos")
        self.set_titlebar(header)

        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="application-exit-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        quit_button.add(quit_image)
        header.pack_end(quit_button)
        quit_button.connect("clicked", self.go_back)

        question = Gtk.Label(
            label="Who is in the blue box?"
        )

        self.name_box = Gtk.Entry()
        global FACE_DEMO
        self.name_box.set_text(
            "Person " + str(len(FACE_DEMO.registered_faces) + 1))

        self.add_button = Gtk.Button.new_with_label("Register Face")
        self.add_button.connect("clicked", self.register_face)
        self.add_button.set_hexpand(True)

        self.skip_button = Gtk.Button.new_with_label("Skip Face")
        self.skip_button.connect("clicked", self.go_back)
        self.skip_button.set_hexpand(True)

        main_grid.attach(question, 0, 0, 1, 1)
        main_grid.attach(self.name_box, 0, 1, 1, 1)
        main_grid.attach(self.add_button, 0, 2, 1, 1)
        main_grid.attach(self.skip_button, 0, 3, 1, 1)

        self.add(main_grid)
    
    def register_face(self, widget):
        """Registers a face"""
        self.name_box.set_sensitive(False)
        self.add_button.set_sensitive(False)
        self.named_face = self.name_box.get_text()
        self.working = False

    def go_back(self, widget):
        """Exits without registering"""
        self.name_box.set_sensitive(False)
        self.add_button.set_sensitive(False)
        self.working = False


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--gui', type=int, default=1, help='Run with GUI')
    parser.add_argument(
        '--show', type=int, default=1, help='Show output')
    parser.add_argument(
        '--npu', type=int, default=1, help='Use NPU')
    parser.add_argument(
        '--camera', type=int, default=0, help='Which camera to use')
    parser.add_argument(
        '--faces', default="", help='Load existing faces')
    args = parser.parse_args()
    os.environ["VIV_VX_CACHE_BINARY_GRAPH_DIR"] = ("/home/root/.cache"
            "/demoexperience")
    os.environ["VIV_VX_ENABLE_CACHE_GRAPH_BINARY"] = "1"
    if(args.gui == 0):
        GUI = False
        print("Command line mode!")
        if args.show == 0:
            OUTPUT = False
            print("Will not show output!")
            output = False
        else:
            OUTPUT = True
            print("Will show output")
            output = True
        if args.npu == 0:
            print("Will not use NPU!")
            backend = "CPU"
        else:
            print("Will use NPU")
            backend = "NPU"
        if (args.camera == -1):
            print("Using videotestsrc!")
            device = "fake"
        else:
            print("Using /dev/video" + str(args.camera))
            device = "/dev/video" + str(args.camera)
        FACE_DEMO = FaceDemo()
        cam_thread = threading.Thread(
            target=FaceDemo.start,
            args=(FACE_DEMO, backend, device))
        cam_thread.daemon =True
        cam_thread.start()
        time.sleep(3)
        if(args.faces != ""):
            FACE_DEMO.import_database(args.faces)
        print("##### HOW TO USE #####")
        print("# R - Register Face  #")
        print("# E - Export Faces   #")
        print("# Q - Quit Demo      #")
        print("######################")
        while(True):
            if FACE_DEMO.mode == 0:
                option = input("Select option: ")
                if option == "R":
                    print("Taking picture...")
                    FACE_DEMO.mode = 1
                elif option == "E":
                    print("Exporting file...")
                    FACE_DEMO.export_database()
                elif option == "Q":
                    print("Exiting...")
                    sys.exit()
    else:
        GUI = True
        Gst.init(None)
        main_window = MainWindow()
        main_window.show_all()
        Gtk.main()
