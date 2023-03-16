"""
Copyright 2023 NXP

SPDX-License-Identifier: BSD-3-Clause

This script calls the respective files for running the
processes of starting, stopping traffics and applying
TSN configurations based on the buttons in the UI.
"""

import paramiko
import time
import sys,os
import subprocess
import shlex
import time

if( len(sys.argv) == 4):

    hostUserName = sys.argv[2]
    hostIP = sys.argv[3]
    hostPwd = "null"
    try:
        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostIP,port = 22, username = hostUserName, password = hostPwd, timeout = 10.0, pkey = None)
        print("true")

    except:
        print("false")
        exit()

    if(sys.argv[1] == "start"):
        os.system("rm /home/root/.nxp-demo-experience/scripts/TSN/qbv/iperf.txt")
        os.system("rm /home/root/.nxp-demo-experience/scripts/TSN/qbv/iperf1.txt")
        os.system("rm /home/root/.nxp-demo-experience/scripts/TSN/qbv/FPS.txt")
        ssh.exec_command("sh /home/root/.nxp-demo-experience/scripts/TSN/qbv/start_qbv_priority.sh &")
        time.sleep(3)
        os.system("iperf -s -i 1 -u >> /home/root/.nxp-demo-experience/scripts/TSN/qbv/iperf.txt &")
        time.sleep(2)
        ssh.exec_command("iperf -c 172.15.0.5 -i 1 -t 100000 -b 900M -u > /dev/null &")
        time.sleep(2)
        os.system("cat /home/root/.nxp-demo-experience/scripts/TSN/qbv/video.txt | tail -n 1 | awk '{print $0}'> /home/root/.nxp-demo-experience/scripts/TSN/qbv/video1.txt")
        f = open("/home/root/.nxp-demo-experience/scripts/TSN/qbv/video1.txt", "r")
        f=f.read()
        y=f.replace('\n','')
        ssh.exec_command("python3 /home/root/.nxp-demo-experience/scripts/TSN/qbv/camera_server.py " + y)
        time.sleep(2)
        os.system("python3 /home/root/.nxp-demo-experience/scripts/TSN/qbv/camera_client.py > /dev/null &")
        time.sleep(2)
        os.system("chmod 777 /home/root/.nxp-demo-experience/scripts/TSN/qbv/iperf.txt");
        os.system("python3 /home/root/.nxp-demo-experience/scripts/TSN/qbv/tsn_config_graph.py")
    elif(sys.argv[1] == "no_qbv"):
        ssh.exec_command("sh /home/root/.nxp-demo-experience/scripts/TSN/qbv/no_qbv.sh")
        time.sleep(2)
    elif(sys.argv[1] == "qbv1"):
        ssh.exec_command("sh /home/root/.nxp-demo-experience/scripts/TSN/qbv/qbv1.sh")
        time.sleep(2)
    elif(sys.argv[1] == "qbv2"):
        ssh.exec_command("sh /home/root/.nxp-demo-experience/scripts/TSN/qbv/qbv2.sh")
        time.sleep(2)
    elif(sys.argv[1] == "stop"):
        ssh.exec_command("sh /home/root/.nxp-demo-experience/scripts/TSN/qbv/stop_qbv_priority.sh")
        ssh.exec_command("sh /home/root/.nxp-demo-experience/scripts/TSN/qbv/kill_server_process.sh")
        os.system("sh /home/root/.nxp-demo-experience/scripts/TSN/qbv/kill_client_process.sh")
        
    else:
        print("Wrong arguments")
else:
    print("Usage:")
    print("\t start/stop host_name host_ip_address host_password")
    print("\t Eg: python tsnqbv.py start xxx IP xxx123")
