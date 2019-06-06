#!/bin/sh

amixer -c 0 sset 'Capture' 100%
arecord -v -d 10 -f cd test.wav
