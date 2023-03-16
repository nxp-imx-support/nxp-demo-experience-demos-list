#!/bin/bash

###
#Copyright 2023 NXP
#
#SPDX-License-Identifier: BSD-3-Clause
#
#This scripts assigns priority to the queues before 
#applying the TSN configurations.
###

/sbin/tc qdisc replace dev eth1 parent root handle 100 taprio num_tc 5 map 0 1 2 3 4 queues 1@0 1@1 1@2 1@3 1@4 base-time 0 sched-entry S 0x1f 1000000 flags 2 >> /dev/null &
sleep 3
/sbin/tc qdisc add dev eth1 clsact >> /dev/null &
sleep 2
/sbin/tc filter add dev eth1 egress prio 1 u32 match ip dport 5001 0xffff action skbedit priority 2 >> /dev/null &
