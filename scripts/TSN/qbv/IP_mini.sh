#!/bin/bash

# Copyright 2023-2024 NXP
# SPDX-License-Identifier: BSD-3-Clause
#
# This scripts assigns IP to the interfaces
# in the i.MX 8M Mini board.

ifconfig eth1 192.168.0.2 up
sleep 0.2
ifconfig eth0 172.15.0.5 up
sleep 0.2
