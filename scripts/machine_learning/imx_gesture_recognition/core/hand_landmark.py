# Copyright 2025 NXP
# SPDX-License-Identifier: Apache-2.0
"""Performs the detection of the hand landmarks in an input image."""
import numpy as np
import tflite_runtime.interpreter as tflite

from app_utils.utils_bboxes import LandmarkBbox


class HandLandmark:
    """Performs the detection of the hand landmarks in an input image.

    This class provides an interface for detecting landmarks in images (the
    images must be square with a size of [224, 224] in the range [-1.0, 1.0]).

    Attributes:
        model (str): Path to the hand landmark model.
        external_delegate (str or None): Path to an external delegate library,
            if used for hardware acceleration.
    """

    def __init__(self, model, external_delegate):
        """Initializates a HandLandmark instance.

        Attributes:
            model (str): Path to the hand landmark model.
            external_delegate (str or None): Path to an external delegate library,
                if used for hardware acceleration.
        """
        if external_delegate:
            external_delegate = [tflite.load_delegate(external_delegate)]

        self._interpreter = tflite.Interpreter(
            model, experimental_delegates=external_delegate
        )
        self._interpreter.allocate_tensors()

        _out_details = self._interpreter.get_output_details()
        _in_details = self._interpreter.get_input_details()

        self._in_idx = _in_details[0]["index"]
        self._out_lmks_idx = _out_details[3]["index"]
        self._out_score_idx = _out_details[2]["index"]
        self._out_handness_idx = _out_details[0]["index"]

        # Ignore the first invoke (Warm-up time)
        batch, width, height, channel = tuple(_in_details[0]["shape"].tolist())
        self._interpreter.set_tensor(
            self._in_idx, np.random.rand(batch, width, height, channel).astype("float32")
        )
        self._interpreter.invoke()

    def __call__(self, frame):
        """Performs the detection of the hand landmarks in an input image."

        Args:
        frame (numpy.ndarray): Input frame to be processed.

        Returns:
        LandmarkBbox object: Object that encanpsulates the bounding box coordinates
            landmarks, score, and handedness.
        """
        self._interpreter.set_tensor(self._in_idx, frame[None])
        self._interpreter.invoke()

        # Normalized landmarks
        landmarks = self._interpreter.get_tensor(self._out_lmks_idx)[0] / 224
        handedness = self._interpreter.get_tensor(self._out_handness_idx)[0]
        score = self._interpreter.get_tensor(self._out_score_idx)[0]

        landmarks = landmarks.tolist()
        del landmarks[2::3]  # Drop z-component
        landmarks = np.array(landmarks).reshape(-1, 2)

        # The center, dims and rotation must be calculated until
        # the landmarks are projected onto the original frame
        lm_bbox = LandmarkBbox(
            center=None,
            dims=None,
            rotation=None,
            score=float(score),
            handedness=float(handedness),
            landmarks=landmarks,
        )

        return lm_bbox
