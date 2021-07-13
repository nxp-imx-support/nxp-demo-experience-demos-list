#!/usr/bin/python3

import sys
from os.path import exists
import urllib.request
import sqlite3

DOWNLOAD_FOLDER = "/home/root/.cache/demoexperience/downloads/"
DOWNLOAD_DB = "/home/root/.nxp-demo-experience/downloads.db"

def downloadFile(name):
    downloads = sqlite3.connect(DOWNLOAD_DB)
    #try:
    download = downloads.execute("SELECT NAME, PATH, URL, ALT_URL FROM DOWNLOADS WHERE NAME = \"" + name + "\"").fetchone()
    if download is None:
        return -2

    if exists(download[1]):
        return download[1]
    if exists(DOWNLOAD_FOLDER + name):
        return DOWNLOAD_FOLDER + name

    try:
        urllib.request.urlretrieve(download[2],DOWNLOAD_FOLDER + name)
    except:
        return -1
    return DOWNLOAD_FOLDER + name
