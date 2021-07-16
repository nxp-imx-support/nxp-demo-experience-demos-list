#!/usr/bin/python3

import sys
from os.path import exists
import urllib.request

DOWNLOAD_FOLDER = "/home/root/.cache/demoexperience/downloads/"
DOWNLOAD_DB = "/home/root/.nxp-demo-experience/downloads.txt"

def downloadFile(name):
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
    print(name)
    print(path)
    print(url)
    print(alt_url)
    print(sha)
    if exists(path):
        return path
    if exists(DOWNLOAD_FOLDER + name):
        return DOWNLOAD_FOLDER + name
    urllib.request.urlretrieve(download[2],DOWNLOAD_FOLDER + name)
    return DOWNLOAD_FOLDER + name
