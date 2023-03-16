"""
Copyright 2023 NXP

SPDX-License-Identifier: BSD-3-Clause

This script provides the UI to the user, showcasing the setup diagram,
camera to be selected, ensuring the setup connectivity and starts the demo.
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, Gio
import os, sys
list1 = ["Fail", "Fail"]

class DialogWindow(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self)
        self.set_border_width(10)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.CENTER)  
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add(box)
        self.connect("destroy", Gtk.main_quit)		
        header = Gtk.HeaderBar()
        header.props.title = "TSN 802.1Qbv"
        quit_button = Gtk.Button()
        quit_button.connect("clicked", self.on_stop_clicked)
        quit_icon = Gio.ThemedIcon(name="process-stop-symbolic")
        quit_image = Gtk.Image.new_from_gicon(quit_icon, Gtk.IconSize.BUTTON)
        self.set_titlebar(header)
        quit_button.add(quit_image)
        header.pack_end(quit_button)
        label2 = Gtk.Label(label= "TSN 802.1 Qbv - Enhancements to Traffic Scheduling\nTime-Aware Shaper - It separates communication on the Ethernet network into a fixed length, repeating time cycles,\n thereby contributing to the delivery of time-critical traffic.")
        box.add(label2)
        pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(filename="/home/root/.nxp-demo-experience/scripts/TSN/qbv/TSN_Qbv_setup_diagram.png",width=850,height=200,preserve_aspect_ratio=False)
        image = Gtk.Image.new_from_pixbuf(pixbuf)
        box.add(image)
        label3 = Gtk.Label("Video source:")
        videos= [
                "/dev/video0",
                "/dev/video1",
                "/dev/video2",
                "/dev/video3",
                "/dev/video4",
                "/dev/video5",
                ]
        video_combo = Gtk.ComboBoxText()
        video_combo.set_entry_text_column(0)
        video_combo.connect("changed", self.on_video_combo_changed)
        for video in videos:
            video_combo.append_text(video)

        video_combo.set_active(0)
        vbox = Gtk.HBox()
        vbox.add(label3)
        vbox.add(video_combo)
        button1 = Gtk.Button(label="Check Connection")                                                                                        
        button1.connect("clicked", self.on_connection_clicked)                                                                                       
        button2 = Gtk.Button(label="Run Demo")
        button2.connect("clicked", self.on_run_clicked) 
        button3 = Gtk.Button(label="Stop Demo")
        button3.connect("clicked",self.on_stop_clicked)
        box.add(vbox)
        box.add(button1)
        box.add(button2)
        box.add(button3)

    def on_video_combo_changed(self, combo):
        text = combo.get_active_text()
        if text is not None:
            print("Selected: Video=%s" % text)
        y = open('/home/root/.nxp-demo-experience/scripts/TSN/qbv/video.txt','w')
        y.write(text)
        y.close()
        list1[0] = "Pass"
    def on_run_clicked(self, button):
        if (list1[0] == "Pass" and list1[1] == "Pass"):
              os.system("python3 /home/root/.nxp-demo-experience/scripts/TSN/qbv/tsnqbv.py start root 192.168.0.1 &")
              dialog = Gtk.MessageDialog(                                                                                                     
                      transient_for=self,                                                                                                  
                      flags=0,                                                
                      message_type=Gtk.MessageType.INFO,                                                   
                      buttons=Gtk.ButtonsType.OK,                                                          
                      text="Notification",                                                                                                 
                      )                                                                                                                    
              dialog.format_secondary_text(                                                                                                   
                      "Demo is starting please wait"                                                                            
                      )                                                                                               
              dialog.run()                                                                                                                    
              dialog.destroy()
              button.set_visible(False)
              print("INFO dialog closed")
        else:
              dialog = Gtk.MessageDialog(
                      transient_for=self,
                      flags=0,
                      message_type=Gtk.MessageType.INFO,
                      buttons=Gtk.ButtonsType.OK,
                      text="Notification",
                      )
              dialog.format_secondary_text(
                      "Please check the connections or video source."
                      )
              dialog.run()
              dialog.destroy() 
    def on_check_clicked(self, button):
        button.set_label("Checking Connection...")
        print("Checking connection")
    def on_stop_clicked(self, button):
        print("Stopping demo")
        os.system("python3 /home/root/.nxp-demo-experience/scripts/TSN/qbv/tsnqbv.py stop root 192.168.0.1 &")

    def on_connection_clicked(self, widget):
        a = os.popen("cat /sys/class/net/eth0/operstate").read()
        b = os.popen("cat /sys/class/net/eth1/operstate").read()

        if ( a == "up\n" and b == "up\n"):
            dialog = Gtk.MessageDialog(transient_for=self,flags=0,message_type=Gtk.MessageType.INFO,buttons=Gtk.ButtonsType.OK,text="Qbv Connection", )
            dialog.format_secondary_text("Connection established successfully")
            dialog.run()
            dialog.destroy()
            list1[1] = "Pass"
        else:
            dialog = Gtk.MessageDialog(
                    transient_for=self,
                    flags=0,
                    message_type=Gtk.MessageType.WARNING,
                    buttons=Gtk.ButtonsType.OK,
                    text="Warning",
                    )
            dialog.format_secondary_text(
                    "Please check the connections."
                    )
            dialog.run()
            dialog.destroy()

win = DialogWindow()
win.show_all()
Gtk.main()

