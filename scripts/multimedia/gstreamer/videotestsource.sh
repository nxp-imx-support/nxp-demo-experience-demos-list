#!/bin/bash
gst-launch-1.0 filesrc location=/home/root/demo-launcher/demo/bbb.mov ! video/quicktime ! aiurdemux ! h264parse ! v4l2h264dec ! queue ! imxvideoconvert_g2d ! glimagesink

