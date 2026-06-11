#!/bin/bash

# Copyright 2023-2024, 2026 NXP
# SPDX-License-Identifier: BSD-3-Clause
#
# This scripts stops the running processes in the client, 
# removes the IP to the interfaces and removes the log files 
# created while demo execution.

device=$(hostname)
if [[ "$device" == *"8mm"* ]] || [[ "$device" == *"8mp"* ]]; then
    FIRST_INTERFACE="eth0"
    SECOND_INTERFACE="eth1"
elif [[ "$device" == *"943"* ]]; then
    FIRST_INTERFACE="eth1"
    SECOND_INTERFACE="eth2"
fi

echo Running kill client on $device 
echo First Interface: $FIRST_INTERFACE
echo Second Interface: $SECOND_INTERFACE

killall python3
sleep 0.1
killall iperf
sleep 0.1
ifconfig $FIRST_INTERFACE 0 up
sleep 0.1
ifconfig $SECOND_INTERFACE 0 up
sleep 0.1
rm /opt/gopoint-apps/scripts/communication/TSN-Qbv/iperf.txt
rm /opt/gopoint-apps/scripts/communication/TSN-Qbv/iperf1.txt
rm /opt/gopoint-apps/scripts/communication/TSN-Qbv/FPS.txt
rm /opt/gopoint-apps/scripts/communication/TSN-Qbv/video.txt
rm /opt/gopoint-apps/scripts/communication/TSN-Qbv/video1.txt
