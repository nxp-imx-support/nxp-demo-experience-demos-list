#!/usr/bin/env python3

"""
Copyright 2022-2024 NXP
SPDX-License-Identifier: BSD-3-Clause

This script define class of Eye used in DMS demo
"""
import time
import math
import numpy as np
import cv2
import tflite_runtime.interpreter as tflite


class Eye:
    """
    This class uses 468 points of face landmark and iris detection model
    from mediapipe to get 71 normalized eye contour landmarks and a
    separate list of 5 normalized iris landmarks.
    """

    LEFT_EYE_START = 33
    LEFT_EYE_END = 133
    RIGHT_EYE_START = 362
    RIGHT_EYE_END = 263
    ROI_SCALE = 2

    EYE_LANDMARK_CONNECTIONS = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 4),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 8),
        (9, 10),
        (10, 11),
        (11, 12),
        (12, 13),
        (13, 14),
        (0, 9),
        (8, 14),
    ]

    def __init__(self, model_path, inf_device, platform):
        """
        Creates an instance of the Eye class

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
        print("iris landmark model warm up time:")
        print((time_end - time_start) * 1000, " ms")

        self.input_index = self.interpreter.get_input_details()[0]["index"]
        self.input_shape = self.interpreter.get_input_details()[0]["shape"]
        self.eye_index = self.interpreter.get_output_details()[0]["index"]
        self.iris_index = self.interpreter.get_output_details()[1]["index"]

    def get_eye_roi(self, face_landmarks, side):
        """Get the left/right eye's ROI position from face landmarks' position"""
        if side == 0:
            x1, y1 = face_landmarks[self.LEFT_EYE_START]
            x2, y2 = face_landmarks[self.LEFT_EYE_END]
        else:
            x1, y1 = face_landmarks[self.RIGHT_EYE_START]
            x2, y2 = face_landmarks[self.RIGHT_EYE_END]

        mid_point_x = int((x1 + x2) / 2)
        mid_point_y = int((y1 + y2) / 2)
        half_eye_width = int((x2 - x1) / 2)
        roi_xmin = int(mid_point_x - self.ROI_SCALE * half_eye_width)
        roi_xmax = int(mid_point_x + self.ROI_SCALE * half_eye_width)
        roi_ymin = int(mid_point_y - self.ROI_SCALE * half_eye_width)
        roi_ymax = int(mid_point_y + self.ROI_SCALE * half_eye_width)
        return roi_xmin, roi_ymin, roi_xmax, roi_ymax

    def _pre_processing(self, input_data):
        """Preprocessing the input_data for the model"""
        input_data = cv2.cvtColor(input_data, cv2.COLOR_BGR2RGB)
        input_data = cv2.resize(input_data, self.input_shape[1:3]).astype(np.float32)
        input_data = (input_data[np.newaxis, :, :, :] - 128) / 128.0
        return input_data

    def get_landmark(self, frame, roi, side):
        """Get the eye and iris landmarks from frame, return two lists of landmarks' position"""
        if side == 1:
            frame = cv2.flip(frame, 1)
        input_data = self._pre_processing(frame)
        self.interpreter.set_tensor(self.input_index, input_data)
        self.interpreter.invoke()
        eye_points = self.interpreter.get_tensor(self.eye_index)
        iris_points = self.interpreter.get_tensor(self.iris_index)

        eye_points = eye_points.reshape(-1, 3)
        iris_points = iris_points.reshape(-1, 3)
        height, width = self.input_shape[1:3]

        eye_points /= (width, height, width)
        iris_points /= (width, height, width)
        if side == 1:
            eye_points[:, 0] *= -1
            eye_points[:, 0] += 1
            iris_points[:, 0] *= -1
            iris_points[:, 0] += 1

        xmin, ymin, xmax, ymax = roi
        roi_width = xmax - xmin
        roi_height = ymax - ymin

        eye_landmarks = []
        iris_landmarks = []
        for i in range(np.size(eye_points, 0)):
            x1 = int(eye_points[i][0] * roi_width + xmin)
            y1 = int(eye_points[i][1] * roi_height + ymin)
            eye_landmarks.append([x1, y1])
        for i in range(np.size(iris_points, 0)):
            x1 = int(iris_points[i][0] * roi_width + xmin)
            y1 = int(iris_points[i][1] * roi_height + ymin)
            iris_landmarks.append([x1, y1])

        return eye_landmarks, iris_landmarks

    def draw_eye_contour(self, frame, eye_landmarks):
        """Draw the eye contour on the frame"""
        for connection in self.EYE_LANDMARK_CONNECTIONS:
            idx1, idx2 = connection
            cv2.line(
                frame,
                tuple(eye_landmarks[idx1]),
                tuple(eye_landmarks[idx2]),
                (255, 0, 0),
                thickness=2,
            )
        return frame

    def blinking_ratio(self, landmarks, side):
        """Calculates a ratio that can indicate whether an eye is closed or not.
        It's calculating the absolute differenc between eye area's color to the
        skin color that at eye edge

        Arguments:
            landmarks : 468 points Facial landmarks of the face region
            side : 0 means left side, 1 means right side

        Returns:
            The computed ratio
        """
        if side == 0:
            point_left = landmarks[0]
            point_right = landmarks[8]
        else:
            point_left = landmarks[8]
            point_right = landmarks[0]

        point_top = landmarks[12]
        point_bottom = landmarks[4]

        eye_width = math.hypot(
            (point_right[0] - point_left[0]), (point_right[1] - point_left[1])
        )
        eye_height = math.hypot(
            (point_bottom[0] - point_top[0]), (point_bottom[1] - point_top[1])
        )

        try:
            ratio = eye_height / eye_width
        except ZeroDivisionError:
            ratio = 0

        return ratio
