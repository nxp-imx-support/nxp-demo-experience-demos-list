#!/usr/bin/env python3

"""
Copyright 2022 NXP
SPDX-License-Identifier: Apache-2.0

Model: MediaPipe Selfie Segmentation
Model's License: Apache-2.0
Original model available at: https://google.github.io/mediapipe/solutions/models.html
Model Card: https://drive.google.com/file/d/1dCfozqknMa068vVsO2j_1FgZkW_e3VWv/preview

The following is a demo to show human segmentation from video.
Application could be aimed at video conference.
The original MediaPipe model was quantized using per-tensor quantization to be
accelerated by the NPU on the i.MX8M Plus EVK.
"""

import cv2
import numpy as np
import tflite_runtime.interpreter as tflite
import time
import os
import subprocess
import sys

sys.path.append("/home/root/.nxp-demo-experience/scripts/")

import utils

if __name__ == "__main__":
    out = subprocess.run(["python3", "/home/root/.nxp-demo-experience/scripts/machine_learning/segmentation_launch.py"]).returncode
    print(out)
    if out == -1:
        exit()
    model_path = utils.download_file("selfie_segmentation_quant.tflite")
    bg_path = utils.download_file("bg_image.jpg")
    # Load model and use VX delegate for acceleration
    ext_delegate = tflite.load_delegate("/usr/lib/libvx_delegate.so")
    interpreter = tflite.Interpreter(
        model_path=model_path, num_threads=4, experimental_delegates=[ext_delegate])
    os.environ["VIV_VX_CACHE_BINARY_GRAPH_DIR"] = ("/home/root/.cache"
        "/demoexperience")
    os.environ["VIV_VX_ENABLE_CACHE_GRAPH_BINARY"] = "1"
    interpreter.allocate_tensors()
    input_index = interpreter.get_input_details()[0]['index']
    input_shape = interpreter.get_input_details()[0]['shape']
    output = interpreter.get_output_details()[0]['index']

    # Get video src
    video_src = "v4l2src device=/dev/video" + str(out) + " ! imxvideoconvert_g2d ! video/x-raw,width=640,height=480,framerate=30/1 ! videoconvert ! appsink"
    cap = cv2.VideoCapture(video_src)

    frame_width = 640
    frame_height = 480

    # Loop through the video frames
    while True:

        got_frame, frame = cap.read()
        if got_frame is False:
            print("No frame... exiting program!")
            break

        start = time.time()

        # Flip frame and change channel layout
        frame = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)

        # fit the image into a 256,256 square for input model
        input_frame = cv2.resize(frame, (256, 256))
        input_frame = np.ascontiguousarray(input_frame)

        # Reshape tensors to fit input size of model
        input_frame = np.reshape(
            input_frame, [-1, input_frame.shape[0], input_frame.shape[1], 3])

        # Normilize input image
        input_frame = np.ascontiguousarray(
            2 * ((input_frame / 255) - 0.5).astype('float32'))

        # Perform inference with model for segmentation
        interpreter.set_tensor(input_index, input_frame)
        inference_start = time.time_ns()
        interpreter.invoke()
        inference_end = time.time_ns()
        segmentation = interpreter.get_tensor(output)[0]

        # Interpret segmentation
        condition = segmentation > 0.10
        condition_frame = np.zeros((256, 256, 3), dtype=np.uint8)
        condition_frame[:, :, 0] = condition[:, :, 0]
        condition_frame[:, :, 1] = condition[:, :, 0]
        condition_frame[:, :, 2] = condition[:, :, 0]
        condition_frame = cv2.resize(
            condition_frame, (frame_width, frame_height), cv2.INTER_CUBIC)

        # Create background image. In this demo, a green background is used.
        # This can be changed for any image or color
        # background_img = np.zeros(frame.shape, dtype=np.uint8)
        # background_img[:] = (0, 255, 0)        
        background_img = cv2.imread(bg_path)
        background_img = cv2.resize(background_img, (640,480))

        # Only print segmentation over background
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        output_image = np.where(condition_frame, frame, background_img)

        # Get inference time for model and FPS for pipeline
        end = time.time()
        total_time = end - start
        total_inference_time = inference_end - inference_start
        fps = 1 / total_time

        cv2.putText(output_image, f'FPS: {int(fps)}', (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2)
        cv2.putText(output_image, f'Inf: {float(total_inference_time / 1000000.0)} ms',
                    (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2)

        cv2.namedWindow("Selfie Segmentation")
        cv2.imshow("Selfie Segmentation", output_image)

        if cv2.waitKey(1) == 27:
            break
