#!/bin/bash

# Copyright 2023, 2026 NXP
# SPDX-License-Identifier: BSD-3-Clause
#
# This scripts removes the priority to the queues while
# stopping the demo.

device=$(hostname)
if [[ "$device" == *"8mp"* ]]; then
    FIRST_INTERFACE="eth0"
    SECOND_INTERFACE="eth1"

    ARGS="parent root handle 100 taprio num_tc 5 map 0 1 2 3 4 queues 1@0 1@1 1@2 1@3 1@4 base-time 0 sched-entry S 0x1f 1000000 flags 2"

elif [[ "$device" == *"943"* ]]; then
    FIRST_INTERFACE="eth1"
    SECOND_INTERFACE="eth2"

    ARGS="parent root handle 100 taprio num_tc 4 map 0 1 2 3 queues 1@0 1@1 1@2 1@3 base-time 0 sched-entry S 0x1f 1000000 flags 2"

fi

/sbin/tc qdisc del dev $SECOND_INTERFACE $ARGS >> /dev/null &
sleep 2
/sbin/tc qdisc del dev $SECOND_INTERFACE clsact >> /dev/null & 
