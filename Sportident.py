#!/usr/bin/python3
#
################################################
# Package for communication with SPORTident HW
#
# Author:  Martin Horak
# Version: 1.1
# Date:    9. 12. 2018
#
################################################

# Communication constants
WAKE = 0xff;
STX = 0x02;
ETX = 0x03;
ACK = 0x06;
NAK = 0x15;
DLE = 0x10;

import os

##################################
# SI lowlevel functions
##################################

#--------------------------------#
def crc_l(length, data):
    """CRC computation."""
    Polynom = 0x8005;
    Bitmask = 0x8000;
    Intmask = 0xFFFF;

    p = 0
    if length < 2: return 0
    sum0 = data[p]
    p += 1
    sum0 = (sum0 << 8) + data[p]
    p += 1

    if length == 2: return sum0

    i = length >> 1
    while i > 0:
        if i > 1:
            sum1 = data[p]
            p += 1
            sum1 = ((sum1 << 8) & Intmask) + data[p]
            p += 1
        else:
            if length & 1:
                sum1 = data[p] << 8
                p += 1
            else:
                sum1 = 0

        for k in range(0,16):
            if sum0 & Bitmask:
                sum0 = (sum0 << 1) & Intmask
                if sum1 & Bitmask: sum0 = sum0 + 1 & Intmask
                sum0 ^= Polynom
            else:
                sum0 = (sum0 << 1) & Intmask
                if sum1 & Bitmask: sum0 = sum0 + 1 & Intmask
            sum1 = (sum1 << 1) & Intmask
        i -= 1
    return sum0

#--------------------------------#
def crc(data):
    """CRC computation of all data (length calculated)."""
    length = len(data)
    return si_crc_l(length, data)

#--------------------------------#
def station_detect():
    """Detect device of connected SI master station"""
    SI_VENDOR_ID = '10c4'
    SI_PRODUCT_ID = '800a'
    devices = []

    for root, dirs, files in os.walk('/sys/devices'):
        if os.path.basename(root).startswith('ttyUSB'):
            idroot = os.path.dirname(os.path.dirname(root))   # Two levels up
            if os.path.isfile(idroot+"/idVendor") and os.path.isfile(idroot+"/idProduct"):
                with open(idroot+"/idVendor") as f:
                    vendor = f.read().replace('\n', '')
                with open(idroot+"/idProduct") as f:
                    product = f.read().replace('\n', '')
                if vendor == SI_VENDOR_ID and product == SI_PRODUCT_ID:
                    devices.append(os.path.basename(root))
    return devices
