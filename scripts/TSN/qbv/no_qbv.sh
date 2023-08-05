#!/bin/bash

# Copyright 2023 NXP
# SPDX-License-Identifier: BSD-3-Clause
#
# This scripts removes the applied TSN Qbv configurations.

/sbin/tc qdisc del dev eth1 parent root handle 100 taprio num_tc 5 map 0 1 2 3 4 queues 1@0 1@1 1@2 1@3 1@4 base-time 0 sched-entry S 0x01 500000 sched-entry S 0x5 500000 flags 2 >> /dev/null &
sleep 2 
/sbin/tc qdisc del dev eth1 parent root handle 100 taprio num_tc 5 map 0 1 2 3 4 queues 1@0 1@1 1@2 1@3 1@4 base-time 0 sched-entry S 0x04 500000 sched-entry S 0x5 130000 flags 2 >> /dev/null &
sleep 1

