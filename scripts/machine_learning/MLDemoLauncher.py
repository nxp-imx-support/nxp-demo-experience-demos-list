#!/usr/bin/env python3

"""
Copyright 2021-2023 NXP

SPDX-License-Identifier: BSD-2-Clause

This script launches the NNStreamer ML Demos using a UI to pick settings.
"""

import gi
import os
import sys
import glob
from gi.repository import Gtk, GLib, Gio

gi.require_version("Gtk", "3.0")

sys.path.append("/home/root/.nxp-demo-experience/scripts/")
import utils


class MLLaunch(Gtk.Window):
    """The GUI window for the ML demo launcher"""

    def __init__(self, demo):
        """Creates the UI window"""
        # Initialization
        self.demo = demo
        super().__init__(title=demo)
        self.set_default_size(450, 200)
        self.set_resizable(False)
        os.environ["VIV_VX_CACHE_BINARY_GRAPH_DIR"] = "/home/root/.cache/demoexperience"
        os.environ["VIV_VX_ENABLE_CACHE_GRAPH_BINARY"] = "1"

        # Get platform
        self.platform = os.uname().nodename

        # Get widget properties
        devices = []
        if self.demo != "brand" and self.demo != "selfie_nn":
            if self.platform != "imx93evk":
                devices.append("Example Video")

        for device in glob.glob("/dev/video*"):
            devices.append(device)

        backends_available = ["CPU"]
        if (
            os.path.exists("/usr/lib/libvx_delegate.so")
            and self.demo != "pose"
            and self.demo != "selfie_nn"
        ):
            backends_available.insert(1, "GPU")
        if os.path.exists("/usr/lib/libneuralnetworks.so") and self.demo != "brand" and self.platform != "imx8qmmek":
            backends_available.insert(0, "NPU")
        if os.path.exists("/usr/lib/libethosu_delegate.so"):
            backends_available.insert(0, "NPU")
            backends_available.pop()

        displays_available = ["Weston"]

        colors_available = ["Red", "Green", "Blue", "Black", "White"]

        demo_modes_available = ["Background Substitution", "Segmentation Mask"]

        # Create widgets
        main_grid = Gtk.Grid.new()
        device_label = Gtk.Label.new("Source")
        self.device_combo = Gtk.ComboBoxText()
        backend_label = Gtk.Label.new("Backend")
        self.backend_combo = Gtk.ComboBoxText()
        self.display_combo = Gtk.ComboBoxText()
        self.launch_button = Gtk.Button.new_with_label("Run")
        self.status_bar = Gtk.Label.new()
        header = Gtk.HeaderBar()
        quit_button = Gtk.Button()
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        separator = Gtk.Separator.new(0)
        time_title_label = Gtk.Label.new("Video Refresh")
        self.time_label = Gtk.Label.new("--.-- ms")
        self.fps_label = Gtk.Label.new("-- FPS")
        inference_title_label = Gtk.Label.new("Inference Time")
        self.inference_label = Gtk.Label.new("--.-- ms")
        self.ips_label = Gtk.Label.new("-- IPS")
        if self.demo != "selfie_nn":
            self.width_entry = self.r_scale = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 300, 1920, 2
            )
            self.height_entry = self.r_scale = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 300, 1080, 2
            )
            self.width_label = Gtk.Label.new("Height")
            self.height_label = Gtk.Label.new("Width")
            self.color_label = Gtk.Label.new("Label Color")
        else:
            self.color_label = Gtk.Label.new("Text Color")
            self.demo_mode = Gtk.Label.new("Demo Mode")
            self.mode_combo = Gtk.ComboBoxText()
        self.color_combo = Gtk.ComboBoxText()

        # Organize widgets
        self.add(main_grid)
        self.set_titlebar(header)

        quit_button.add(quit_image)
        header.pack_end(quit_button)

        main_grid.set_row_spacing(10)
        main_grid.set_border_width(10)

        main_grid.attach(device_label, 0, 1, 2, 1)
        device_label.set_hexpand(True)
        main_grid.attach(backend_label, 0, 2, 2, 1)
        # main_grid.attach(display_label, 0, 3, 2, 1)
        if self.demo != "selfie_nn":
            main_grid.attach(self.width_label, 0, 4, 2, 1)
            main_grid.attach(self.height_label, 0, 5, 2, 1)
            main_grid.attach(self.color_label, 0, 6, 2, 1)
        else:
            main_grid.attach(self.demo_mode, 0, 4, 2, 1)
            main_grid.attach(self.color_label, 0, 5, 2, 1)

        main_grid.attach(self.device_combo, 2, 1, 2, 1)
        self.device_combo.set_hexpand(True)
        main_grid.attach(self.backend_combo, 2, 2, 2, 1)
        # main_grid.attach(self.display_combo, 2, 3, 2, 1)
        if self.demo != "selfie_nn":
            main_grid.attach(self.width_entry, 2, 4, 2, 1)
            main_grid.attach(self.height_entry, 2, 5, 2, 1)
            main_grid.attach(self.color_combo, 2, 6, 2, 1)
        else:
            main_grid.attach(self.mode_combo, 2, 4, 2, 1)
            main_grid.attach(self.color_combo, 2, 5, 2, 1)

        main_grid.attach(self.launch_button, 0, 7, 4, 1)
        main_grid.attach(self.status_bar, 0, 8, 4, 1)

        main_grid.attach(separator, 0, 9, 4, 1)

        main_grid.attach(time_title_label, 0, 10, 2, 1)
        main_grid.attach(self.time_label, 0, 11, 1, 1)
        main_grid.attach(self.fps_label, 1, 11, 1, 1)
        main_grid.attach(inference_title_label, 2, 10, 2, 1)
        main_grid.attach(self.inference_label, 2, 11, 1, 1)
        main_grid.attach(self.ips_label, 3, 11, 1, 1)

        # Configure widgets
        for device in devices:
            self.device_combo.append_text(device)
        for backend in backends_available:
            self.backend_combo.append_text(backend)
        for display in displays_available:
            self.display_combo.append_text(display)
        for color in colors_available:
            self.color_combo.append_text(color)
        if self.demo == "selfie_nn":
            for mode in demo_modes_available:
                self.mode_combo.append_text(mode)

        self.device_combo.set_active(0)
        self.backend_combo.set_active(0)
        self.display_combo.set_active(0)
        self.color_combo.set_active(0)
        if self.demo != "selfie_nn":
            self.width_entry.set_value(1920)
            self.height_entry.set_value(1080)
            self.width_entry.set_sensitive(False)
            self.height_entry.set_sensitive(False)
        else:
            self.mode_combo.set_active(0)
        self.device_combo.connect("changed", self.on_source_change)
        self.launch_button.connect("clicked", self.start)
        quit_button.connect("clicked", exit)
        if self.demo == "detect":
            header.set_title("Detection Demo")
        elif self.demo == "id":
            header.set_title("Classification Demo")
        elif self.demo == "pose":
            header.set_title("Pose Demo")
        elif self.demo == "brand":
            header.set_title("Brand Demo")
        elif self.demo == "selfie_nn":
            header.set_title("Selfie Segmenter Demo")
        else:
            header.set_title("NNStreamer Demo")
        header.set_subtitle("NNStreamer Examples")

    def start(self, button):
        """Starts the ML Demo with selected settings"""
        self.update_time = GLib.get_monotonic_time()
        self.launch_button.set_sensitive(False)
        if self.color_combo.get_active_text() == "Red":
            r = 1
            g = 0
            b = 0
        elif self.color_combo.get_active_text() == "Blue":
            r = 0
            g = 0
            b = 1
        elif self.color_combo.get_active_text() == "Green":
            r = 0
            g = 1
            b = 0
        elif self.color_combo.get_active_text() == "Black":
            r = 0
            g = 0
            b = 0
        elif self.color_combo.get_active_text() == "White":
            r = 1
            g = 1
            b = 1
        else:
            r = 1
            g = 0
            b = 0
        if self.demo == "detect":
            if self.platform == "imx93evk":
                model = utils.download_file("mobilenet_ssd_v2_coco_quant_postprocess_vela.tflite")
            else:
                model = utils.download_file("mobilenet_ssd_v2_coco_quant_postprocess.tflite")
            labels = utils.download_file("coco_labels.txt")
            if self.device_combo.get_active_text() == "Example Video":
                device = utils.download_file("detect_example.mov")
            else:
                device = self.device_combo.get_active_text()
            if model == -1 or model == -2 or model == -3:
                if self.platform == "imx93evk":
                    error = "mobilenet_ssd_v2_coco_quant_postprocess_vela.tflite"
                else:
                    error = "mobilenet_ssd_v2_coco_quant_postprocess.tflite"
            elif labels == -1 or labels == -2 or labels == -3:
                error = "coco_labels.txt"
            elif device == -1 or device == -2 or device == -3:
                error = "detect_example.mov"
        if self.demo == "id":
            if self.platform == "imx93evk":
                model = utils.download_file("mobilenet_v1_1.0_224_quant_vela.tflite")
            else:
                model = utils.download_file("mobilenet_v1_1.0_224_quant.tflite")
            labels = utils.download_file("1_1.0_224_labels.txt")
            if self.device_combo.get_active_text() == "Example Video":
                device = utils.download_file("id_example.mov")
            else:
                device = self.device_combo.get_active_text()
            if model == -1 or model == -2 or model == -3:
                if self.platform == "imx93evk":
                    error = "mobilenet_v1_1.0_224_quant_vela.tflite"
                else:
                    error = "mobilenet_v1_1.0_224_quant.tflite"
            elif labels == -1 or labels == -2 or labels == -3:
                error = "1_1.0_224_labels.txt"
            elif device == -1 or device == -2 or device == -3:
                error = "id_example.mov"
        if self.demo == "pose":
            model = utils.download_file("posenet_resnet50_uint8_float32_quant.tflite")
            labels = utils.download_file("key_point_labels.txt")
            if self.device_combo.get_active_text() == "Example Video":
                device = utils.download_file("pose_example.mov")
            else:
                device = self.device_combo.get_active_text()
            if model == -1 or model == -2 or model == -3:
                error = "posenet_resnet50_uint8_float32_quant.tflite"
            elif labels == -1 or labels == -2 or labels == -3:
                error = "key_point_labels.txt"
            elif device == -1 or device == -2 or device == -3:
                error = "pose_example.mov"
        if self.demo == "brand":
            model = utils.download_file("brand_model.tflite")
            labels = utils.download_file("brand_labels.txt")
            if self.device_combo.get_active_text() == "Example Video":
                device = utils.download_file("brand_example.mov")
            else:
                device = self.device_combo.get_active_text()
            if model == -1 or model == -2 or model == -3:
                error = "brand_model.tflite"
            elif labels == -1 or labels == -2 or labels == -3:
                error = "brand_labels.txt"
            elif device == -1 or device == -2 or device == -3:
                error = "brand_example.mov"
        if self.demo == "selfie_nn":
            if self.platform == "imx93evk":
                model = utils.download_file(
                    "selfie_segmenter_landscape_int8_vela.tflite"
                )
            else:
                model = utils.download_file("selfie_segmenter_int8.tflite")
            # Labels refer to background img
            if self.platform == "imx93evk":
                labels = utils.download_file("bg_image_landscape.jpg")
            else:
                labels = utils.download_file("bg_image.jpg")
            if self.device_combo.get_active_text() == "Example Video":
                device = utils.download_file("selfie_example.mov")
            else:
                device = self.device_combo.get_active_text()
            if model == -1 or model == -2 or model == -3:
                if self.platform == "imx93evk":
                    error = "selfie_segmenter_landscape_int8_vela.tflite"
                else:
                    error = "selfie_segmenter_int8.tflite"
            elif labels == -1 or labels == -2 or labels == -3:
                if self.platform == "imx93evk":
                    error = "bg_image_landscape.jpg"
                else:
                    error = "bg_image.jpg"
            elif device == -1 or device == -2 or device == -3:
                error = "selfie_example.mov"
            if self.mode_combo.get_active_text() == "Background Substitution":
                set_mode = 0
            else:
                set_mode = 1

        if model == -1 or labels == -1 or device == -1:
            """
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CANCEL,
                text="Cannot find files! The file that you requested" +
                " does not have any metadata that is related to it. " +
                "Please see /home/root/.nxp-demo-experience/downloads.txt" +
                " to see if the requested file exists! \n \n Cannot find:" +
                error)
            dialog.run()
            dialog.destroy()
            """
            self.status_bar.set_text("Cannot find files!")
            self.launch_button.set_sensitive(True)
            return
        if model == -2 or labels == -2 or device == -2:
            """
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CANCEL,
                text="Cannot download files! The URL used to download the" +
                " file cannot be reached. If you are connected to the " +
                "internet, please check the /home/root/.nxp-demo-experience" +
                "/downloads.txt for the URL. For some regions, " +
                "these sites may be blocked. To install these manually," +
                " please go to the file listed above and provide the " +
                "path to the file in \"PATH\" \n \n Cannot download " + error)
            dialog.run()
            dialog.destroy()
            """
            self.status_bar.set_text("Download failed!")
            self.launch_button.set_sensitive(True)
            return
        if model == -3 or labels == -3 or device == -4:
            """
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.ERROR,
                buttons=Gtk.ButtonsType.CANCEL,
                text="Invalid files! The files where not what we expected." +
                "If you are SURE that the files are correct, delete " +
                "the \"SHA\" value in /home/root/.nxp-demo-experience" +
                "/downloads.txt to bypass the SHA check. \n \n Bad SHA for " +
                error)
            dialog.run()
            dialog.destroy()
            """
            self.status_bar.set_text("Downloaded bad file!")
            self.launch_button.set_sensitive(True)
            return
        if self.demo == "detect":
            import nndetection

            example = nndetection.ObjectDetection(
                self.platform,
                device,
                self.backend_combo.get_active_text(),
                model,
                labels,
                self.display_combo.get_active_text(),
                self.update_stats,
                self.width_entry.get_value(),
                self.height_entry.get_value(),
                r,
                g,
                b,
            )
            example.run()
        if self.demo == "id":
            import nnclassification

            example = nnclassification.NNStreamerExample(
                self.platform,
                device,
                self.backend_combo.get_active_text(),
                model,
                labels,
                self.display_combo.get_active_text(),
                self.update_stats,
                self.width_entry.get_value(),
                self.height_entry.get_value(),
                r,
                g,
                b,
            )
            example.run_example()
        if self.demo == "pose":
            import nnpose

            example = nnpose.NNStreamerExample(
                self.platform,
                device,
                self.backend_combo.get_active_text(),
                model,
                labels,
                self.display_combo.get_active_text(),
                self.update_stats,
                self.width_entry.get_value(),
                self.height_entry.get_value(),
                r,
                g,
                b,
            )
            example.run_example()
        if self.demo == "brand":
            import nnbrand

            example = nnbrand.NNStreamerExample(
                self.platform,
                device,
                self.backend_combo.get_active_text(),
                model,
                labels,
                self.display_combo.get_active_text(),
                self.update_stats,
                self.width_entry.get_value(),
                self.height_entry.get_value(),
                r,
                g,
                b,
            )
            example.run_example()
        if self.demo == "selfie_nn":
            import selfie_segmenter

            example = selfie_segmenter.SelfieSegmenter(
                self.platform,
                device,
                self.backend_combo.get_active_text(),
                model,
                labels,
                self.update_stats,
                set_mode,
                r,
                g,
                b,
            )
            example.run()

        self.launch_button.set_sensitive(True)

    def update_stats(self, time):
        """Callback used the update stats in GUI"""
        interval_time = (GLib.get_monotonic_time() - self.update_time) / 1000000
        if interval_time > 1:
            refresh_time = time.interval_time
            inference_time = time.tensor_filter.get_property("latency")

            if refresh_time != 0 and inference_time != 0:
                # Print pipeline information
                if self.demo == "selfie_nn" or self.demo == "id" or self.demo == "detect":
                    self.time_label.set_text(
                        "{:12.2f} ms".format(1.0 / time.current_framerate * 1000.0)
                    )
                    self.fps_label.set_text(
                        "{:12.2f} FPS".format(time.current_framerate)
                    )
                else:
                    self.time_label.set_text("{:12.2f} ms".format(refresh_time / 1000))
                    self.fps_label.set_text(
                        "{:12.2f} FPS".format(1 / (refresh_time / 1000000))
                    )
                # Print inference information
                self.inference_label.set_text(
                    "{:12.2f} ms".format(inference_time / 1000)
                )
                self.ips_label.set_text(
                    "{:12.2f} FPS".format(1 / (inference_time / 1000000))
                )
            self.update_time = GLib.get_monotonic_time()
        return True

    def on_source_change(self, widget):
        """Callback to lock sliders"""
        if self.demo != "selfie_nn":
            if self.device_combo.get_active_text() == "Example Video":
                self.width_entry.set_value(1920)
                self.height_entry.set_value(1080)
                self.width_entry.set_sensitive(False)
                self.height_entry.set_sensitive(False)
            else:
                self.width_entry.set_sensitive(True)
                self.height_entry.set_sensitive(True)


if __name__ == "__main__":
    if (
        len(sys.argv) != 2
        and sys.argv[1] != "detect"
        and sys.argv[1] != "id"
        and sys.argv[1] != "pose"
        and sys.argv[1] != "selfie_nn"
    ):
        print("Demos available: detect, id, pose, selfie_nn")
    else:
        win = MLLaunch(sys.argv[1])
        win.connect("destroy", Gtk.main_quit)
        win.show_all()
        Gtk.main()
