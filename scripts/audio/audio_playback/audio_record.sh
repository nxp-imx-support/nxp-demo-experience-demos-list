#!/bin/sh

# Copyright 2019 NXP
# SPDX-License-Identifier: BSD-2-Clause

amixer -c 0 sset 'Capture' 100%
arecord -v -d 10 -f cd test.wav
