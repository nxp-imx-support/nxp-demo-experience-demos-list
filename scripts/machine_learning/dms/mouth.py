# Copyright 2022 NXP
# SPDX-License-Identifier: BSD-3-Clause

import math
import numpy as np

class Mouth(object):
    """
    This class use 468 points landmark to analyze eye behavior
    """

    MOUTH_POINTS = [78, 13, 308, 14]
    FACE_POINTS = [132, 361]

    def __init__(self, landmarks = None):
        self.landmark_points = landmarks

    def yawning_ratio(self, landmarks):
        """
        Calculates a ratio that can indicate whether a person is yawning or not.
        It's the division of the height of the mouth, by its width.

        Arguments:
            landmarks : 468 points Facial landmarks of the face region

        Returns:
            The computed ratio
        """

        points = []
        for i in self.MOUTH_POINTS:
            point = landmarks[i]
            points.append(point)

        mouth_width = math.hypot((points[2][0] - points[0][0]), (points[2][1] - points[0][1]))
        mouth_height = math.hypot((points[1][0] - points[3][0]), (points[1][1] - points[3][1]))

        try:
            ratio = mouth_height / mouth_width
        except ZeroDivisionError:
            ratio = 0

        return ratio

    def mouth_face_ratio(self, landmarks):
        """
        Calculates a ratio that can indicate whether a person is turning left or right
        It's the division of the length from mouth middle point to the left side face, by
        the lengh from mouth middle point to the right side face.

        Arguments:
            landmarks : 468 points Facial landmarks of the face region

        Returns:
            The computed ratio
        """

        mouth_middle = landmarks[self.MOUTH_POINTS[1]]
        left_face = landmarks[self.FACE_POINTS[0]]
        right_face = landmarks[self.FACE_POINTS[1]]

        mouth_to_left = math.hypot((mouth_middle[0] - left_face[0]), (mouth_middle[1] - left_face[1]))
        mouth_to_right = math.hypot((right_face[0] - mouth_middle[0]), (right_face[1] - mouth_middle[1]))

        try:
            ratio = mouth_to_left / mouth_to_right
        except ZeroDivisionError:
            ratio = 0

        return ratio
