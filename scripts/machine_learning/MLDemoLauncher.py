# ML Demo Launcher
# Copyright NXP 2021

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gio

import glob

import sys
sys.path.append("/home/root/.nxp-demo-experience/scripts/")
import utils
import subprocess
import multiprocessing

class MLLaunch(Gtk.Window):

    def __init__(self, demo):

        # Initialization
        self.DEMO = demo
        super().__init__(title=demo)
        self.set_default_size(450, 250)
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
        self.separator = Gtk.Separator.new(0)
        self.timeTitleLabel = Gtk.Label.new("Update Time")
        self.timeLabel = Gtk.Label.new("--.-- ms")
        self.fpsTitleLabel = Gtk.Label.new("NNStreamer FPS")
        self.fpsLabel = Gtk.Label.new("-- FPS")
        self.header = Gtk.HeaderBar()
        self.quitButton = Gtk.Button()
        self.quitIcon = Gio.ThemedIcon(name="application-exit-symbolic")
        self.quitImage = Gtk.Image.new_from_gicon(self.quitIcon, Gtk.IconSize.BUTTON)

        # Organize widgets
        self.add(self.mainGrid)
        self.set_titlebar(self.header)
        
        self.quitButton.add(self.quitImage)
        self.header.pack_end(self.quitButton)

        self.mainGrid.set_row_spacing(10)
        self.mainGrid.set_border_width(10)
   
        self.mainGrid.attach(self.deviceLabel, 0, 1, 1, 1)
        self.deviceLabel.set_hexpand(True)
        
        self.mainGrid.attach(self.backendLabel, 0, 2, 1, 1)
        
        self.mainGrid.attach(self.displayLabel, 0, 3, 1, 1)
        
        self.mainGrid.attach(self.deviceCombo, 1, 1, 1, 1)
        self.deviceCombo.set_hexpand(True)
        
        self.mainGrid.attach(self.backendCombo, 1, 2, 1, 1)
        
        self.mainGrid.attach(self.displayCombo, 1, 3, 1, 1)
        
        self.mainGrid.attach(self.launchButton, 0, 4, 2, 1)
        
        self.mainGrid.attach(self.separator, 0, 5, 2, 1)
        
        self.mainGrid.attach(self.timeTitleLabel, 0, 6, 1, 1)

        self.mainGrid.attach(self.fpsTitleLabel, 1, 6, 1, 1)

        self.mainGrid.attach(self.timeLabel, 0, 7, 1, 1)
        
        self.mainGrid.attach(self.fpsLabel, 1, 7, 1, 1)

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
        self.quitButton.connect("clicked",exit)
        if self.DEMO == "nndetection":
            self.header.set_title("Detection Demo")
        elif self.DEMO == "nnclassification":
            self.header.set_title("Classification Demo")
        elif self.DEMO == "nnpose":
            self.header.set_title("Pose Demo")
        else :
            self.header.set_title("NNStreamer Demo")
        self.header.set_subtitle("NNStreamer Examples")

    def start(self, button):
        self.updateTime = GLib.get_monotonic_time()
        self.deviceCombo.set_sensitive(False)
        self.backendCombo.set_sensitive(False)
        self.displayCombo.set_sensitive(False)
        self.launchButton.set_sensitive(False)
        if self.DEMO == "nndetection":
            model = utils.downloadFile("mobilenet_ssd_v2_coco_quant_postprocess.tflite")
            labels = utils.downloadFile("coco_labels.txt")
        if self.DEMO == "nnclassification":
            model = utils.downloadFile("mobilenet_v1_1.0_224_quant.tflite")
            labels = utils.downloadFile("1_1.0_224_labels.txt")
        if self.DEMO == "nnpose":
            model = utils.downloadFile("posenet_resnet50_uint8_float32_quant.tflite")
            labels = utils.downloadFile("key_point_labels.txt")
        if (model == -2 or labels == -2):
            print("DB Error")
        if (model == -1 or labels == -1):
            print("DL Error")
        if self.DEMO == "nndetection":
            import nndetection
            example = nndetection.ObjectDetection(self.deviceCombo.get_active_text(), self.backendCombo.get_active_text(), self.displayCombo.get_active_text(), model, labels, self.updateStats)
            example.run()
        if self.DEMO == "nnclassification":
            import nnclassification
            example = nnclassification.NNStreamerExample(self.deviceCombo.get_active_text(), self.backendCombo.get_active_text(), self.displayCombo.get_active_text(), model, labels, self.updateStats)
            example.run_example()
        if self.DEMO == "nnpose":
            import nnpose 
            example = nnpose.NNStreamerExample(self.deviceCombo.get_active_text(), self.backendCombo.get_active_text(), self.displayCombo.get_active_text(), model, labels, self.updateStats)
            example.run_example()
        self.deviceCombo.set_sensitive(True)
        self.backendCombo.set_sensitive(True)
        self.displayCombo.set_sensitive(True)
        self.launchButton.set_sensitive(True)

    def updateStats(self, time):
        interTime = (GLib.get_monotonic_time() - self.updateTime)/1000000
        if interTime > 1:
            self.timeLabel.set_text("{:12.2f}".format(time/1000) + ' ms')
            self.fpsLabel.set_text("{:12.2f}".format(1/(time/1000000)) + ' FPS')
            self.updateTime = GLib.get_monotonic_time()


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

def nnPose():
    win = MLLaunch("nnpose")
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == "__main__":
    if(len(sys.argv) == 1):
        nnDetection()
    elif(sys.argv[1] == 'detect'):
        nnDetection()
    elif(sys.argv[1] == 'id'):
        nnClassification()
    elif(sys.argv[1] == 'pose'):
        nnPose()
    else:
        print("No demo found")
