#!/usr/bin/env python3
# Copyright 2025 NXP
# SPDX-License-Identifier: Apache-2.0
"""i.MX Gesture Recognition"""
import os
import sys
import time
import logging
import argparse

import cv2

import hand_tracker
import gesture_classifier
from app_utils import drawkit

# GoPoint
if os.path.isdir("/opt/gopoint-apps/scripts/machine_learning/imx_gesture_recognition"):
    sys.path.append("/opt/gopoint-apps/scripts/machine_learning/imx_gesture_recognition")

def run(stream, args):
    """Run Hand Gesture Recognition task"""
    cap = cv2.VideoCapture(stream)
    if not cap.isOpened():
        raise RuntimeError(f"Error opening video stream or file: {stream}")

    tracker = hand_tracker.HandTracker(
        palm_detection_model=args.palm_model,
        hand_landmark_model=args.hand_landmark_model,
        anchors=args.anchors,
        external_delegate=args.external_delegate_path,
        num_hands=args.num_hands,
    )

    classifier = gesture_classifier.Classifier(model=args.classification_model)
    cv2.namedWindow("i.MX Gesture Recognition", cv2.WND_PROP_FULLSCREEN)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        start_time = time.time()
        detections = tracker(frame)

        if detections:
            for results in detections:
                landmarks, hand_bbox, handedness = results
                drawkit.draw_landmarks(landmarks, frame)
                drawkit.draw_handbbox(hand_bbox, frame)

                predictions = classifier(landmarks)
                drawkit.draw_results(predictions, handedness, landmarks[0], frame)

        end_time = time.time()

        if logger.getEffectiveLevel() == logging.DEBUG:
            # Display debugging information on the frame
            fps = 1 / (end_time - start_time)
            drawkit.display_fps(fps, frame)

        cv2.imshow("i.MX Gesture Recognition", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="i.MX Gesture Recognition showcases the Machine "
        "Learning (ML) capabilities of the i.MX SoCs (i.MX 93 and i.MX 8M Plus) "
        "using the available Neural Processing Unit (NPU) to accelerate two "
        "Deep Learning vision-based models. Together, these models detect up to "
        "two hands present in the scene and predict 21 3D-keypoints that are used "
        "to recognize hand signs and finger gestures by implementing a "
        "Multi Layer Perceptron (MLP)."
    )

    parser.add_argument(
        "-f",
        "--file",
        metavar="file",
        type=str,
        help="Input file. It can be an image or a video.",
    )
    parser.add_argument(
        "-d",
        "--device",
        metavar="device",
        type=str,
        help="Camera device. Please provide the camera device " "as /dev/videoN.",
    )
    parser.add_argument(
        "-e",
        "--external_delegate_path",
        metavar="external delegate",
        type=str,
        help="Path to external delegate for HW acceleration.",
    )
    parser.add_argument(
        "--logging_level",
        metavar="logging level",
        type=int,
        default=logging.WARNING,
        help="Logging level priority.",
    )

    parser.add_argument(
        "--palm_model",
        metavar="palm model",
        type=str,
        required=True,
        help="Path to palm detection model.",
    )
    parser.add_argument(
        "--hand_landmark_model",
        metavar="hand landmark model",
        type=str,
        required=True,
        help="Path to hand landmark model.",
    )
    parser.add_argument(
        "--classification_model",
        metavar="classification model",
        type=str,
        required=True,
        help="Path to classification model.",
    )
    parser.add_argument(
        "--anchors",
        metavar="anchors",
        type=str,
        required=True,
        help="Path to anchors file.",
    )

    parser.add_argument(
        "--num_hands",
        metavar="Number of hands",
        type=int,
        default=2,
        help="Max number of hands that will be detected [1, 2]",
    )

    args = parser.parse_args()
    source = args.file
    if source:
        if not os.path.isfile(args.file):
            raise FileNotFoundError(
                "Source file does not exists. Please provide"
                " a valid source. You can check"
                " python3 main.py --help for more details."
            )

    elif args.device:
        source = args.device

    if args.external_delegate_path:
        if not os.path.isfile(args.external_delegate_path):
            raise FileNotFoundError(f"File {args.external_delegate_path} not found.")

    if not args.num_hands in [1, 2]:
        raise ValueError("The Number of hands must be 1 or 2.")

    if not os.path.isfile(args.palm_model):
        raise FileNotFoundError(f"File {args.palm_model} not found.")
    if not os.path.isfile(args.hand_landmark_model):
        raise FileNotFoundError(f"File {args.hand_landmark_model} not found.")
    if not os.path.isfile(args.classification_model):
        raise FileNotFoundError(f"File {args.classification_model} not found.")
    if not os.path.isfile(args.anchors):
        raise FileNotFoundError(f"File {args.anchors} not found.")

    logging.basicConfig(level=args.logging_level, format="%(levelname)s: %(message)s")
    logger = logging.getLogger()

    logging.info("Source: %s", source)
    logging.info("Palm detection: %s", args.palm_model)
    logging.info("Hand landmark: %s", args.hand_landmark_model)
    logging.info("Classification model: %s", args.classification_model)
    logging.info("External delegate: %s", args.external_delegate_path)
    logging.info("Number of hands: %d", args.num_hands)

    run(source, args)
