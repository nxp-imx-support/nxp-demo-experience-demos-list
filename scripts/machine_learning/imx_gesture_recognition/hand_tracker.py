# Copyright 2025 NXP
# SPDX-License-Identifier: Apache-2.0
"""
hand_tracker.py

This module provides the HandTracker class, which detects and tracks
up to two hands in a given frame.

Usage:
    import hand_tracker

    tracker = hand_tracker.HandTracker()
    detections = tracker(frame)

Classes:
    HandTracker: Detects and tracks hands in an frame.
"""
import cv2
import numpy as np

from app_utils import drawkit
from app_utils import utils_image
from app_utils import utils_bboxes
from core import hand_landmark
from core import palm_detection


class HandTracker:
    """Detects and tracks up to two hands in a given frame.

    This class provides an interface for detecting up to two hands in
    an input frame, returning a list with the following structure:
    [(landmarks, hand_bbox, handedness), (landmarks, hand_bbox, handedness)]
    Where:
        - landmarks(list): Collection of 21 2D landmarks
        - hand_bbox(Bbox object instance): Object that encapsulates
            coordinates and other params that represent a bounding box
            enclosing a hand.
        - Handedness (Float): Right or left hand

    The HandTracker is mainly composed by two modules:
    First we run a palm detector over the entire input frame, searching for
    all palm instances. Then, by applying non-maximum suppression we can
    filter redundant detections and return up to 2 palm instances.

    These palm detections are resized to cover the entire hand and sent
    to the hand landmark module to calculate the 21 2D hand landmarks,
    their score, and handedness.

    If the score exceeds a threshold, we consider these detections
    as corrrect and use the landmarks to calculate a new hand bbox,
    eliminating the need to run the palm detector again until the hand
    is lost.

    Attributes:
        Palm detection model (str): Path to the palm detection model.
        Hand landmark model (str): Path to the hand landmark model.
        anchors (str): Path to the anchors.txt file.
        external_delegate (str or None): Path to an external delegate library,
            if used for hardware acceleration.
        num_hands (int): Max number of hand detections the object can return
            (1 or 2).

    You can also adjust the rest of the params. Experiment to see which
    settings gives you the best results.
    """

    def __init__(
        self,
        palm_detection_model,
        hand_landmark_model,
        anchors,
        external_delegate=None,
        num_hands=2,
        palm_detection_conf=0.50,
        min_suppression_threshold=0.3,
        palm_bbox_enlarge=2.6,
        palm_bbox_shift=(0.0, -0.5),
        hand_landmark_conf=0.49,
        hand_landmark_bbox_enlarge=2.6,
        hand_landmark_bbox_shift=(0.0, -0.3),
    ):
        """Initializates a HandTracker instance.

        Attributes:
            Palm detection model (str): Path to the palm detection model.
            Hand landmark model (str): Path to the hand landmark model.
            anchors (str): Path to the anchors.txt file.
            external_delegate (str or None): Path to an external delegate library,
                if used for hardware acceleration.
            num_hands (int): Max number of hand detections the object can return
                (1 or 2).
        """
        self._palm_detector = palm_detection.PalmDetector(
            model=palm_detection_model,
            anchors=anchors,
            external_delegate=external_delegate,
            palm_detection_conf=palm_detection_conf,
            min_suppr_thr=min_suppression_threshold,
            num_palms=num_hands,
        )

        self._hand_landmarks = hand_landmark.HandLandmark(
            model=hand_landmark_model, external_delegate=external_delegate
        )

        # Palm detection hyperparams
        self._palm_bbox_enlarge = palm_bbox_enlarge
        self._palm_bbox_shift = palm_bbox_shift

        # Hand landmark hyperparams
        self._hand_landmark_conf = hand_landmark_conf
        self._hand_landmark_bbox_enlarge = hand_landmark_bbox_enlarge
        self._hand_landmark_bbox_shift = hand_landmark_bbox_shift

        self._num_hands = num_hands
        self._previous_hand_bboxes = []

    def __call__(self, frame):
        """Detects and tracks up to two hands in a given frame."

        Args:
        frame (numpy.ndarray): Input frame to be processed.

        Returns:
        list: list with the following structure:
            [(landmarks, hand_bbox), (landmarks, hand_bbox)]
            Where:
                - landmarks(list): Collection of 21 2D landmarks
                - hand_bbox(Bbox object instance): Object that encapsulates
                    coordinates and other params that represent a bounding box
                    enclosing a hand.
        """
        detections = []
        # Run the palm detector again because we did not find any hands or we
        # missed them in the frame
        if len(self._previous_hand_bboxes) < self._num_hands:
            in_frame = frame.copy()
            if self._previous_hand_bboxes:
                # If we previously found a hand, we don't want to find a new bbox
                # for it using the palm detector
                drawkit.hide_hand(self._previous_hand_bboxes[0], in_frame)

            in_frame, padding = utils_image.preprocess(in_frame, 192)
            palm_bboxes = self._palm_detector(in_frame)

            if palm_bboxes:
                for i in range(self._num_hands - len(self._previous_hand_bboxes)):
                    if i >= len(palm_bboxes):
                        break
                    palm_bbox = palm_bboxes[i]

                    # At this point we have sucessfully found a palm,
                    # but hand landmark model needs an image where the
                    # entire hand appears
                    hand_bbox = utils_bboxes.compute_hand_bbox(
                        palm_bbox, self._palm_bbox_shift, self._palm_bbox_enlarge
                    )

                    hand_bbox = utils_bboxes.scale_bbox_to_frame(hand_bbox, padding)
                    self._previous_hand_bboxes.append(hand_bbox)

        # Previously, we used the palm detector to find any hands in the entire
        # frame. Now, we just need to run the hand landmark model to track
        # them if they exist
        if self._previous_hand_bboxes:
            new_hand_bboxes = []
            for i, _ in enumerate(self._previous_hand_bboxes):
                hand_bbox = self._previous_hand_bboxes[i]
                center = hand_bbox.center
                dims = hand_bbox.dims
                rot_degrees = hand_bbox.rotation * 180 / np.pi

                rect = (center, dims, rot_degrees)
                cropped, m_inv = utils_image.crop_rotated_rectangle(frame, rect)

                # Prepare the ROI before calculating the landmarks
                norm_cropped, padding = utils_image.preprocess(cropped, 224)
                lm_bbox = self._hand_landmarks(norm_cropped)

                if lm_bbox.score < self._hand_landmark_conf:
                    continue

                # Scale the landmarks to the cropped frame dimensions
                # before projecting them to the ROI
                lm_bbox = utils_bboxes.scale_bbox_to_frame(lm_bbox, padding)
                lm_bbox.landmarks = cv2.perspectiveTransform(
                    lm_bbox.landmarks.reshape(-1, 1, 2), m_inv
                )

                lm_bbox.landmarks = lm_bbox.landmarks.reshape(-1, 2)

                # Calculate a new hand bbox but using the landmarks
                hand_bbox = utils_bboxes.compute_hand_bbox(
                    lm_bbox,
                    self._hand_landmark_bbox_shift,
                    self._hand_landmark_bbox_enlarge,
                )

                detections.append((lm_bbox.landmarks, hand_bbox, lm_bbox.handedness))
                new_hand_bboxes.append(hand_bbox)

            self._previous_hand_bboxes = new_hand_bboxes

        return detections
