#!/usr/bin/env python3

"""
Copyright 2023-2024 NXP
SPDX-License-Identifier: BSD-3-Clause

This script define class of smoking/calling detection used in DMS demo
"""
import time
import numpy as np
import tflite_runtime.interpreter as tflite
import cv2

ANCHORS_TINY = [23, 27, 37, 58, 81, 82, 81, 82, 135, 169, 344, 319]
STRIDES = [16, 32]
ANCHORS = np.array(ANCHORS_TINY)
ANCHORS.reshape(2, 3, 2)
NUM_CLASS = 2
XYSCALE = [1.05, 1.05]


class SmokingCallingDetector:
    """The class to detect smoking and calling behavior"""

    def __init__(self, model_path, inf_device, platform, iou=0.25, conf=0.55):
        """
        Creates an instance of the smoking/calling detector

        Arguments:
        model_path -- the path to the model
        inf_device -- the inference device, CPU or NPU
        platform -- the plaform that running this demo
        iou -- the overlay threshold for nms
        conf -- the threshold for confidence scores
        """
        if inf_device == "NPU":
            if platform == "i.MX8MP":
                delegate = tflite.load_delegate("/usr/lib/libvx_delegate.so")
            elif platform == "i.MX93":
                delegate = tflite.load_delegate("/usr/lib/libethosu_delegate.so")
            else:
                print("Platform not supported!")
                return
            self.interpreter = tflite.Interpreter(
                model_path=model_path, experimental_delegates=[delegate]
            )
        else:
            self.interpreter = tflite.Interpreter(model_path=model_path)

        self.nms_threshold = iou
        self.conf_threshold = conf
        self.labels = ["phone", "smoke"]
        self.max_wh = 0
        self.raw_frame_width = 0
        self.raw_frame_height = 0
        self.result = []

        self.interpreter.allocate_tensors()
        # model warm up
        time_start = time.time()
        self.interpreter.invoke()
        time_end = time.time()
        print("smk/calling model warm up time:")
        print((time_end - time_start) * 1000, " ms")

        self.input_details = self.interpreter.get_input_details()
        self.input_height = self.input_details[0]["shape"][1]
        self.input_width = self.input_details[0]["shape"][2]
        self.input_type = self.input_details[0]["dtype"]

        self.output_details = self.interpreter.get_output_details()

    def inference(self, input_image, mono):
        """Detect smoking and calling behavior from input_image and return the bounding box"""
        raw_frame_shape = input_image.shape
        self.raw_frame_width = raw_frame_shape[1]
        self.raw_frame_height = raw_frame_shape[0]

        # preprocess
        if mono:
            print("not supported yet")
        else:
            original_image = cv2.cvtColor(input_image, cv2.COLOR_BGR2RGB)
            resized_img_rgb = cv2.resize(
                original_image, (self.input_width, self.input_height)
            )
            input_data = np.float32(resized_img_rgb) / 255.0

        # send data
        self.interpreter.set_tensor(
            self.input_details[0]["index"], np.expand_dims(input_data, axis=0)
        )
        # inference
        self.interpreter.invoke()
        pred = [
            self.interpreter.get_tensor(self.output_details[i]["index"])
            for i in range(len(self.output_details))
        ]

        # postprocess
        self.result = self.filter_boxes(pred[1], pred[0])

        result = []
        if len(self.result) > 0:
            num_result = len(self.result[2])
            for i in range(0, num_result):
                temp = self.result[0][i].tolist()
                temp.append(self.result[1][i].tolist())
                temp.append(self.result[2][i].tolist())
                temp[:4] = self.scale_coords(
                    [self.input_width, self.input_height],
                    temp[:4],
                    [self.raw_frame_height, self.raw_frame_width],
                )
                result.append(temp)
        result = np.array(result)
        return result

    def scale_coords(self, img1_shape, coords, img0_shape):
        """Scale the coordinates from img1_shape to img0_shape"""
        gain = min(img1_shape[0] / img0_shape[0], img1_shape[1] / img0_shape[1])
        pad = (img1_shape[1] - img0_shape[1] * gain) / 2, (
            img1_shape[0] - img0_shape[0] * gain
        ) / 2

        coords[0] -= pad[0]
        coords[2] -= pad[0]
        coords[1] -= pad[1]
        coords[3] -= pad[1]
        coords[:4] /= gain
        self.clip_coords(coords, img0_shape)
        return coords

    def clip_coords(self, boxes, shape):
        """Clip the boxes to the safe margins"""
        boxes[0] = round(boxes[0].clip(0, shape[1]))
        boxes[2] = round(boxes[2].clip(0, shape[1]))
        boxes[1] = round(boxes[1].clip(0, shape[0]))
        boxes[3] = round(boxes[3].clip(0, shape[0]))

    def filter_boxes(self, box_xywh, scores):
        """Filter all the detections and return the best ones"""
        pred_conf = scores[0]
        # for each possible detection, get the max score of all classes
        box_max_scores = np.max(pred_conf, axis=1)
        # for each possible detection, get the class index which has the max score
        box_max_score_classes = np.argmax(pred_conf, axis=1)
        # keep the detections that has score over threshold
        conf_keep_idx = np.where(box_max_scores > self.conf_threshold)[0]

        classes_score = box_max_scores[conf_keep_idx]
        classes_id = box_max_score_classes[conf_keep_idx]
        boxes = self.xywhtoxyxy(box_xywh[0][conf_keep_idx, :])

        if len(conf_keep_idx) < 1:
            return []
        if len(conf_keep_idx) == 1:
            return (np.expand_dims(boxes, axis=0), classes_score, classes_id)

        result_index = self.nms(boxes, classes_score)

        return [
            boxes[result_index],
            classes_score[result_index],
            classes_id[result_index],
        ]

    def xywhtoxyxy(self, x):
        """Convert x_center, y_center, width, height to xmin, ymin, xmax, ymax"""
        y1 = x[:, 0] - x[:, 2] / 2
        y2 = x[:, 1] - x[:, 3] / 2
        y3 = x[:, 0] + x[:, 2] / 2
        y4 = x[:, 1] + x[:, 3] / 2
        y = np.squeeze(np.dstack((y1, y2, y3, y4)))
        return y

    def nms(self, rect_box, scores):
        """Return only the most significant detections"""
        x1 = rect_box[:, 0]
        y1 = rect_box[:, 1]
        x2 = rect_box[:, 2]
        y2 = rect_box[:, 3]
        order = scores.argsort()[::-1]

        areas = (x2 - x1 + 1e-3) * (y2 - y1 + 1e-3)
        temp_iou = []

        while order.size > 0:
            i = order[0]
            temp_iou.append(i)

            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0.0, xx2 - xx1 + 1e-3)
            h = np.maximum(0.0, yy2 - yy1 + 1e-3)
            inter = w * h
            ovr = inter / (areas[i] + areas[order[1:]] - inter)

            inds = np.where(ovr <= self.nms_threshold)[0]
            order = order[inds + 1]

        return temp_iou

    def draw_result(self, input_image, show_label=True):
        """Draw the result on the input_image and save as jpg file"""
        if len(self.result) == 0:
            num_result = 0
        else:
            num_result = len(self.result[2])

        colors = [(0, 255, 0), (255, 0, 0)]
        font_scale = 0.5
        bbox_thick = int(0.6 * (self.raw_frame_width + self.raw_frame_height) / 600)

        for i in range(0, num_result):
            left = int(self.result[0][i][0] * self.raw_frame_width / self.input_width)
            top = int(self.result[0][i][1] * self.raw_frame_height / self.input_height)
            right = int(self.result[0][i][2] * self.raw_frame_width / self.input_width)
            bottom = int(
                self.result[0][i][3] * self.raw_frame_height / self.input_height
            )

            cv2.rectangle(
                input_image,
                (left, top),
                (right, bottom),
                colors[self.result[2][i]],
                bbox_thick,
            )

            if show_label and self.result[2][i] < 2:
                bbox_mess = f"{self.labels[self.result[2][i]]}: {self.result[1][i]:.2f}"
                t_size = cv2.getTextSize(
                    bbox_mess, 0, font_scale, thickness=bbox_thick // 2
                )[0]
                c3 = (left + t_size[0], top - t_size[1] - 3)
                cv2.rectangle(
                    input_image,
                    (left, top),
                    (np.int32(c3[0]), np.int32(c3[1])),
                    colors[self.result[2][i]],
                    -1,
                )  # filled

                cv2.putText(
                    input_image,
                    bbox_mess,
                    (left, np.int32(top - 2)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    font_scale,
                    (0, 0, 0),
                    bbox_thick // 2,
                    lineType=cv2.LINE_AA,
                )

        cv2.imwrite("img_out_test.jpg", input_image)
