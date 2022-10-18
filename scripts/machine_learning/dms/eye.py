# Copyright 2022 NXP Semiconductors
# SPDX-License-Identifier: BSD-3-Clause

import numpy as np

class Eye(object):
    """
    This class use 468 points landmark to analyze eye behavior
    """

    LEFT_EYE_POINTS = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE_POINTS = [362, 385, 387, 263, 373, 380]
    LEFT_EYE_EDGE = 8
    RIGHT_EYE_EDGE = 8

    def __init__(self, landmarks = None):
        self.landmark_points = landmarks

    def blinking_ratio(self, frame, landmarks, side):
        """Calculates a ratio that can indicate whether an eye is closed or not.
        It's calculating the absolute differenc between eye area's color to the
        skin color that at eye edge

        Arguments:
            landmarks : 468 points Facial landmarks of the face region
            side : 0 means left side, 1 means right side

        Returns:
            The computed ratio
        """

        points = []
        edge_point = 0
        if side == 0:
            for i in self.LEFT_EYE_POINTS:
                point = landmarks[i]
                points.append(point)
            edge_point = landmarks[self.LEFT_EYE_EDGE]
        else:
            for i in self.RIGHT_EYE_POINTS:
                point = landmarks[i]
                points.append(point)
            edge_point = landmarks[self.RIGHT_EYE_EDGE]

        x1 = points[1][0]
        y1 = points[1][1]
        x2 = points[4][0]
        y2 = points[4][1]

        x3 = edge_point[0]
        y3 = edge_point[1]

        eye_center_mean = np.mean(np.array(frame[y1:y2, x1:x2]), axis=(0,1))
        #print(np.shape(eye_center_mean))
        eye_edge = np.array(frame[y3, x3])
        #print(np.shape(eye_edge))

        diff_3_mean = np.abs(np.mean(eye_center_mean - eye_edge))

        return diff_3_mean

