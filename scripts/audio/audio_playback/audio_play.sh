#!/bin/sh

# Copyright 2019 NXP
# SPDX-License-Identifier: BSD-2-Clause

amixer -c 0 sset 'Headphone' 100%
[ -f test.wav ] && aplay test.wav || echo "Run the Audio Record demo first."
