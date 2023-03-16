#!/bin/bash

###
#Copyright 2023 NXP
#
#SPDX-License-Identifier: BSD-3-Clause
#
#This scripts removes the priority to the queues while
#stopping the demo.
###

/sbin/tc qdisc del dev eth1 parent root handle 100 taprio num_tc 5 map 0 1 2 3 4 queues 1@0 1@1 1@2 1@3 1@4 base-time 0 sched-entry S 0x1f 1000000 flags 2 >> /dev/null &
sleep 3
/sbin/tc qdisc del dev eth1 clsact >> /dev/null & 
