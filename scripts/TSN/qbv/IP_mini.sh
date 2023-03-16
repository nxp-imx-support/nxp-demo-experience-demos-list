#!/bin/bash

###
#Copyright 2023 NXP
#
#SPDX-License-Identifier: BSD-3-Clause
#
#This scripts assigns IP to the interfaces
#in the i.mx8mm board.
###

ifconfig eth0 192.168.0.2 up
sleep 0.2
ifconfig eth1 172.15.0.5 up
sleep 0.2
