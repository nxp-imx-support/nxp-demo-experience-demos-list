#!/bin/bash

# Copyright 2023 NXP
# SPDX-License-Identifier: BSD-3-Clause
#
# This scripts stops the running processes in the server.

killall iperf
sleep 0.1
killall python3
sleep 0.1

