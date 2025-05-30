# Copyright 2025 NXP
# SPDX-License-Identifier: Apache-2.0
"""Several bounding box representations."""
import numpy as np

from app_utils.names import HandJoints, PalmJoints


class Bbox:
    """ "Represents a bounding box with center, dimensions and rotation.

    Attributes:
        center (list): Coordinates of the box center (x, y).
        dims (list): Width and height of box.
        rotation (float): Rotation of the bounding box.
    """

    def __init__(self, center, dims, rotation=0.0):
        """Initializates a Bbox instance.

        Args:
            center (list): Coordinates of the box center (x, y).
            dims (list): [Width, height] of box.
            rotation (float): Rotation of the bounding box.
        """
        self.center = center
        self.dims = dims
        self.rotation = rotation


class PalmBbox(Bbox):
    """ "Represents a bounding box that encloses a palm instance.

    Attributes:
        center (list): Coordinates of the box center (x, y).
        dims (list): Width and height of box.
        rotation (float): Rotation of the bounding box.
    """

    def __init__(self, center, dims, score, keypoints, rotation=0.0):
        """ "Initializates a PalmBbox instance.

        Attributes:
            center (list): Coordinates of the box center (x, y).
            dims (list): Width and height of box.
            rotation (float): Rotation of the bounding box.
            score (flaot): Probabilty that this bounding box contains a
                palm instance.
            keypoints (list): List of seven keypoints for palm detection
        """
        super().__init__(center, dims, rotation)
        self.score = score
        self.keypoints = keypoints

    def coordinates(self):
        """Return bounding box coordinates in [xmin, ymin, xmax, ymax] format."""
        x_min = self.center[0] - self.dims[0] / 2.0
        y_min = self.center[1] - self.dims[1] / 2.0
        x_max = self.center[0] + self.dims[0] / 2.0
        y_max = self.center[1] + self.dims[1] / 2.0

        return [x_min, y_min, x_max, y_max]

    def compute_rotation(self):
        """Return the rotation value of a palm bbox instance."""
        x_0, y_0 = self.keypoints[HandJoints.WRIST.value]
        # NOTE: In palm detections keypoints, this joint has index 2
        # That's why we need to subtract 7
        x_1, y_1 = self.keypoints[HandJoints.MIDDLE_FINGER_MCP.value - 7]

        target_angle = np.pi * 0.5
        rot = target_angle - np.arctan2(-(y_1 - y_0), (x_1 - x_0))
        norm_rot = rot - 2 * np.pi * np.floor((rot + np.pi) / (2 * np.pi))
        return norm_rot


class LandmarkBbox(Bbox):
    """ "Represents a bounding box that encloses a hand instance by using lmks.

    Attributes:
        center (list): Coordinates of the box center (x, y).
        dims (list): Width and height of box.
        rotation (float): Rotation of the bounding box.
    """

    def __init__(self, center, dims, score, handedness, landmarks, rotation=0.0):
        """ "Initializates a LandmarkBbox instance.

        Attributes:
            center (list): Coordinates of the box center (x, y).
            dims (list): Width and height of box.
            rotation (float): Rotation of the bounding box.
            score (flaot): Probabilty that this bounding box contains a
                palm instance.
            keypoints (list): List of seven keypoints for palm detection
        """
        super().__init__(center, dims, rotation)
        self.score = score
        self.handedness = handedness
        self.landmarks = landmarks

    def compute_rotation(self):
        """Return the rotation value of a LandmarkBbox instance."""
        x_0, y_0 = self.landmarks[HandJoints.WRIST.value]
        x_1, y_1 = self.landmarks[HandJoints.MIDDLE_FINGER_MCP.value]

        target_angle = np.pi * 0.5
        rot = target_angle - np.arctan2(-(y_1 - y_0), (x_1 - x_0))
        norm_rot = rot - 2 * np.pi * np.floor((rot + np.pi) / (2 * np.pi))
        return norm_rot


def compute_hand_bbox(bbox, shift, box_enlarge):
    """Calculate a bbox that encloses an entire hand.

    Given a palm bbox or landmark bbox, returns a wider bbox enclosing an
    entire hand.
    """
    if isinstance(bbox, LandmarkBbox):
        # Calculate the coordinates of a bouding box that encloses the palm
        max_x = -np.inf
        max_y = -np.inf
        min_x = np.inf
        min_y = np.inf

        for joint in PalmJoints:
            max_x = max(bbox.landmarks[joint.value][0], max_x)
            max_y = max(bbox.landmarks[joint.value][1], max_y)

            min_x = min(bbox.landmarks[joint.value][0], min_x)
            min_y = min(bbox.landmarks[joint.value][1], min_y)

        center = ((min_x + max_x) / 2, (min_y + max_y) / 2)
        dims = (max_x - min_x, max_y - min_y)

        bbox.center = center
        bbox.dims = dims

    shift_x, shift_y = shift
    rotation = bbox.compute_rotation()
    width, height = bbox.dims

    d_x = (width * shift_x) * np.cos(rotation) - (height * shift_y) * np.sin(rotation)

    d_y = (width * shift_x) * np.sin(rotation) + (height * shift_y) * np.cos(rotation)

    long_side = np.max([width, height])
    hand_w = long_side * box_enlarge
    hand_h = long_side * box_enlarge
    hand_center = [bbox.center[0] + d_x, bbox.center[1] + d_y]

    hand_bbox = Bbox(hand_center, [hand_w, hand_h], rotation)
    return hand_bbox


def scale_bbox_to_frame(bbox, padding):
    """Scale bbox coordinates to the size of a frame"""
    img_dim = padding["pad_img_dim"]
    pad_h, pad_w = padding["pad_size"]

    if isinstance(bbox, LandmarkBbox):
        # If the bbox is of type LanmarkBbox, we just need to scale the lmks
        bbox.landmarks = bbox.landmarks * img_dim
        return bbox

    bbox.center[0] = bbox.center[0] * img_dim - pad_w
    bbox.center[1] = bbox.center[1] * img_dim - pad_h

    bbox.dims[0] = bbox.dims[0] * img_dim
    bbox.dims[1] = bbox.dims[1] * img_dim

    return bbox
