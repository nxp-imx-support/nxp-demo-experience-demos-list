"""
Copyright 2023 NXP

SPDX-License-Identifier: BSD-3-Clause

This script used to apply the configurations namely, no qbv(No Traffic control),
qbv1(Iperf control), qbv2(Video control) and plots the graph in the UI,
Iperf and FPS vs time is plotted.
"""

import os
import gi
import time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_gtk3agg import FigureCanvasGTK3Agg as FigureCanvas
from itertools import count
from matplotlib.animation import FuncAnimation
from matplotlib.figure import Figure

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gio

figure = Figure(figsize=(8, 8), dpi=100)
ax1 = figure.add_subplot()
x_axis = []
y1_axis = []
y2_axis = []
index = count()
ax2 = ax1.twinx()


class ButtonWindow(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_border_width(10)
        self.set_resizable(False)
        hb = Gtk.HeaderBar()
        hb.props.title = "TSN 802.1Qbv"
        self.set_titlebar(hb)
        quit_button = Gtk.Button()
        quit_button.connect("clicked", exit)
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        self.set_titlebar(hb)
        quit_button.add(quit_image)
        hb.pack_end(quit_button)
        liststore = Gtk.ListStore(str)
        for item in [
            "No qbv (No Prioritization)",
            "Qbv1 (Video Prioritization)",
            "Qbv2 (Iperf Prioritization)",
        ]:
            liststore.append([item])
        combobox = Gtk.ComboBox()
        combobox.set_model(liststore)
        combobox.set_active(0)
        combobox.connect("changed", self.on_combobox_changed)
        hb.add(combobox)
        cellrenderertext = Gtk.CellRendererText()
        combobox.pack_start(cellrenderertext, True)
        combobox.add_attribute(cellrenderertext, "text", 0)

    def on_combobox_changed(self, combobox):
        treeiter = combobox.get_active_iter()
        model = combobox.get_model()
        if model[treeiter][0] == "No qbv (No Prioritization)":
            os.system(
                "python3 /home/root/.nxp-demo-experience/scripts/TSN/qbv/tsnqbv.py no_qbv root 192.168.0.1 &"
            )
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Note: No-Qbv (No Prioritization)",
            )
            dialog.format_secondary_text(
                "Iperf and Camera traffic share the link bandwidth.The 1Gbps link bandwidth allows camera streaming to work even though this traffic can be delayed in a non-deterministic manner by iperf traffic sharing the link. Any such delays are not noticeable visually due to buffering and loss concealment of the video itransport stream."
            )
            dialog.run()
            dialog.destroy()
        if model[treeiter][0] == "Qbv1 (Video Prioritization)":
            os.system(
                "python3 /home/root/.nxp-demo-experience/scripts/TSN/qbv/tsnqbv.py qbv1 root 192.168.0.1 &"
            )
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Note: Qbv1 (Video Prioritization)",
            )
            dialog.format_secondary_text(
                "Iperf traffic is limited to half the bandwidth,\nthe other half is available for the camera stream."
            )
            dialog.run()
            dialog.destroy()
        if model[treeiter][0] == "Qbv2 (Iperf Prioritization)":
            os.system(
                "python3 /home/root/.nxp-demo-experience/scripts/TSN/qbv/tsnqbv.py qbv2 root 192.168.0.1 &"
            )
            dialog = Gtk.MessageDialog(
                transient_for=self,
                flags=0,
                message_type=Gtk.MessageType.INFO,
                buttons=Gtk.ButtonsType.OK,
                text="Note: Qbv2 (Iperf Prioritization)",
            )
            dialog.format_secondary_text(
                "Iperf traffic is allocated nearly full bandwidth and\nfor the remainder, iperf contends with the camera stream."
            )
            dialog.run()
            dialog.destroy()


def animate(i, x_axis: list, y1_axis: list, y2_axis: list):
    try:
        Local_time = time.localtime()
        _Time = time.strftime("%H:%M:%S", Local_time)
        x_axis.append(_Time)
        iperf_result = open(
            "/home/root/.nxp-demo-experience/scripts/TSN/qbv/iperf.txt", "r"
        ).readlines()
        iperf_result = iperf_result[-1]
        iperf_result = iperf_result.split()
        if "received" in iperf_result:
            pass
        else:
            iperf_result = iperf_result[
                iperf_result.index("MBytes") + 1 or iperf_result.index("Bytes") + 1
            ]
            iperf_result1 = open(
                "/home/root/.nxp-demo-experience/scripts/TSN/qbv/iperf1.txt", "w"
            )
            iperf_result1.write(iperf_result)
            iperf_result1.close()
        iperf = open(
            "/home/root/.nxp-demo-experience/scripts/TSN/qbv/iperf1.txt", "r"
        ).readlines()
        iperf = iperf[0].strip()
        iperf = float(iperf)
        FPS = open(
            "/home/root/.nxp-demo-experience/scripts/TSN/qbv/FPS.txt", "r"
        ).readlines()
        FPS = FPS[0].strip()
        FPS = float(FPS)
        y1_axis.append(iperf)
        y2_axis.append(FPS)
        x_axis = x_axis[-8:]
        y1_axis = y1_axis[-8:]
        y2_axis = y2_axis[-8:]
        ax1.clear()
        ax2.clear()
        ax1.plot(
            x_axis,
            y1_axis,
            "go-",
            linewidth=1,
            markersize=3,
            label="Iperf(Mbps)=%.0f" % (iperf),
        )
        plt.setp(ax1.get_xticklabels(), rotation=30, horizontalalignment="right")
        ax2.plot(
            x_axis, y2_axis, "bo-", linewidth=1, markersize=3, label="FPS=%.2f" % (FPS)
        )
        lns = ax1.get_lines() + ax2.get_lines()
        labs = [l.get_label() for l in lns]
        ax1.legend(lns, labs, loc="upper right", bbox_to_anchor=(0.75, 1.08), ncol=2)
        ax1.set_xlabel("Time")
        ax1.set_ylim([0, 1000])
        ax2.set_ylim([0, 150])
        ax1.set_ylabel("IPERF", color="g")
        ax2.set_ylabel("FPS", color="b")
    except:
        print("FPS is not updated at this point")


canvas = FigureCanvas(figure)
canvas.set_size_request(750, 750)
ani = FuncAnimation(
    figure, animate, fargs=(x_axis, y1_axis, y2_axis), interval=1000, blit=False
)
win = ButtonWindow()
win.add(canvas)
win.show_all()
Gtk.main()
