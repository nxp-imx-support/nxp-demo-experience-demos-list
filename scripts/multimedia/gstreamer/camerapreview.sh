#!/bin/bash

# Copyright 2019 NXP
# SPDX-License-Identifier: BSD-2-Clause

gst-launch-1.0 v4l2src device=/dev/video0 num-buffers=200 ! video/x-raw,width=640,height=480 ! glimagesink
