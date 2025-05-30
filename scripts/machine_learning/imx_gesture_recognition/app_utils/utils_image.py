# Copyright 2025 NXP
# SPDX-License-Identifier: Apache-2.0
"""Several functions to manipulate images."""
import cv2
import numpy as np


def _normalize_image(image):
    """Returns an image in the range [-1.0, 1.0]."""
    return np.ascontiguousarray((image / 255.0).astype("float32"))


def preprocess(image, dim):
    """Preprocesses an image for machine learning model inference.

    This function normalizes the input image and resizes it to a squared
    shape of [dim, dim]. If the image is already square, no padding
    is applied.

    Args:
        image (numpy.ndarray): An input frame retrieved from a media source.
        dim (int): Target dimension for the squared output image.

    Returns:
        numpy.ndarray: The preprocessed image, resized and normalized for
            model input.
        dict: A dictionary containing padding information.
            The dictionary contains:
            - 'padding' (tuple): Padding applied in (height, width).
            - 'pad_img_dim' (int): The dimension of the padded image.
    """
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    shape = image.shape

    pad_size = ((max(shape) - shape[0]) // 2, (max(shape) - shape[1]) // 2)
    padded_image = np.pad(
        image,
        ((pad_size[0], pad_size[0]), (pad_size[1], pad_size[1]), (0, 0)),
        mode="constant",
    )

    resized_image = cv2.resize(padded_image, (dim, dim))
    norm_image = _normalize_image(np.ascontiguousarray(resized_image))
    padding = {"pad_size": pad_size, "pad_img_dim": padded_image.shape[0]}

    return norm_image, padding


def crop_rotated_rectangle(image, rect):
    # Get the rotation matrix
    box = cv2.boxPoints(rect).astype("float32")
    width, height = int(rect[1][0]), int(rect[1][1])

    dst_pts = np.array(
        [[0, height - 1], [0, 0], [width - 1, 0], [width - 1, height - 1]],
        dtype="float32",
    )

    # Compute the perspective transformation matrix
    mat = cv2.getPerspectiveTransform(box, dst_pts)
    m_inv = cv2.getPerspectiveTransform(dst_pts, box)

    # Warp the image
    cropped = cv2.warpPerspective(image, mat, (width, height))
    return cropped, m_inv
