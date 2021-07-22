#!/usr/bin/python3

import sys
from os.path import exists
import urllib.request
import subprocess

DOWNLOAD_FOLDER = "/home/root/.cache/demoexperience/downloads/"
DOWNLOAD_DB = "/home/root/.nxp-demo-experience/downloads.txt"

def download_file(name):
    downloads = open(DOWNLOAD_DB, 'r').read().splitlines()
    found = False
    for i in range(len(downloads)):
        if downloads[i] == "name:"+name:
            path = downloads[i+1][5:]
            url = downloads[i+2][4:]
            alt_url = downloads[i+3][8:]
            sha = downloads[i+4][4:]
            found = True
    if not found:
        return -1
    if exists(path):
        loc = path
    elif exists(DOWNLOAD_FOLDER + name):
        loc = DOWNLOAD_FOLDER + name
    else:
        urllib.request.urlretrieve(url,DOWNLOAD_FOLDER + name)
        loc = DOWNLOAD_FOLDER + name
    sha_check = ['sha1sum', loc, '-z']
    check_process = subprocess.Popen(sha_check, stdout=subprocess.PIPE)
    if(sha != check_process.stdout.read().split()[0].decode('utf-8')):
        return -3
    return loc
