# ML Demo Launcher
# Copyright NXP 2021

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import glob

import sys
sys.path.append("/home/root/.nxp-demo-experience/scripts/")
import utils
import subprocess

class MLLaunch(Gtk.Window):

    def __init__(self, demo):

        # Initialization
        self.DEMO = demo
        super().__init__(title=demo)
        self.set_default_size(450, 150)
        self.set_resizable(False)

        # Get widget properties
        devices = []
        for device in glob.glob('/dev/video*'):
            devices.append(device)
        
        backendsAvl = ["CPU", "GPU", "NPU"]

        displaysAvl = ["X11", "Weston"]

        # Create widgets
        self.mainGrid = Gtk.Grid.new()
        self.deviceLabel = Gtk.Label.new("Camera")
        self.deviceCombo = Gtk.ComboBoxText()
        self.backendLabel = Gtk.Label.new("Backend")
        self.backendCombo = Gtk.ComboBoxText()
        self.displayLabel = Gtk.Label.new("Display")
        self.displayCombo = Gtk.ComboBoxText()
        self.launchButton = Gtk.Button.new_with_label("Run")

        # Organize widgets
        self.add(self.mainGrid)
        
        self.mainGrid.attach(self.deviceLabel, 0, 1, 1, 1)
        self.deviceLabel.set_hexpand(True)
        
        self.mainGrid.attach(self.backendLabel, 0, 2, 1, 1)
        
        self.mainGrid.attach(self.displayLabel, 0, 3, 1, 1)
        
        self.mainGrid.attach(self.deviceCombo, 1, 1, 1, 1)
        self.deviceCombo.set_hexpand(True)
        
        self.mainGrid.attach(self.backendCombo, 1, 2, 1, 1)
        
        self.mainGrid.attach(self.displayCombo, 1, 3, 1, 1)
        
        self.mainGrid.attach(self.launchButton, 0, 4, 2, 1)

        # Configure widgets
        for device in devices:
            self.deviceCombo.append_text(device)
        for backend in backendsAvl:
            self.backendCombo.append_text(backend)
        for display in displaysAvl:
            self.displayCombo.append_text(display)

        self.deviceCombo.set_active(0)
        self.backendCombo.set_active(0)
        self.displayCombo.set_active(0)
        self.launchButton.connect("clicked",self.start)

    def start(self, button):
        if self.DEMO == "nndetection":
            model = utils.downloadFile("mobilenet_ssd_v2_coco_quant_postprocess.tflite")
            labels = utils.downloadFile("coco_labels.txt")
        if self.DEMO == "nnclassification":
            model = utils.downloadFile("mobilenet_v1_1.0_224_quant.tflite")
            labels = utils.downloadFile("1_1.0_224_labels.txt")
        if self.DEMO == "nnpose":
            model = utils.downloadFile("posenet_resnet50_{:d}_{:d}_uint8_float32_quant.tflite")
            labels = utils.downloadFile("key_point_labels.txt")
        if (model == -2 or labels == -2):
            print("DB Error")
        if (model == -1 or labels == -1):
            print("DL Error")
        if self.DEMO == "nndetection":
            subprocess.call(['/home/root/.nxp-demo-experience/scripts/machine_learning/nndetection.py', self.deviceCombo.get_active_text(), self.backendCombo.get_active_text(), self.displayCombo.get_active_text(), model, labels])
        if self.DEMO == "nnclassification":
            print("test")
            subprocess.call(['/home/root/.nxp-demo-experience/scripts/machine_learning/nnclassification.py', self.deviceCombo.get_active_text(), self.backendCombo.get_active_text(), self.displayCombo.get_active_text(), model, labels])
        if self.DEMO == "nnpose":
            print("TODO")


def nnDetection():
    win = MLLaunch("nndetection")
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

def nnClassification():
    win = MLLaunch("nnclassification")
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    print(sys.argv)
    if(sys.argv[1] == 'detect'):
        nnDetection()
    elif(sys.argv[1] == 'id'):
        nnClassification()
    else:
        print("No demo found")
