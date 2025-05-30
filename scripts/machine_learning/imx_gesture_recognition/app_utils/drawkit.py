# Copyright 2025 NXP
# SPDX-License-Identifier: Apache-2.0
"""Auxiliar functions for displaying info and drawing figures on frame."""
import cv2
import numpy as np

FONT = cv2.FONT_HERSHEY_SIMPLEX
LINETYPE = cv2.LINE_AA
FONTSCALE = 0.5
COLOR = (0, 255, 0)
THICKNESS = 2
OFFSET = 50

# Colors
GREEN = (0, 202, 105)
ORANGE = (0, 181, 249)
BLUE = (224, 175, 14)


def draw_landmarks(landmarks, frame):
    """Draw landmarks on a hand."""
    # Joint indexes.
    # Visit https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker
    # for more details
    #
    #        8   12  16  20
    #        |   |   |   |
    #        7   11  15  19
    #    4   |   |   |   |
    #    |   6   10  14  18
    #    3   |   |   |   |
    #    |   5---9---13--17
    #    2    \         /
    #     \    \       /
    #      1    \     /
    #       \    \   /
    #        ------0-
    #
    connections = [
        (1, 2),
        (2, 3),
        (3, 4),
        (5, 6),
        (6, 7),
        (7, 8),
        (9, 10),
        (10, 11),
        (11, 12),
        (13, 14),
        (14, 15),
        (15, 16),
        (17, 18),
        (18, 19),
        (19, 20),
        (0, 1),
        (0, 5),
        (0, 9),
        (0, 13),
        (0, 17),
        (5, 9),
        (9, 13),
        (13, 17),
    ]

    if landmarks is not None:
        for connection in connections:
            x_0, y_0 = landmarks[connection[0]]
            x_1, y_1 = landmarks[connection[1]]
            cv2.line(frame, (int(x_0), int(y_0)), (int(x_1), int(y_1)), BLUE, 2)

        for index, point in enumerate(landmarks):
            x, y = point
            if index in [0, 1, 2, 5, 9, 13, 17]:  # Palm
                cv2.circle(frame, (int(x), int(y)), 6, ORANGE, -1)
            else:
                cv2.circle(frame, (int(x), int(y)), 6, GREEN, -1)


def draw_handbbox(hand_bbox, frame):
    """Draw a bounding box enclosing a hand."""
    rot_degrees = hand_bbox.rotation * 180 / np.pi
    rect = (hand_bbox.center, hand_bbox.dims, rot_degrees)

    # Draw hand bbox
    box = cv2.boxPoints(rect)
    box = np.int64(box)
    cv2.drawContours(frame, [box], 0, GREEN, 2)


def hide_hand(hand_bbox, frame):
    """Fill the bounding box to 'hide' a hand bbox."""
    rot_degrees = hand_bbox.rotation * 180 / np.pi
    rect = (hand_bbox.center, hand_bbox.dims, rot_degrees)

    # Draw hand bbox
    box = cv2.boxPoints(rect)
    box = np.int64(box)
    cv2.drawContours(frame, [box], 0, GREEN, cv2.FILLED)

def draw_results(predictions, handedness, origin, frame):
    """Draw data on a frame."""
    org = (int(origin[0]), int(origin[1] + OFFSET))

    predictions = predictions.squeeze() > 0.75
    predictions = predictions.tolist()

    try:
        gesture_idx = predictions.index(True)
    except ValueError:
        gesture_idx = -1

    if gesture_idx == 0:
        gesture = "Open"
    elif gesture_idx == 1:
        gesture = "Close"
    elif gesture_idx == 2:
        gesture = "Point"
    else:
        gesture = "Unknown"

    if handedness > 0.75:
        hand = "Right"
    else:
        hand = "Left"

    cv2.putText(
        frame, f"Hand: {hand}", org, FONT, FONTSCALE, ORANGE, THICKNESS, LINETYPE
    )
    org = (int(origin[0]), int(origin[1] + 80))
    cv2.putText(
        frame, f"Gesture: {gesture}", org, FONT, FONTSCALE, ORANGE, THICKNESS, LINETYPE
    )


def display_fps(fps, frame):
    """Display FPS"""
    text = f"FPS: {fps:.2f}"
    cv2.putText(frame, text, (10, 40), FONT, FONTSCALE, (0, 0, 0), THICKNESS, LINETYPE)
