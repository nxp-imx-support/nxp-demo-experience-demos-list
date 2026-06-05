#!/bin/bash

# Copyright 2023 NXP
# SPDX-License-Identifier: BSD-3-Clause
#
# This scripts applies the TSN configuration to
# limit iperf traffic. 

device=$(hostname)
if [[ "$device" == *"8mp"* ]]; then
    TSN_INTERFACE="eth1"
    ARGS="num_tc 5 map 0 1 2 3 4 queues 1@0 1@1 1@2 1@3 1@4 base-time 0 sched-entry S 0x01 500000 sched-entry S 0x5 500000 flags 2"

elif [[ "$device" == *"943"* ]]; then
    TSN_INTERFACE="eth2"
    ARGS="num_tc 4 map 0 1 2 3 queues 1@0 1@1 1@2 1@3 base-time 0 sched-entry S 0x01 500000 sched-entry S 0x5 500000 flags 2"

fi

echo Running: /sbin/tc qdisc replace dev $TSN_INTERFACE parent root handle 100 taprio $ARGS
/sbin/tc qdisc replace dev $TSN_INTERFACE parent root handle 100 taprio $ARGS >> /dev/null &
sleep 0.1
