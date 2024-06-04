#!/bin/bash

# Copyright 2023-2024 NXP
# SPDX-License-Identifier: BSD-3-Clause
#
# This scripts stops the running processes in the client, 
# removes the IP to the interfaces and removes the log files 
# created while demo execution.

killall python3
sleep 0.1
killall iperf
sleep 0.1
ifconfig eth0 0 up
sleep 0.1
ifconfig eth1 0 up
sleep 0.1
rm /opt/gopoint-apps/scripts/TSN/qbv/iperf.txt
rm /opt/gopoint-apps/scripts/TSN/qbv/iperf1.txt
rm /opt/gopoint-apps/scripts/TSN/qbv/FPS.txt
rm /opt/gopoint-apps/scripts/TSN/qbv/video.txt
rm /opt/gopoint-apps/scripts/TSN/qbv/video1.txt
