# Copyright 2022 NXP Semiconductors
# SPDX-License-Identifier: BSD-3-Clause

import numpy as np
import cv2
import tflite_runtime.interpreter as tflite
import time

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

class YoloFace(object):
    def __init__(self, model_path, threshold = 0.75):
        self.interpreter = tflite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        self.ips = "N/A IPS"

        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        self.input_shape = self.input_details[0]['shape'][1:3]
        self.threshold = threshold

    def detect(self, img):
        input_data = self._pre_processing(img)
        self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
        self.interpreter.invoke()
        output_data = self.interpreter.get_tensor(self.output_details[0]['index'])
        return self._post_processing(output_data)

    def _pre_processing(self, input_data):
        input_data = cv2.cvtColor(input_data, cv2.COLOR_BGR2RGB)
        input_data = cv2.resize(input_data, self.input_shape).astype(np.float32)
        input_data = (input_data[np.newaxis,:,:,:] - 128).astype(np.int8)
        return input_data

    def _post_processing(self, output_data):
        output = output_data[0].astype(np.float32)
        output = (output + 15) * 0.14218327403068542
        nx,ny,_ = output.shape
        anchors = np.zeros([3, 1, 1, 2], dtype=np.float32)
        anchors[0,0,0,:] = [9, 14]
        anchors[1,0,0,:] = [12, 17]
        anchors[2,0,0,:] = [22, 21]
        output = output.reshape((7,7,3,6)).transpose([2,0,1,3])
        yv, xv = np.meshgrid(np.arange(ny), np.arange(nx))
        grid = np.stack((yv, xv), 2).reshape((1, ny, nx, 2)).astype(np.float32)
        output[..., 0:2] = (sigmoid(output[..., 0:2]) + grid) * 8
        output[..., 2:4] = np.exp(output[..., 2:4]) * anchors
        output[..., 4:] = sigmoid(output[..., 4:])

        #non max suppression
        prediction = output.reshape((-1, 6))
        x = prediction[prediction[..., 4] > self.threshold]
        if not x.shape[0]:
            return []
        x = x[:, :4]
        boxes = np.zeros(x.shape, dtype=np.float32)
        boxes[..., 0] = (x[..., 0] - x[..., 2] / 2) / self.input_shape[1]
        boxes[..., 1] = (x[..., 1] - x[..., 3] / 2) / self.input_shape[0]
        boxes[..., 2] = (x[..., 0] + x[..., 2] / 2) / self.input_shape[1]
        boxes[..., 3] = (x[..., 1] + x[..., 3] / 2) / self.input_shape[0]
        return boxes


