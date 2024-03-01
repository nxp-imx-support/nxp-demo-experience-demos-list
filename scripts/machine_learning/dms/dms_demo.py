#!/usr/bin/env python3

"""
Copyright 2022-2024 NXP
SPDX-License-Identifier: BSD-3-Clause

Model: face_detection_ptq.tflite
Model licensed under Apache-2.0 License
Original model available at
https://storage.googleapis.com/mediapipe-assets/face_detection_short_range.tflite
Model card: https://mediapipe.page.link/blazeface-mc

Model: face_landmark_ptq.tflite
Model licensed under Apache-2.0 License
Original model available at https://storage.googleapis.com/mediapipe-assets/face_landmark.tflite
Model card: https://mediapipe.page.link/facemesh-mc

Model: iris_landmark_ptq.tflite
Model licensed under Apache-2.0 License
Original model available at https://storage.googleapis.com/mediapipe-assets/iris_landmark.tflite
Model card: https://mediapipe.page.link/iris-mc

Model: yolov4_tiny_smk_call.tflite
Model licensed under Apache-2.0 License
This model is trained by NXP.
Original model structure available at https://github.com/AlexeyAB/darknet/

This script define class of DMSDemo. The DMS demo shows how to implement a driver monitor system
using multiple ML models with NPU acceleration.
"""

import os
import sys
import math
import time
import argparse
import numpy as np
import gi
import cairo
from face_detection import FaceDetector
from face_landmark import FaceLandmark
from eye import Eye
from mouth import Mouth
from smoking_calling_yolov4 import SmokingCallingDetector

gi.require_version("Gst", "1.0")
from gi.repository import Gst

cur_path = os.path.dirname(os.path.abspath(__file__))

DRAW_SMK_CALL_CORDS = False
""" To enable drawing for smk/call detection box """

DRAW_LANDMARKS = False
""" To enable drawing for face landmarks
(this will slow down the drawing process a lot, just for debug) """

FRAME_WIDTH = 300
""" The frame width of image from gstreamer pipeline to ml_sink """

FRAME_HEIGHT = 300
""" The frame height of image from gstreamer pipeline to ml_sink """

BAD_FACE_PENALTY = 0.01
""" % to remove for far away face """

NO_FACE_PENALTY = 0.7
""" % to remove for no faces in frame """

YAWN_PENALTY = 7.0
""" % to remove for yawning """

DISTRACT_PENALTY = 2.0
""" % to remove for looking away """

SLEEP_PENALTY = 5.0
""" % to remove for sleeping """

SMK_PENALTY = 2.0
""" % to remove for smoking """

CALL_PENALTY = 2.0
""" % to remove for calling """

RESTORE_CREDIT = -5.0
""" % to restore for doing everything right """

FACE_THRESHOLD = 0.7
""" The threshold value for face detection """

LEFT_EYE_THRESHOLD = 0.3
""" if the left_eye ratio is greater then this value, then left eye will be
    considered as open, otherwise be considered as closed. """

RIGHT_EYE_THRESHOLD = 0.3
""" if the right_eye ratio is greater then this value, then right eye will be
    considered as open, otherwise be considered as closed. """

MOUTH_THRESHOLD = 0.4
""" if the mouth ratio is greater then this value, then mouth will be
    considered as open, otherwise be considered as closed. """

FACING_LEFT_THRESHOLD = 0.5
""" if the mouth_face_ratio is less then this value then face will be
    considered as turning left """

FACING_RIGHT_THRESHOLD = 2
""" if the mouth_face_ratio is greater then this value, then face will be
    considered as turning right"""

SMK_CALL_THRESHOLD = 0.7
""" The threshold value for smoking/calling detection """

LEFT_W = 3
""" The filter window size for left eye """

RIGHT_W = 3
""" The filter window size for right eye """

LEFT_EYE_STATUS = np.zeros(LEFT_W)
""" Array to filter out left eye blinking. In the array, 0 means eye closed, 1 means eye open """

RIGHT_EYE_STATUS = np.zeros(RIGHT_W)
""" Array to filter out right eye blinking. In the array, 0 means eye closed, 1 means eye open """


class DMSDemo:
    """The class to run the DMS demo"""

    def __init__(self, video_device, inf_device, model_path):
        """
        Creates an instance of the DMSDemo

        Arguments:
        video_device -- the device node of input camera
        inf_device -- the inference device, CPU or NPU
        model_path -- the path to all models and image
        """

        self.inited = False
        self.distracted = False
        self.drowsy = False
        self.yawn = False
        self.smoking = False
        self.phone = False
        self.face_cords = []
        self.marks = []
        self.safe_value = 0.0
        self.smk_call_cords = []

        if os.path.exists("/usr/lib/libvx_delegate.so"):
            self.platform = "i.MX8MP"
        elif os.path.exists("/usr/lib/libethosu_delegate.so"):
            self.platform = "i.MX93"
        else:
            print("Target is not supported!")
            sys.exit()

        if self.platform == "i.MX8MP":
            videoconvert = "imxvideoconvert_g2d ! "
            videocrop = (
                "imxvideoconvert_g2d ! videocrop top=0 left=134 right=134 bottom=0 ! "
            )
            info_image = "/imx8mp_dms_info.jpeg"
            compositor = "imxcompositor_g2d "
        if self.platform == "i.MX93":
            videoconvert = "imxvideoconvert_pxp ! "
            videocrop = "videocrop top=0 left=80 right=80 bottom=0 ! "
            info_image = "/imx93_dms_info.jpeg"
            compositor = "imxcompositor_pxp "

        cam_pipeline = (
            "v4l2src device="
            + video_device
            + " ! video/x-raw,framerate=30/1,"
            + "height=480,width=640,format=YUY2 ! "
            + videocrop
            + videoconvert
            + "video/x-raw,height=1072,width=1072,format=RGB16 ! "
            + "tee name=cam !  queue max-size-buffers=2 leaky=2 ! comp.sink_0  filesrc "
            + "location="
            + model_path
            + info_image
            + " ! jpegdec ! video/x-raw,"
            + "height=1080,width=840 ! imagefreeze ! comp.sink_1 "
            + compositor
            + "name=comp sink_1::xpos=0 sink_1::ypos=0 "
            + "sink_0::xpos=840 sink_0::ypos=4 ! cairooverlay name=drawer ! "
            + "queue max-size-buffers=2 leaky=2 ! waylandsink "
            + "window_width=1920 window-height=1080 "
            + "cam. ! queue max-size-buffers=2 leaky=2 ! "
            + videoconvert
            + "video/x-raw,height="
            + str(FRAME_HEIGHT)
            + ",width="
            + str(FRAME_WIDTH)
            + ",format=RGB16 ! videoconvert ! video/x-raw,format=RGB ! "
            + "appsink emit-signals=true drop=true max-buffers=2 name=ml_sink"
        )
        pipeline = Gst.parse_launch(cam_pipeline)
        pipeline.set_state(Gst.State.PLAYING)

        drawer = pipeline.get_by_name("drawer")
        drawer.connect("draw", self.draw)

        ml_sink = pipeline.get_by_name("ml_sink")
        ml_sink.connect("new-sample", self.inference)

        face_model = model_path + "/face_detection_ptq.tflite"
        landmark_model = model_path + "/face_landmark_ptq.tflite"
        iris_model = model_path + "/iris_landmark_ptq.tflite"
        smk_call_model = model_path + "/yolov4_tiny_smk_call.tflite"

        if self.platform == "i.MX93" and inf_device == "NPU":
            face_model = model_path + "/face_detection_ptq_vela.tflite"
            landmark_model = model_path + "/face_landmark_ptq_vela.tflite"
            iris_model = model_path + "/iris_landmark_ptq_vela.tflite"
            smk_call_model = model_path + "/yolov4_tiny_smk_call_vela.tflite"

        self.face_detector = FaceDetector(
            face_model, inf_device, self.platform, FACE_THRESHOLD
        )
        self.face_landmark = FaceLandmark(landmark_model, inf_device, self.platform)
        self.mouth = Mouth()
        self.eye = Eye(iris_model, inf_device, self.platform)
        self.smoking_calling_detector = SmokingCallingDetector(
            smk_call_model, inf_device, self.platform, conf=SMK_CALL_THRESHOLD
        )

        self.inited = True

    def inference(self, data):
        """Run all DMS models' inference on data from gst pipeline"""
        frame = data.emit("pull-sample")
        face_cords = []
        smk_call_cords = []
        mark_group = []

        call = True
        smk = True
        attention = True
        yawn = True
        sleep = True

        if frame is None:
            return 0
        if self.inited is False:
            return 0

        buffer = frame.get_buffer()
        caps = frame.get_caps()
        ret, mem_buf = buffer.map(Gst.MapFlags.READ)
        height = caps.get_structure(0).get_value("height")
        width = caps.get_structure(0).get_value("width")
        frame = np.ndarray(
            shape=(height, width, 3), dtype=np.uint8, buffer=mem_buf.data
        )[..., ::-1]

        boxes = self.face_detector.detect(frame)

        face_cords = []
        smk_call_cords = []
        mark_group = []

        if np.size(boxes, 0) > 0:
            # do smoking/calling detection
            smk_call_result = self.smoking_calling_detector.inference(frame, False)

            if np.size(smk_call_result, 0) > 0:
                for i in range(np.size(smk_call_result, 0)):
                    if int(smk_call_result[i][5]) == 0:
                        call = False
                    elif int(smk_call_result[i][5]) == 1:
                        smk = False
                    x1 = int(smk_call_result[i][0])
                    y1 = int(smk_call_result[i][1])
                    x2 = int(smk_call_result[i][2])
                    y2 = int(smk_call_result[i][3])
                    smk_call_cords.append([x1, y1, x2, y2])

            for i in range(np.size(boxes, 0)):
                boxes[i][[0, 2]] *= FRAME_WIDTH
                boxes[i][[1, 3]] *= FRAME_HEIGHT

            # Transform the boxes into squares.
            boxes = self.transform_to_square(boxes, scale=1.26, offset=(0, 0))

            # Clip the boxes if they cross the image boundaries.
            boxes, _ = self.clip_boxes(boxes, (0, 0, FRAME_WIDTH, FRAME_HEIGHT))
            boxes = boxes.astype(np.int32)

            # only do landmark for one face closest to the center
            face_in_center = 0
            distance_to_center = math.hypot(FRAME_WIDTH / 2, FRAME_HEIGHT / 2)
            for i in range(np.size(boxes, 0)):
                x1, y1, x2, y2 = boxes[i]
                mid_to_center = math.hypot(
                    (x2 + x1 - FRAME_WIDTH) / 2, (y2 + y1 - FRAME_HEIGHT) / 2
                )
                if mid_to_center < distance_to_center:
                    face_in_center = i
                    distance_to_center = mid_to_center

            x1, y1, x2, y2 = boxes[face_in_center]
            face_cords.append([x1, y1, x2, y2])

            # now do face landmark inference
            face_image = frame[y1:y2, x1:x2]
            face_marks = self.face_landmark.get_landmark(face_image, (x1, y1, x2, y2))
            face_marks = np.array(face_marks)
            mark_group.append(face_marks)

            # process landmarks for left eye
            x1, y1, x2, y2 = self.eye.get_eye_roi(face_marks, 0)
            left_eye_image = frame[y1:y2, x1:x2]
            left_eye_marks, left_iris_marks = self.eye.get_landmark(
                left_eye_image, (x1, y1, x2, y2), 0
            )
            mark_group.append(np.array(left_iris_marks))

            # process landmarks for right eye
            x1, y1, x2, y2 = self.eye.get_eye_roi(face_marks, 1)
            right_eye_image = frame[y1:y2, x1:x2]
            right_eye_marks, right_iris_marks = self.eye.get_landmark(
                right_eye_image, (x1, y1, x2, y2), 1
            )
            mark_group.append(np.array(right_iris_marks))

            # process landmarks for eyes
            left_eye_ratio = self.eye.blinking_ratio(left_eye_marks, 0)
            right_eye_ratio = self.eye.blinking_ratio(right_eye_marks, 1)

            # average the left eye status in a window of LEFT_W frames
            for i in range(LEFT_W - 1):
                LEFT_EYE_STATUS[i] = LEFT_EYE_STATUS[i + 1]

            if left_eye_ratio > LEFT_EYE_THRESHOLD:
                LEFT_EYE_STATUS[LEFT_W - 1] = 1
            else:
                LEFT_EYE_STATUS[LEFT_W - 1] = 0

            # average the right eye status in a window of RIGHT_W frames
            for i in range(RIGHT_W - 1):
                RIGHT_EYE_STATUS[i] = RIGHT_EYE_STATUS[i + 1]

            if right_eye_ratio > RIGHT_EYE_THRESHOLD:
                RIGHT_EYE_STATUS[RIGHT_W - 1] = 1
            else:
                RIGHT_EYE_STATUS[RIGHT_W - 1] = 0

            if np.mean(LEFT_EYE_STATUS) < 0.5 and np.mean(RIGHT_EYE_STATUS) < 0.5:
                sleep = False
            else:
                sleep = True

            mouth_ratio = self.mouth.yawning_ratio(face_marks)
            if mouth_ratio > MOUTH_THRESHOLD:
                yawn = False
            else:
                yawn = True

            mouth_face_ratio = self.mouth.mouth_face_ratio(face_marks)
            if (
                mouth_face_ratio < FACING_LEFT_THRESHOLD
                or mouth_face_ratio > FACING_RIGHT_THRESHOLD
            ):
                attention = False
            else:
                attention = True
        else:
            face_cords = []

        self.marks = mark_group
        self.face_cords = face_cords
        self.smk_call_cords = smk_call_cords
        self.distracted = not attention
        self.drowsy = not sleep
        self.yawn = not yawn
        self.smoking = not smk
        self.phone = not call
        if not attention:
            self.safe_value = min(self.safe_value + DISTRACT_PENALTY, 100.00)
        if not sleep:
            self.safe_value = min(self.safe_value + SLEEP_PENALTY, 100.00)
        if not yawn:
            self.safe_value = min(self.safe_value + YAWN_PENALTY, 100.00)
        if not smk:
            self.safe_value = min(self.safe_value + SMK_PENALTY, 100.00)
        if not call:
            self.safe_value = min(self.safe_value + CALL_PENALTY, 100.00)
        if not face_cords:
            self.safe_value = min(self.safe_value + NO_FACE_PENALTY, 100.00)
        if attention and sleep and yawn and smk and call and face_cords:
            self.safe_value = max(self.safe_value + RESTORE_CREDIT, 0.00)

        buffer.unmap(mem_buf)
        return 0

    def transform_to_square(self, boxes, scale=1.0, offset=(0, 0)):
        """Get the square bounding boxes.
        Args:
            boxes: input boxes [[xmin, ymin, xmax, ymax], ...]
            scale: ratio to scale the boxes
            offset: a tuple of offset ratio to move the boxes (x, y)
        Returns:
            boxes: square boxes.
        """
        xmins, ymins, xmaxs, ymaxs = np.split(boxes, 4, 1)
        width = xmaxs - xmins
        height = ymaxs - ymins

        # How much to move.
        offset_x = offset[0] * width
        offset_y = offset[1] * height

        # Where is the center location.
        center_x = np.floor_divide(xmins + xmaxs, 2) + offset_x
        center_y = np.floor_divide(ymins + ymaxs, 2) + offset_y

        # Make them squares.
        margin = np.floor_divide(np.maximum(height, width) * scale, 2)
        boxes = np.concatenate(
            (
                center_x - margin,
                center_y - margin,
                center_x + margin,
                center_y + margin,
            ),
            axis=1,
        )

        return boxes

    def clip_boxes(self, boxes, margins):
        """Clip the boxes to the safe margins.
        Args:
            boxes: input boxes [[xmin, ymin, xmax, ymax], ...].
            margins: a tuple of 4 int (left, top, right, bottom)
            as safe margins.
        Returns:
            boxes: clipped boxes.
            clip_mark: the mark of clipped sides, like [[True,
            False, False, False], ...]
        """
        left, top, right, bottom = margins

        clip_mark = (
            boxes[:, 1] < top,
            boxes[:, 0] < left,
            boxes[:, 3] > bottom,
            boxes[:, 2] > right,
        )

        boxes[:, 1] = np.maximum(boxes[:, 1], top)
        boxes[:, 0] = np.maximum(boxes[:, 0], left)
        boxes[:, 3] = np.minimum(boxes[:, 3], bottom)
        boxes[:, 2] = np.minimum(boxes[:, 2], right)

        return boxes, clip_mark

    def increase_brightness(self, image):
        """Increase the brightness of input image, used for monochrome camera"""
        image = image.astype(np.uint16) * 4
        image[image > 255] = 255
        image = image.astype(np.uint8)
        return image

    def draw(self, overlay, context, timestamp, duration):
        """Draw the DMS inference result on the display"""
        context.select_font_face(
            "Arial", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD
        )
        scale = 1072.00 / FRAME_HEIGHT
        offset = 840
        context.set_source_rgb(0, 1, 0)
        context.set_line_width(3)

        # draw smk_call_cords if enabled by DRAW_SMK_CALL_CORDS
        if self.smk_call_cords and DRAW_SMK_CALL_CORDS:
            for cords in self.smk_call_cords:
                context.rectangle(
                    (cords[0] * scale) + offset,
                    (cords[1] * scale),
                    (cords[2] - cords[0]) * scale,
                    (cords[3] - cords[1]) * scale,
                )
            context.stroke()

        # draw landmark point if enabled by DRAW_LANDMARKS
        if self.marks and DRAW_LANDMARKS:
            for m in self.marks:
                for mark in m:
                    mark = mark * scale
                    mark[0] = mark[0] + offset
                    point = tuple(mark.astype(int))
                    context.arc(point[0], point[1], 1, 0, 1)
                    context.stroke()

        if self.face_cords:
            self.write_text(context, self.distracted, 410, 680)
            self.write_text(context, self.drowsy, 410, 765)
            self.write_text(context, self.yawn, 410, 850)
            self.write_text(context, self.smoking, 410, 935)
            self.write_text(context, self.phone, 410, 1020)
            context.set_source_rgb(0, 1, 0)
            context.rectangle(
                (self.face_cords[0][0] * scale) + offset,
                (self.face_cords[0][1] * scale),
                (self.face_cords[0][2] - self.face_cords[0][0]) * scale,
                (self.face_cords[0][3] - self.face_cords[0][1]) * scale,
            )
            context.stroke()
        else:
            self.write_text(context, None, 410, 680)
            self.write_text(context, None, 410, 765)
            self.write_text(context, None, 410, 850)
            self.write_text(context, None, 410, 935)
            self.write_text(context, None, 410, 1020)
        self.write_status(context)

    def write_text(self, context, yes, y, x):
        """Write text on the display"""
        context.set_font_size(int(45.0))
        context.move_to(y, x)
        if yes is None:
            context.set_source_rgb(0, 0, 0)
            context.show_text("N/A")
            return
        if yes:
            context.set_source_rgb(1, 0, 0)
            context.show_text("Yes")
        else:
            context.set_source_rgb(0, 1, 0)
            context.show_text("No")
        return

    def write_status(self, context):
        """Write driver's status on the display"""
        context.set_font_size(int(60.0))
        context.move_to(25, 600)
        r = min(self.safe_value / 50.0, 1.0)
        g = min(1.0, (100.0 - self.safe_value) / 50.0)
        b = 0
        context.set_source_rgb(r, g, b)
        if self.face_cords:
            if self.safe_value < 33:
                context.show_text("Driver OK (" + str(round(self.safe_value, 2)) + "%)")
            elif self.safe_value < 66:
                context.show_text("Warning! (" + str(round(self.safe_value, 2)) + "%)")
            else:
                context.show_text("Danger! (" + str(round(self.safe_value, 2)) + "%)")
        else:
            context.show_text(
                "Driver not found! (" + str(round(self.safe_value, 2)) + "%)"
            )


if __name__ == "__main__":
    os.environ["XDG_RUNTIME_DIR"] = "/run/user/0"
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--device", type=str, default="/dev/video0", help="Camera device to be used"
    )
    parser.add_argument(
        "--backend", type=str, default="NPU", help="Use NPU or CPU to do inference"
    )
    parser.add_argument(
        "--model_path", type=str, default=cur_path, help="Path for models and image"
    )
    args = parser.parse_args()
    Gst.init(None)
    window = DMSDemo(args.device, args.backend, args.model_path)
    while True:
        quit_demo = input("Enter q to exit:")
        if quit_demo == "q":
            print("Exiting...")
            sys.exit()
