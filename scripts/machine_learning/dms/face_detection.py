#!/usr/bin/env python3

"""
Copyright © 2021 Patrick Levin
Copyright 2022-2024 NXP

SPDX-License-Identifier: MIT
Original Source: https://github.com/patlevin/face-detection-tflite

This script define class of face detection used in DMS demo
"""
import time
import numpy as np
import cv2
import tflite_runtime.interpreter as tflite

# score limit is 100 in mediapipe and leads to overflows with IEEE 754 floats
# this lower limit is safe for use with the sigmoid functions and float32
RAW_SCORE_LIMIT = 80

# NMS similarity threshold
MIN_SUPPRESSION_THRESHOLD = 0.5


def sigmoid(x):
    """Apply the sigmoid function on the input x"""
    return 1 / (1 + np.exp(-x))


class FaceDetector:
    """The class to do face dectcion"""

    def __init__(self, model_path, inf_device, platform, threshold=0.75):
        """
        Creates an instance of the face detector

        Arguments:
        model_path -- the path to the model
        inf_device -- the inference device, CPU or NPU
        platform -- the plaform that running this demo
        threshold -- the threshold for confidence scores
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
            # inf_device is CPU
            self.interpreter = tflite.Interpreter(model_path=model_path)

        self.interpreter.allocate_tensors()

        # model warm up
        time_start = time.time()
        self.interpreter.invoke()
        time_end = time.time()
        print("face detection model warm up time:")
        print((time_end - time_start) * 1000, " ms")

        self.input_index = self.interpreter.get_input_details()[0]["index"]
        self.input_shape = self.interpreter.get_input_details()[0]["shape"]
        self.bbox_index = self.interpreter.get_output_details()[1]["index"]
        self.score_index = self.interpreter.get_output_details()[0]["index"]

        # (reference: modules/face_detection/face_detection_short_range_common.pbtxt)
        self.ssd_opts = {
            "num_layers": 4,
            "input_size_height": 128,
            "input_size_width": 128,
            "anchor_offset_x": 0.5,
            "anchor_offset_y": 0.5,
            "strides": [8, 16, 16, 16],
            "interpolated_scale_aspect_ratio": 1.0,
        }

        self.anchors = self._ssd_generate_anchors(self.ssd_opts)
        self.threshold = threshold

    def _pre_processing(self, input_data):
        """Preprocessing the input_data for the model"""
        input_data = cv2.cvtColor(input_data, cv2.COLOR_BGR2RGB)
        input_data = cv2.resize(input_data, self.input_shape[1:3]).astype(np.float32)
        input_data = (input_data[np.newaxis, :, :, :] - 128) / 128.0
        return input_data

    def detect(self, img):
        """Detect the face from img and return the bounding box"""
        input_data = self._pre_processing(img)
        self.interpreter.set_tensor(self.input_index, input_data)
        self.interpreter.invoke()
        raw_boxes = self.interpreter.get_tensor(self.bbox_index)
        raw_scores = self.interpreter.get_tensor(self.score_index)

        boxes = self._decode_boxes(raw_boxes)
        scores = self._get_sigmoid_scores(raw_scores)

        score_above_threshold = scores > self.threshold
        filtered_boxes = boxes[np.argwhere(score_above_threshold)[:, 1], :]
        filtered_scores = scores[score_above_threshold]

        output_boxes = np.array(
            self._non_maximum_suppression(
                filtered_boxes, filtered_scores, MIN_SUPPRESSION_THRESHOLD
            )
        )

        return output_boxes

    def _overlap_similarity(self, box1, box2):
        """Return intersection-over-union similarity of two bounding boxes"""
        if box1 is None or box2 is None:
            return 0
        x1_min, y1_min, x1_max, y1_max = box1
        x2_min, y2_min, x2_max, y2_max = box2
        box1_area = (x1_max - x1_min) * (y1_max - y1_min)
        box2_area = (x2_max - x2_min) * (y2_max - y2_min)
        x3_min = max(x1_min, x2_min)
        x3_max = min(x1_max, x2_max)
        y3_min = max(y1_min, y2_min)
        y3_max = min(y1_max, y2_max)
        intersect_area = (x3_max - x3_min) * (y3_max - y3_min)
        denominator = box1_area + box2_area - intersect_area
        return intersect_area / denominator if denominator > 0.0 else 0.0

    def _non_maximum_suppression(self, boxes, scores, min_suppression_threshold):
        """Return only the most significant detections"""
        candidates_list = []
        for i in range(np.size(boxes, 0)):
            candidates_list.append((boxes[i], scores[i]))
        candidates_list = sorted(candidates_list, key=lambda x: x[1], reverse=True)
        kept_list = []
        for sorted_boxes, sorted_scores in candidates_list:
            suppressed = False
            for kept in kept_list:
                similarity = self._overlap_similarity(kept, sorted_boxes)
                if similarity > min_suppression_threshold:
                    suppressed = True
                    break
            if not suppressed:
                kept_list.append(sorted_boxes)
        return kept_list

    def _decode_boxes(self, raw_boxes: np.ndarray) -> np.ndarray:
        """
        Simplified version of
        mediapipe/calculators/tflite/tflite_tensors_to_detections_calculator.cc
        """
        # width == height so scale is the same across the board
        scale = self.input_shape[1]
        num_points = raw_boxes.shape[-1] // 2
        # scale all values (applies to positions, width, and height alike)
        boxes = raw_boxes.reshape(-1, num_points, 2) / scale
        # adjust center coordinates and key points to anchor positions
        boxes[:, 0] += self.anchors
        for i in range(2, num_points):
            boxes[:, i] += self.anchors
        # convert x_center, y_center, w, h to xmin, ymin, xmax, ymax
        center = np.array(boxes[:, 0])
        half_size = boxes[:, 1] / 2
        boxes[:, 0] = center - half_size
        boxes[:, 1] = center + half_size

        # only need boxes xmin, ymin, xmax, ymax
        boxes = boxes[:, 0:2, :].reshape(-1, 4)
        return boxes

    def _get_sigmoid_scores(self, raw_scores: np.ndarray) -> np.ndarray:
        """
        Extracted loop from ProcessCPU (line 327) in
        mediapipe/calculators/tflite/tflite_tensors_to_detections_calculator.cc
        """
        # just a single class ("face"), which simplifies this a lot
        # 1) thresholding; adjusted from 100 to 80, since sigmoid of [-]100
        #    causes overflow with IEEE single precision floats (max ~10e38)
        raw_scores[raw_scores < -RAW_SCORE_LIMIT] = -RAW_SCORE_LIMIT
        raw_scores[raw_scores > RAW_SCORE_LIMIT] = RAW_SCORE_LIMIT
        # 2) apply sigmoid function on clipped confidence scores
        return sigmoid(raw_scores)

    def _ssd_generate_anchors(self, opts: dict) -> np.ndarray:
        """
        This is a trimmed down version of the C++ code; all irrelevant parts
        have been removed.
        (reference: mediapipe/calculators/tflite/ssd_anchors_calculator.cc)
        """
        layer_id = 0
        num_layers = opts["num_layers"]
        strides = opts["strides"]
        assert len(strides) == num_layers
        input_height = opts["input_size_height"]
        input_width = opts["input_size_width"]
        anchor_offset_x = opts["anchor_offset_x"]
        anchor_offset_y = opts["anchor_offset_y"]
        interpolated_scale_aspect_ratio = opts["interpolated_scale_aspect_ratio"]
        anchors = []
        while layer_id < num_layers:
            last_same_stride_layer = layer_id
            repeats = 0
            while (
                last_same_stride_layer < num_layers
                and strides[last_same_stride_layer] == strides[layer_id]
            ):
                last_same_stride_layer += 1
                # aspect_ratios are added twice per iteration
                repeats += 2 if interpolated_scale_aspect_ratio == 1.0 else 1
            stride = strides[layer_id]
            feature_map_height = input_height // stride
            feature_map_width = input_width // stride
            for y in range(feature_map_height):
                y_center = (y + anchor_offset_y) / feature_map_height
                for x in range(feature_map_width):
                    x_center = (x + anchor_offset_x) / feature_map_width
                    for _ in range(repeats):
                        anchors.append((x_center, y_center))
            layer_id = last_same_stride_layer
        return np.array(anchors, dtype=np.float32)
