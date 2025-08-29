# Copyright 2025 NXP
# SPDX-License-Identifier: BSD-3-Clause

import tflite_runtime.interpreter as tflite
import numpy as np
import os
import scipy.io.wavfile as wavfile
import subprocess
import time
import wave
import sys

#from pydub import AudioSegment

def increase_volume(input_file, output_file, gain):
    audio = AudioSegment.from_file(input_file, format="wav")
    louder_audio = audio + gain
    louder_audio.export(output_file, format="wav")


def analyze_audio(wavefile):
    f = wave.open(wavefile, 'rb')
    params = f.getparams()
    nchannels, sampwidth, framerate, nframes = params[:4]

    print("channel %d, sample width %d, framerate %d, frames %d" % (nchannels, sampwidth, framerate, nframes))
    data_str = f.readframes(nframes)
    audio_data = np.frombuffer(data_str, dtype=np.int16)
    audio_data = audio_data / 32768.0

    spectrogram = np.zeros((49, 64), dtype=np.int8)
    for i in range(49):
        start_sample = (i) * int(framerate * 0.02)
        end_sample = start_sample + int(framerate * 0.032)
        audio_segment = audio_data[start_sample:end_sample]

        fft_data = np.fft.fft(audio_segment)
        if len(fft_data) != 512:
            print("sample number is not 512! Please check.")
            print(wavefile)
            break

        #normalize fft's amplitude by dividing N/2
        fft_data = np.abs(fft_data[:256]) * 2 / len(fft_data)
        fft_data[0] = 0
  
        n = len(fft_data) // 4 * 4
        fft_data = np.max(fft_data[:n].reshape(-1, 4), axis=1)


        #scale fft's value to 0-256.
        #From test, found that the max value is usually smaller than 0.390625
        #so scale fft's value from 0-0.390625 to 0-256
        
        fft_data = (fft_data / np.max(fft_data)) * 256
        
        #make sure fft's value is within 0-255, and then change to int8
        fft_data = (np.clip(fft_data, 0, 255) - 128).astype(np.int8)
        spectrogram[i] = fft_data
    return spectrogram
    f.close()

class SoundClassifier:
    def __init__(self, model_path):
        self.interpreter = tflite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        self.labels = ['snoring', 'no_snoring']

    def predict(self, spectrogram):
        input_data = np.array(spectrogram, dtype=self.input_details[0]['dtype'])
        input_data = input_data.reshape(1, 49, 64, 1)
        self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
        self.interpreter.invoke()
        output_data = self.interpreter.get_tensor(self.output_details[0]['index'])
        return self.labels[np.argmax(output_data)]

