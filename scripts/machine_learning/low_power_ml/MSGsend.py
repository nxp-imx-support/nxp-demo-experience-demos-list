#!/usr/bin/env python3

"""
Copyright 2024 NXP
SPDX-License-Identifier: BSD-3-Clause

This script define class of MSG_client used to send
message to server in socket communication
"""

import socket
import os


class MSG_client:
    """The Class used to send message to server"""

    def __init__(self, server_ip=None):
        self.server_ip = server_ip
        self.connected = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self):
        """Connect to the server"""

        print("Trying to connect server ", self.server_ip)
        err = self.sock.connect_ex((self.server_ip, 10819))
        if err == 0:
            print("Connected to Server")
            self.connected = True
        else:
            print("Connect to Server failed, error is ", os.strerror(err))

    def send_msg(self, msg):
        """Send message to the server"""

        if self.connected is True:
            try:
                self.sock.send(bytes(msg, encoding="utf8"))
            except socket.error:
                print("socket error")
                self.close()
                self.connected = False
        else:
            if self.server_ip is not None:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.connect()
                if self.connected is True:
                    try:
                        self.sock.send(bytes(msg, encoding="utf8"))
                    except socket.error:
                        print("socket error")
                        self.close()
                        self.connected = False
                else:
                    print("Failed to reconnect to Server")
            else:
                print("Missing Server IP address")

    def close(self):
        """Close connection"""

        self.sock.close()
