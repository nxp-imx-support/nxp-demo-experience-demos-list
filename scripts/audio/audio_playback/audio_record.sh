#!/bin/sh

# Copyright 2019, 2024 NXP
# SPDX-License-Identifier: BSD-3-Clause

amixer -c 0 sset 'Capture' 100%
arecord -v -d 10 -f cd test.wav
