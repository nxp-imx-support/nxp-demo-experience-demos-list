#!/usr/bin/env python3

"""
Copyright 2022-2024 NXP
SPDX-License-Identifier: BSD-3-Clause

This script define class of face landmark used in DMS demo
"""
import time
import numpy as np
import cv2
import tflite_runtime.interpreter as tflite


class FaceLandmark:
    """The class to get face landmark"""

    def __init__(self, model_path, inf_device, platform):
        """
        Creates an instance of the face landmark class

        Arguments:
        model_path -- the path to the model
        inf_device -- the inference device, CPU or NPU
        platform -- the plaform that running this demo
        """
        if inf_device == "NPU":
            if platform == "i.MX8MP":
                delegate = tflite.load_delegate("/usr/lib/libvx_delegate.so")
            elif platform == "i.MX93":
                delegate = tflite.load_delegate("/usr/lib/libethosu_delegate.so")
            else:
                print("Platform not supported!")
                return
            self.interpreter = tflite.Interpreter(
                model_path=model_path, experimental_delegates=[delegate]
            )
        else:
            self.interpreter = tflite.Interpreter(model_path=model_path)

        self.interpreter.allocate_tensors()

        # model warm up
        time_start = time.time()
        self.interpreter.invoke()
        time_end = time.time()
        print("face landmark model warm up time:")
        print((time_end - time_start) * 1000, " ms")

        self.input_index = self.interpreter.get_input_details()[0]["index"]
        self.input_shape = self.interpreter.get_input_details()[0]["shape"]
        self.landmark_index = self.interpreter.get_output_details()[1]["index"]
        self.score_index = self.interpreter.get_output_details()[0]["index"]

    def _pre_processing(self, input_data):
        """Preprocessing the input_data for the model"""
        input_data = cv2.cvtColor(input_data, cv2.COLOR_BGR2RGB)
        input_data = cv2.resize(input_data, self.input_shape[1:3]).astype(np.float32)
        input_data = (input_data[np.newaxis, :, :, :] - 128) / 128.0
        return input_data

    def get_landmark(self, img, roi):
        """Get the face landmarks from img, return a list of all landmarks' position"""
        input_data = self._pre_processing(img)
        self.interpreter.set_tensor(self.input_index, input_data)
        self.interpreter.invoke()
        raw_landmarks = self.interpreter.get_tensor(self.landmark_index)[0]

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
