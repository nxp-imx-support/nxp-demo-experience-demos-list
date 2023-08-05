#!/bin/bash

# Copyright 2023 NXP
# SPDX-License-Identifier: BSD-3-Clause
#
# This scripts assigns IP to the interfaces
# of the i.mx8mp board.

ifconfig eth0 192.168.0.1 up
sleep 0.2
ifconfig eth1 172.15.0.1 up
sleep 0.2
