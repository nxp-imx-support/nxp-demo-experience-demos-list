#!/usr/bin/env python3

"""
Copyright 2025 NXP
SPDX-License-Identifier: Apache-2.0

The following is a demo to show CAN Open usage on i.MX boards.
It simulates a car navigation system composed of sensors and 
a reversing camera screen.
Sensors are emulated using sliders.
"""

import canopen
import time
import os
import cv2
import numpy as np


from gi.repository import Gdk
screen = Gdk.Screen.get_default()
SCREEN = screen.get_monitor_geometry(screen.get_primary_monitor())

import argparse

parser = argparse.ArgumentParser()
parser.add_argument("can_device")
args = parser.parse_args()
CAN_DEVICE = args.can_device

low_r = np.array([0, 0, 1], dtype=np.uint8)
low_g = np.array([0, 1, 0], dtype=np.uint8)
COLOR_RANGE = [((255 - i) * low_r + low_g * i).tolist() for i in range(0, 255, 5)]
DIRECTION_POINTS = [
    [1 - y * 0.018, x / 100, 1 - x / 100] for y, x in enumerate(range(15, 40))
]


def draw_circle_arc(image, index, angles):
    center = (int(image.shape[1] / 2), 350)
    return cv2.ellipse(
        image,
        center,
        (int(550 + index / 2), int(550 + index / 2)),
        0,
        angles[0],
        angles[1],
        COLOR_RANGE[index],
        int(2 + 10 - index / 5),
    )


def draw_direction(image, angle):
    h, w, _ = image.shape
    last_y = int(DIRECTION_POINTS[0][0] * h)
    last_x1 = int(DIRECTION_POINTS[0][1] * w)
    last_x2 = int(DIRECTION_POINTS[0][2] * w)
    for point_y_x_x in DIRECTION_POINTS:
        y = int(point_y_x_x[0] * h)
        x1 = int((point_y_x_x[1] + angle / 70 * (1 - point_y_x_x[0]) ** 1.4) * w)
        x2 = int((point_y_x_x[2] + angle / 70 * (1 - point_y_x_x[0]) ** 1.4) * w)
        image = cv2.line(image, (last_x1, last_y), (x1, y), (0, 255, 0), 5)
        image = cv2.line(image, (last_x2, last_y), (x2, y), (0, 255, 0), 5)
        last_y, last_x1, last_x2 = y, x1, x2
    return image


def main():
    cv2.namedWindow("Car Reverse Screen", cv2.WINDOW_FULLSCREEN)
    cv2.setWindowProperty("Car Reverse Screen", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    car_frame = cv2.imread("/opt/gopoint-apps/scripts/communication/car_navigation/data/car.jpg")
    car_frame = cv2.resize(
        car_frame, (int(car_frame.shape[1] * (SCREEN.height / car_frame.shape[0])), SCREEN.height)
    )

    camera_frame = cv2.imread("/opt/gopoint-apps/scripts/communication/car_navigation/data/parking.jpg")
    camera_frame = cv2.resize(
        camera_frame, (int(camera_frame.shape[1] * (SCREEN.height / camera_frame.shape[0])), SCREEN.height)
    )
    camera_frame = camera_frame[
        :,
        int((camera_frame.shape[1] - SCREEN.width + car_frame.shape[1]) / 2) : int(
            (camera_frame.shape[1] + SCREEN.width - car_frame.shape[1]) / 2
        ),
    ]

    network = canopen.Network()
    network.connect(channel=CAN_DEVICE, interface="socketcan")
    local_node = canopen.LocalNode(10, "/opt/gopoint-apps/scripts/communication/car_navigation/data/CarNavigationGoPoint.eds")
    network.add_node(local_node)

    network.scanner.search(10)
    time.sleep(0.05)
    for node_id in network.scanner.nodes:
        print(f"Found node {node_id}!")

    key = 8
    while key != ord("q"):

        colors = [50, 50, 50, 50]

        os.system("clear")
        for obj in local_node.object_dictionary.values():
            try:
                print(f"0x{obj.index:X}: {obj.name} = {local_node.sdo[obj.index].raw}")
                if obj.index == 8192:
                    steering_wheel = int(local_node.sdo[obj.index].raw)
            except Exception as e:
                print(f"0x{obj.index:X}: {obj.name}")

            if isinstance(obj, canopen.objectdictionary.ODArray):
                for subobj in obj.values():
                    print(
                        f"  {subobj.subindex}: {subobj.name} = {local_node.sdo[obj.index][subobj.subindex].raw}"
                    )
                    colors[subobj.subindex] = int(
                        local_node.sdo[obj.index][subobj.subindex].raw
                    )

        car_frame_aux = car_frame.copy()

        car_frame_aux = draw_circle_arc(car_frame_aux, colors[0], (60, 74))
        car_frame_aux = draw_circle_arc(car_frame_aux, colors[1], (76, 89))
        car_frame_aux = draw_circle_arc(car_frame_aux, colors[2], (91, 104))
        car_frame_aux = draw_circle_arc(car_frame_aux, colors[3], (106, 120))

        camera_frame_aux = draw_direction(camera_frame.copy(), steering_wheel)

        # empty
        cv2.imshow(
            "Car Reverse Screen",  
            cv2.resize(
                cv2.hconcat([car_frame_aux, camera_frame_aux]),
                (SCREEN.width, SCREEN.height),
            ),
        )
        key = cv2.waitKey(50)


if __name__ == "__main__":
    main()
