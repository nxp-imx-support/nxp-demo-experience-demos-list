#!/bin/bash

# Copyright 2023-2024 NXP
# SPDX-License-Identifier: BSD-3-Clause
#
# This scripts assigns IP to the interfaces
# of the i.MX 8M Plus board.

device=$(hostname)
if [[ "$device" == *"8mm"* ]] || [[ "$device" == *"8mp"* ]]; then
    FIRST_INTERFACE="eth0"
    SECOND_INTERFACE="eth1"
elif [[ "$device" == *"943"* ]]; then
    FIRST_INTERFACE="eth1"
    SECOND_INTERFACE="eth2"
fi

echo Running IP configuration on $device 
echo First Interface: $FIRST_INTERFACE
echo Second Interface: $SECOND_INTERFACE

ifconfig $FIRST_INTERFACE 192.168.0.1 up
sleep 0.2
ifconfig $SECOND_INTERFACE 172.15.0.1 up
sleep 0.2
