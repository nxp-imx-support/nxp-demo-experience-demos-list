# Copyright 2025 NXP
# SPDX-License-Identifier: Apache-2.0
"""Performs palm detection in an input image."""
import csv

import numpy as np
import tflite_runtime.interpreter as tflite

from app_utils.utils_bboxes import PalmBbox


class PalmDetector:
    """Performs palm detection in an input image.

    This class provides an interface for detecting palms in images (the
    images must be square with a size of [256, 256] in the range [-1.0, 1.0]).

    This class processes input images, applies non-maximum supression (NMS)
    to filter redundant detections. and returns the most probable palm
    locations.

    Attributes:
        model (str): Path to the palm detection model.
        anchors (str): Path to the anchors.txt file.
        num_palms (int): Max number of palm detections the object can return
            (1 or 2).
        external_delegate (str or None): Path to an external delegate library,
            if used for hardware acceleration.
        palm_detection_conf (float): Minimum confidence score required to
            consider a palm detection as valid.
        min_suppr_thr (float): Minimum supression threshold for the non-max
            supression (NMS) algorithm.
    """

    def __init__(
        self,
        model,
        anchors,
        num_palms,
        external_delegate,
        palm_detection_conf,
        min_suppr_thr,
    ):
        """Initializates a PalmDetector instance.

        Attributes:
            model (str): Path to the palm detection model.
            anchors (str): Path to the anchors.txt file.
            num_palms (int): Max number of palm detections the object can return
                (1 or 2).
            external_delegate (str or None): Path to an external delegate library,
                if used for hardware acceleration.
            palm_detection_conf (float): Minimum confidence score required to
                consider a palm detection as valid.
            min_suppr_thr (float): Minimum supression threshold for the non-max
                supression (NMS) algorithm.
        """
        if external_delegate:
            external_delegate = [tflite.load_delegate(external_delegate)]

        self._interpreter = tflite.Interpreter(
            model, experimental_delegates=external_delegate
        )

        # Hyperparameters for palm detection task
        self._palm_detection_conf = palm_detection_conf
        self._min_supression_threshold = min_suppr_thr

        assert num_palms in [1, 2], "The number of palms must be 1 or 2"
        self._num_palms = num_palms

        # Read SSD anchors
        with open(anchors, "r", encoding="utf-8") as csv_file:
            self._anchors = np.r_[
                [line for line in csv.reader(csv_file, quoting=csv.QUOTE_NONNUMERIC)]
            ]

        self._interpreter.allocate_tensors()
        _out_details = self._interpreter.get_output_details()
        _in_details = self._interpreter.get_input_details()

        self._in_idx = _in_details[0]["index"]
        self._out_reg_idx = _out_details[1]["index"]
        self._out_clf_idx = _out_details[0]["index"]

        # Ignore the first invoke (Warm-up time)
        batch, width, height, channel = tuple(_in_details[0]["shape"].tolist())
        self._interpreter.set_tensor(
            self._in_idx, np.random.rand(batch, width, height, channel).astype("float32")
        )
        self._interpreter.invoke()

    def sigmoid(self, array):
        """Applies sigmoid function to an array."""
        # LIMIT_SCORE = 80 # To avoid overflows with IEEE 754
        # array[array > LIMIT_SCORE] = LIMIT_SCORE
        # array[array < -LIMIT_SCORE] = -LIMIT_SCORE
        return 1.0 / (1.0 + np.exp(-array))

    def _inter_over_union(self, bbox1, bbox2):
        """Calculates intersection over union score between two boxes."""
        if bbox1 is None or bbox2 is None:
            return 0.0

        x1_min, y1_min, x1_max, y1_max = bbox1.coordinates()
        x2_min, y2_min, x2_max, y2_max = bbox2.coordinates()

        box1_area = (x1_max - x1_min) * (y1_max - y1_min)
        box2_area = (x2_max - x2_min) * (y2_max - y2_min)

        x3_min = max(x1_min, x2_min)
        x3_max = min(x1_max, x2_max)
        y3_min = max(y1_min, y2_min)
        y3_max = min(y1_max, y2_max)

        intersect_area = (x3_max - x3_min) * (y3_max - y3_min)
        denominator = box1_area + box2_area - intersect_area
        return intersect_area / denominator if denominator > 0.0 else 0.0

    def _non_max_suppression(self, bboxes, min_suppression_threshold):
        """Non-maximum supression algorithm."""
        bboxes = sorted(bboxes, key=lambda bbox: bbox.score, reverse=True)
        kept_bboxes = []

        for bbox in bboxes:
            suppressed = False
            for kept_bbox in kept_bboxes:
                similarity = self._inter_over_union(kept_bbox, bbox)
                if similarity > min_suppression_threshold:
                    suppressed = True
                    break
            if not suppressed:
                kept_bboxes.append(bbox)
        return kept_bboxes

    def __call__(self, frame):
        """Performs palm detection in an input image."

        The input image must be square with a size of [256, 256] in the
        range [-1.0, 1.0].

        Args:
        frame (numpy.ndarray): Input frame to be processed.

        Returns:
        PalmBbox object: Object that encanpsulates the bounding box coordinates
            and the 7 keypoints.
        """
        # Predict box offsets, width, height and 7 keypoints
        # [dx, dy, w, h (kx0, ky0), ..., (kx6, ky6)]
        self._interpreter.set_tensor(self._in_idx, frame[None])
        self._interpreter.invoke()

        out_reg = self._interpreter.get_tensor(self._out_reg_idx)[0]
        out_clf = self._interpreter.get_tensor(self._out_clf_idx)[0, :, 0]

        # Apply sigmoid to raw scores and find the predictions above the threshold
        scores = self.sigmoid(out_clf)
        mask = scores > self._palm_detection_conf

        detections = out_reg[mask]
        anchors = self._anchors[mask]
        scores = scores[mask]

        # No palm was found
        if detections.shape[0] == 0:
            return None

        bboxes = []
        for detection, anchor, score in zip(detections, anchors, scores):
            deltax, deltay, width, height = detection[0:4] / frame.shape[0]
            anchor_center = anchor[0:2]
            keypoints = anchor_center + detection[4:].reshape(-1, 2)

            center = [anchor_center[0] + deltax, anchor_center[1] + deltay]
            dims = [width, height]

            bbox = PalmBbox(center, dims, score, keypoints)
            bboxes.append(bbox)

        # Apply non-maximum supression to eliminate redundant bboxes
        bboxes = self._non_max_suppression(bboxes, self._min_supression_threshold)
        return bboxes[: self._num_palms]
