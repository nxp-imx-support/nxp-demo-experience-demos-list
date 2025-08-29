# Copyright 2025 NXP
# SPDX-License-Identifier: BSD-3-Clause

import sys
import os
import numpy as np
import tflite_runtime.interpreter as tflite
import csv
import wave
import math
import time
import struct
import gi
import glob
import threading
import subprocess

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

#check scipy package
def check_and_install_scipy():
    try:
        import scipy
        print("scipy is already installed.")
    except ImportError:
        print("scipy is not installed. Installing now...")
        try:
            subprocess.check_call(["pip3", "install", "scipy"])
            print("scipy has been successfully installed.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install scipy. Error: {e}")
            sys.exit(1)

sys.path.append("/opt/gopoint-apps/scripts/")
check_and_install_scipy()
import scipy.signal
from scipy.io import wavfile
import acc
import utils


#find the sound_card
sound_card = "0"
snd_card_str = os.popen("arecord -l").read()
snd_idx = snd_card_str.find("micfilaudio")
if snd_idx != -1:
    sound_card = snd_card_str[snd_idx - 3]
    print("Using sound card " + sound_card)

class StartWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Snoring Detection Demo")
        self.set_default_size(700, 300)
        self.set_resizable(False)
        self.flag = threading.Event()
        self.flag.set()
        self.running = threading.Event()
        self.running.set()

        button_record = Gtk.Button(label="Record audio")
        button_record.connect("clicked", self.record_audio)
        button_snoring_detect = Gtk.Button(label="Snoring Detect")
        button_snoring_detect.connect("clicked", self.start)
        button_stop_demo = Gtk.Button(label="Stop Snoring Detect")
        button_stop_demo.connect("clicked", self.stop)

        self.audio_file_select = Gtk.ComboBoxText()
        self.audio_file_select.set_entry_text_column(0)
        self.audio_file_select.set_hexpand(False)
        for audio_file in glob.glob('/opt/gopoint-apps/downloads/*.wav'):
            self.audio_file_select.append_text(audio_file)
        for audio_file in glob.glob('./*.wav'):
            self.audio_file_select.append_text(audio_file)
        self.audio_file_select.append_text("None wav files")
        self.audio_file_select.set_active(0)

        file_label = Gtk.Label(label="Select target audio file")
        file_label.set_size_request(200,30)
        console_label = Gtk.Label(label="Output Console")
        console_label.set_size_request(340,30)
        console_label.set_justify(Gtk.Justification.FILL)
        sep = Gtk.Label(label=" ")
        sep.set_size_request(200,100)
        sep1 = Gtk.Label(label=" ")
        sep1.set_size_request(100,30)
        self.log_label = Gtk.Label(label="Snoring Detection Demo")
        self.log_label.set_justify(Gtk.Justification.LEFT)
        self.log_label.set_line_wrap(True)
        self.log_label.set_max_width_chars(100)

        grid = Gtk.Grid()
        grid.set_margin_start(30)
        grid.set_margin_end(30)
        grid.set_margin_top(30)
        grid.set_margin_bottom(30)
        grid.attach(file_label, 0, 0, 1, 1)
        grid.attach(self.audio_file_select, 0, 1, 1, 1)
        grid.attach(sep, 0, 2, 1, 1)
        grid.attach(button_record, 0, 3, 1, 1)
        grid.attach(button_snoring_detect, 0, 4, 1, 1)
        grid.attach(button_stop_demo, 0, 6, 1, 1)
        grid.attach(sep1, 1, 0, 1, 1)
        grid.attach(console_label, 2, 0, 1, 1)
        grid.attach(self.log_label, 2, 1, 1, 4)

        self.add(grid)
        
        self.model = "/opt/gopoint-apps/downloads/snoring_detect.tflite"
        self.audio_file = "my_record.wav"
        self.interpreter = tflite.Interpreter(model_path=self.model)
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()

        self.output_log = ""
        self.waveform = None
        self.output_data = None
        self.show_all()
    
    def record_audio(self, unused):
        self.log_label.set_text("Start recording audio for 1 seconds...")
        GLib.idle_add(os.system, "arecord -D hw:"+sound_card+",0 -r 16000 -f S32_LE -c 1 -d 1 my_record.wav")
        GLib.idle_add(self.log_label.set_text, "Recording finished, saved in my_record.wav")
        self.audio_file_select.append_text("my_record.wav")
 
    def convert_audio_format(self, input_file, output_file):
        with wave.open(input_file, 'rb') as wav_in:
            params = wav_in.getparams()
            sample_width = wav_in.getsampwidth()

            if sample_width != 4:
                print("Input audio file is not in S32_LE format.")
                return

            with wave.open(output_file, 'wb') as wav_out:
                wav_out.setparams(params)
                wav_out.setsampwidth(2)  # Set sample width to 2 bytes for S16_LE format

                for _ in range(wav_in.getnframes()):
                    frame = wav_in.readframes(1)
                    data_s32le = struct.unpack('<l', frame)[0]  # Unpack 32-bit signed integer
                    data_s16le = max(-32768, min(data_s32le // 65536, 32767))  # Convert to 16-bit signed integer
                    data_s16le_bytes = struct.pack('<h', data_s16le)  # Pack as 16-bit signed integer
                    wav_out.writeframes(data_s16le_bytes)

        print("Audio format conversion completed.")

    def predict_audio(self, audio_file):
        self.output_log = ""
        mfcc_feat = acc.analyze_audio(audio_file)
        classifier = acc.SoundClassifier(model_path="/opt/gopoint-apps/downloads/snoring_detect.tflite")
        inference_time = time.monotonic()
        predicted_label = classifier.predict(mfcc_feat)
        print("Inference time: " + str(time.monotonic() - inference_time) + " s")
        print(predicted_label)
        self.output_log += "Inference time: " + str(time.monotonic() - inference_time) + " s\n"
        self.output_log += "Predicted Label: " + predicted_label + "\n"
        GLib.idle_add(self.log_label.set_text, self.output_log)
   
    def inference_run(self):
        while self.running.is_set():
            subprocess.run("arecord -D hw:"+sound_card+",0 -r 16000 -f S32_LE -c 1 -d 1 my_record.wav", shell=True)
            self.convert_audio_format('my_record.wav', 'my_record_s16.wav')
            self.predict_audio('my_record_s16.wav')
            time.sleep(1)
            print("Running loop...")

    def start(self, unused):
        self.audio_file = self.audio_file_select.get_active_text()
        if self.audio_file:
            if os.path.exists(self.audio_file):
                #self.output_log = ""
                with wave.open(self.audio_file, 'rb') as wav_in:
                    params = wav_in.getparams()
                    sample_width = wav_in.getsampwidth()
                    if sample_width == 2:
                        self.output_log += "Input audio file is S16_LE format.\n"
                        print("Input audio file is S16_LE format.")
                        self.predict_audio(self.audio_file)
                    if sample_width == 4:
                        self.output_log += "Input audio file is S32_LE format.\n"
                        print("Input audio file is S32_LE format.")
                        self.convert_audio_format(self.audio_file, 'my_record_s16.wav')
                        self.predict_audio('my_record_s16.wav')
                self.log_label.set_text(self.output_log)
            else:
                self.running.set()
                t = threading.Thread(target=self.inference_run, daemon=True)              
                if not t.is_alive():
                    t.start()
                else:
                    self.log_label.set_text("Snoring Detection is already running")

    def stop(self, unused):
        self.flag.set()
        self.running.clear()    
        self.log_label.set_text("Stop Running the Demo")
    
if __name__ == '__main__':
    os.system('echo "\nStart demo" > /dev/console')
    os.system('echo "Downloading machine learning file & audio files..." > /dev/console')
    ml_model = utils.download_file("snoring_detect.tflite")
    if ml_model == -1:
        os.system('echo "Cannot find files!" > /dev/console')
        os.system('echo "Make sure required files are available in downloads database!" > /dev/console')
        sys.exit(1)
    if ml_model == -2:
        os.system('echo "Download failed!" > /dev/console')
        os.system('echo "Please make sure you have internet connection on the target and try again." > /dev/console')
        sys.exit(1)
    if ml_model == -3:
        os.system('echo "Downloaded corrupted file!" > /dev/console')
        os.system('echo "Please clean /opt/gopoint-apps/downloads/ and try to download again." > /dev/console')
        sys.exit(1)
    window = StartWindow()
    window.connect("destroy", Gtk.main_quit)
    window.show_all()
    Gtk.main()
