#!/bin/bash

# Copyright 2023, 2026 NXP
# SPDX-License-Identifier: BSD-3-Clause
#
# This scripts removes the applied TSN Qbv configurations.

device=$(hostname)
if [[ "$device" == *"8mp"* ]]; then
    TSN_INTERFACE="eth1"

    ARGS1="num_tc 5 map 0 1 2 3 4 queues 1@0 1@1 1@2 1@3 1@4 base-time 0 sched-entry S 0x01 500000 sched-entry S 0x5 500000 flags 2"
    ARGS2="num_tc 5 map 0 1 2 3 4 queues 1@0 1@1 1@2 1@3 1@4 base-time 0 sched-entry S 0x04 500000 sched-entry S 0x5 130000 flags 2"

elif [[ "$device" == *"943"* ]]; then
    TSN_INTERFACE="eth2"
    
    ARGS1="num_tc 4 map 0 1 2 3 queues 1@0 1@1 1@2 1@3 base-time 0 sched-entry S 0x01 500000 sched-entry S 0x5 500000 flags 2"
    ARGS2="num_tc 4 map 0 1 2 3 queues 1@0 1@1 1@2 1@3 base-time 0 sched-entry S 0x04 500000 sched-entry S 0x5 130000 flags 2"

fi

echo Running: 
echo 1. /sbin/tc qdisc del dev $TSN_INTERFACE parent root handle 100 taprio $ARGS1
echo 2. /sbin/tc qdisc del dev $TSN_INTERFACE parent root handle 100 taprio $ARGS2

/sbin/tc qdisc del dev $TSN_INTERFACE parent root handle 100 taprio $ARGS1 >> /dev/null &
sleep 2 
/sbin/tc qdisc del dev $TSN_INTERFACE parent root handle 100 taprio $ARGS2 >> /dev/null &
sleep 1

