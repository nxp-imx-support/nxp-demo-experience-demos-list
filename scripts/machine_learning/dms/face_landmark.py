# Copyright 2022 NXP
# SPDX-License-Identifier: BSD-3-Clause

import numpy as np
import cv2
#import tensorflow.lite as tflite
import tflite_runtime.interpreter as tflite


class FaceLandmark(object):
    def __init__(self, model_path):
        self.interpreter = tflite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()

        self.input_index = self.interpreter.get_input_details()[0]['index']
        self.input_shape = self.interpreter.get_input_details()[0]['shape']
        self.landmark_index = self.interpreter.get_output_details()[1]['index']
        self.score_index = self.interpreter.get_output_details()[0]['index']


    def _pre_processing(self, input_data):
        input_data = cv2.cvtColor(input_data, cv2.COLOR_BGR2RGB)
        input_data = cv2.resize(input_data, self.input_shape[1:3]).astype(np.float32)
        input_data = (input_data[np.newaxis,:,:,:] / 255.0 - 0.5) * 2
        #input_data = (input_data[np.newaxis,:,:,:] - 128).astype(np.int8)
        return input_data


    def get_landmark(self, img, roi):
        input_data = self._pre_processing(img)
        self.interpreter.set_tensor(self.input_index, input_data)
        self.interpreter.invoke()
        raw_landmarks = self.interpreter.get_tensor(self.landmark_index)[0]
        raw_scores = self.interpreter.get_tensor(self.score_index)[0]

        raw_landmarks = raw_landmarks.astype(np.float32)
        raw_landmarks = np.reshape(raw_landmarks, (-1, 3))

        height, width = self.input_shape[1:3]
        xmin, ymin, xmax, ymax = roi
        roi_width = xmax - xmin
        roi_height = ymax - ymin

        output_landmarks = []
        for i in range(np.size(raw_landmarks, 0)):
            x = int((raw_landmarks[i][0] / width) * roi_width + xmin)
            y = int((raw_landmarks[i][1] / height) * roi_height + ymin)
            output_landmarks.append([x, y])

        return output_landmarks

