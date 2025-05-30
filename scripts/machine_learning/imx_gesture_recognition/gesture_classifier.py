# Copyright 2025 NXP
# SPDX-License-Identifier: Apache-2.0
"""
gesture_classifier.py

This module provides the Classifier class, which uses 21 2D landmarks
to predict between three hand gestures: Pointer, Close, and Open.

Usage:
    import gesture_classifier

    classifier = gesture_classifier.Classifier()
    predictions = classifier(landmarks)

Classes:
    Classifier: Predict between three hand gestures.
"""
import numpy as np
import tflite_runtime.interpreter as tflite


class Classifier:
    """MLP to recognize various hand signs and finger gestures"""
    def __init__(self, model):
        self._interpreter = tflite.Interpreter(model)
        self._interpreter.allocate_tensors()

        _out_details = self._interpreter.get_output_details()
        _in_details = self._interpreter.get_input_details()

        self._in_idx = _in_details[0]["index"]
        self._out_idx = _out_details[0]["index"]

    def __call__(self, landmarks):
        landmarks = landmarks - landmarks[0]
        landmarks = landmarks.flatten()
        landmarks = landmarks / np.max(np.abs(landmarks))

        self._interpreter.set_tensor(self._in_idx, landmarks.astype("float32")[None])
        self._interpreter.invoke()
        predictions = self._interpreter.get_tensor(self._out_idx)

        return predictions
