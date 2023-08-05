"""
Copyright 2023 NXP

SPDX-License-Identifier: BSD-3-Clause

This script helps for the camera streaming using gstreamer in
the client, which recieves the frames via UDP, calculates
the FPS and stores in the file.
"""

import cv2
import time

FPS = 0
value = 1
start_time = time.time()
count = 0
cap = cv2.VideoCapture(
    "udpsrc port=5000 ! application/x-rtp, encoding-name=JPEG, payload=26 ! rtpjpegdepay ! jpegparse ! jpegdec ! decodebin ! videoconvert ! appsink",
    cv2.CAP_GSTREAMER,
)

while cap.isOpened():
    ret, frame = cap.read()
    if ret:
        cv2.imshow("Camera Streaming", frame)
        if cv2.waitKey(25) & 0xFF == ord("q"):
            break
        count += 1
        if (time.time() - start_time) > value:
            FPS = count / (time.time() - start_time)
            FPS = str(FPS)
            _file = open("/home/root/.nxp-demo-experience/scripts/TSN/qbv/FPS.txt", "w")
            _file.write(FPS)
            count = 0
            start_time = time.time()
cap.release()
cv2.destroyAllWindows()
