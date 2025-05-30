# Copyright 2025 NXP
# SPDX-License-Identifier: Apache-2.0
""" "Names of the joints and their respectives indices"""
from enum import Enum


class HandJoints(Enum):
    WRIST = 0
    THUMB_CMC = 1
    THUMB_MCP = 2
    THUMB_IP = 3
    THUMB_TIP = 4
    INDEX_FINGER_MCP = 5
    INDEX_FINGER_PIP = 6
    INDEX_FINGER_DIP = 7
    INDEX_FINGER_TIP = 8
    MIDDLE_FINGER_MCP = 9
    MIDDLE_FINGER_PIP = 10
    MIDDLE_FINGER_DIP = 11
    MIDDLE_FINGER_TIP = 12
    RING_FINGER_MCP = 13
    RING_FINGER_PIP = 14
    RING_FINGER_DIP = 15
    RING_FINGER_TIP = 16
    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_DIP = 19
    PINKY_TIP = 20


class PalmJoints(Enum):
    WRIST = 0
    THUMB_CMC = 1
    THUMB_MCP = 2
    INDEX_FINGER_MCP = 5
    MIDDLE_FINGER_MCP = 9
    RING_FINGER_MCP = 13
    PINKY_MCP = 17
